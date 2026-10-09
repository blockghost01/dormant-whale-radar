import json
import os
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

import streamlit as st


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Dormant Whale Radar",
    page_icon="🐋",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# APPLICATION CONFIGURATION
# ============================================================

API = "https://mempool.space/api"

# Preserve the original Bitcoin receiving address.
WALLET = "18t9FDLShbkgXZfiaFzSuqFCBgxTitL9aC"

# Display setting only; this does not verify payments.
PAYMENT_AMOUNT_BTC = 0.001

SCANNER_STATE_FILE = "whale_scanner_state.json"

SATOSHIS_PER_BTC = 100_000_000

# Limit requests during a manual recent-activity scan.
MAX_BLOCKS_TO_SCAN = 3
MAX_TRANSACTIONS_PER_BLOCK = 25
MAX_DORMANT_INPUTS_TO_CHECK = 100


# ============================================================
# GENERAL DATA HELPERS
# ============================================================

def fetch_json(url, timeout=15):
    """Fetch JSON from a public API."""
    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "DormantWhaleRadar/1.0"
            },
        )

        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:
            return json.loads(
                response.read().decode("utf-8")
            )

    except Exception:
        return None


def number(value):
    """Format an integer safely."""
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError, OverflowError):
        return "Unavailable"


def btc(satoshis):
    """Convert satoshis to BTC."""
    try:
        return (
            f"{int(satoshis) / SATOSHIS_PER_BTC:.8f}"
        )
    except (ValueError, TypeError, OverflowError):
        return "Unavailable"


def time_utc(timestamp):
    """Format a Unix timestamp as UTC."""
    try:
        return datetime.fromtimestamp(
            int(timestamp),
            timezone.utc,
        ).strftime("%Y-%m-%d %H:%M UTC")

    except (ValueError, TypeError, OverflowError, OSError):
        return "Unavailable"


def address_link(address):
    encoded = urllib.parse.quote(
        str(address),
        safe="",
    )

    return (
        f"https://mempool.space/address/{encoded}"
    )


def transaction_link(txid):
    return f"https://mempool.space/tx/{txid}"


def block_link(block_hash):
    return f"https://mempool.space/block/{block_hash}"


# ============================================================
# TELEGRAM ALERT CONNECTION
# ============================================================

def send_telegram_alert(message):
    """
    Send a Telegram message using credentials stored in
    Streamlit Secrets.

    Required Streamlit Secrets:

    TELEGRAM_BOT_TOKEN = "your private bot token"
    TELEGRAM_CHAT_ID = "@YourChannelUsername"
    """

    try:
        token = st.secrets["TELEGRAM_BOT_TOKEN"]
        chat_id = st.secrets["TELEGRAM_CHAT_ID"]

        if not token or not chat_id:
            print("Telegram token or chat ID is empty.")
            return False

        url = (
            f"https://api.telegram.org/"
            f"bot{token}/sendMessage"
        )

        payload = urllib.parse.urlencode(
            {
                "chat_id": chat_id,
                "text": message,
                "disable_web_page_preview": "true",
            }
        ).encode("utf-8")

        request = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type":
                    "application/x-www-form-urlencoded",
                "User-Agent": "DormantWhaleRadar/1.0",
            },
            method="POST",
        )

        with urllib.request.urlopen(
            request,
            timeout=15,
        ) as response:

            response_data = json.loads(
                response.read().decode("utf-8")
            )

            return (
                response.status == 200
                and response_data.get("ok") is True
            )

    except Exception as error:
        # Do not print or expose the bot token.
        print(
            "Telegram alert failed:",
            type(error).__name__,
        )

        return False


# ============================================================
# DORMANT WHALE SCANNER STATE
# ============================================================

def load_scanner_state():
    """
    Load previously alerted transaction IDs.

    The local file may not persist permanently on Streamlit
    Cloud. For durable history, use a persistent database.
    """

    try:
        if not os.path.exists(SCANNER_STATE_FILE):
            return {"alerted_txids": []}

        with open(
            SCANNER_STATE_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            state = json.load(file)

        if not isinstance(state, dict):
            return {"alerted_txids": []}

        txids = state.get("alerted_txids", [])

        if not isinstance(txids, list):
            txids = []

        return {
            "alerted_txids": [
                str(txid) for txid in txids
            ]
        }

    except Exception:
        return {"alerted_txids": []}


def save_scanner_state(state):
    """Save the alert history."""
    try:
        temporary_file = SCANNER_STATE_FILE + ".tmp"

        with open(
            temporary_file,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(state, file)

        os.replace(
            temporary_file,
            SCANNER_STATE_FILE,
        )

        return True

    except Exception as error:
        print(
            "Could not save scanner state:",
            type(error).__name__,
        )

        return False


# ============================================================
# NETWORK AND MARKET DATA
# ============================================================

@st.cache_data(ttl=30)
def get_network():
    return {
        "blocks": fetch_json(
            f"{API}/blocks"
        ),
        "mempool": fetch_json(
            f"{API}/mempool"
        ),
        "fees": fetch_json(
            f"{API}/v1/fees/recommended"
        ),
        "difficulty": fetch_json(
            f"{API}/v1/difficulty-adjustment"
        ),
    }


@st.cache_data(ttl=60)
def get_market():
    return fetch_json(
        "https://api.coingecko.com/api/v3/coins/bitcoin/"
        "market_chart?vs_currency=usd&days=1"
    )


@st.cache_data(ttl=60)
def get_btc_price():
    return fetch_json(
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=bitcoin&vs_currencies=usd"
        "&include_24hr_change=true"
        "&include_last_updated_at=true"
    )


@st.cache_data(ttl=30)
def get_address(address):
    encoded = urllib.parse.quote(
        address,
        safe="",
    )

    return {
        "info": fetch_json(
            f"{API}/address/{encoded}"
        ),
        "transactions": fetch_json(
            f"{API}/address/{encoded}/txs"
        ),
    }


@st.cache_data(ttl=60)
def get_transaction(txid):
    return fetch_json(
        f"{API}/tx/{txid}"
    )


@st.cache_data(ttl=60)
def get_recent_transactions():
    """
    Fetch a limited sample of transactions from the
    latest confirmed blocks.

    This is not a complete blockchain scan.
    """

    blocks = fetch_json(
        f"{API}/blocks"
    )

    if not isinstance(blocks, list):
        return []

    found = []
    seen_txids = set()

    for block in blocks[:MAX_BLOCKS_TO_SCAN]:

        block_hash = block.get("id")

        if not block_hash:
            continue

        txids = fetch_json(
            f"{API}/block/{block_hash}/txids"
        )

        if not isinstance(txids, list):
            continue

        for txid in txids[
            :MAX_TRANSACTIONS_PER_BLOCK
        ]:

            if txid in seen_txids:
                continue

            seen_txids.add(txid)

            tx = get_transaction(txid)

            if isinstance(tx, dict):
                found.append(tx)

    return found


# ============================================================
# DORMANT WHALE DETECTION
# ============================================================

def check_dormant_whale_transaction(
    tx,
    min_whale_btc,
    dormancy_years,
):
    """
    Inspect transaction inputs to identify old outputs
    being spent in the recent transaction sample.

    A qualifying input must:
      - Have a known previous output value.
      - Meet the selected BTC threshold.
      - Have a known previous transaction.
      - Have a confirmed parent transaction.
      - Have remained unspent until the current spend.
      - Be older than the selected dormancy period.

    This identifies a qualifying old output being spent.
    It does not prove the current owner's identity.
    """

    if not isinstance(tx, dict):
        return []

    txid = tx.get("txid")

    if not txid:
        return []

    status = tx.get("status", {})

    # Only analyze confirmed spending transactions.
    if not status.get("confirmed"):
        return []

    now = int(time.time())

    # Approximate year length for the selected target.
    dormancy_seconds = (
        int(dormancy_years)
        * 365
        * 24
        * 60
        * 60
    )

    threshold_timestamp = (
        now - dormancy_seconds
    )

    matches = []

    for vin in tx.get("vin", []):

        if not isinstance(vin, dict):
            continue

        previous_txid = vin.get("txid")
        prevout = vin.get("prevout") or {}

        if not previous_txid:
            continue

        if not isinstance(prevout, dict):
            continue

        value_satoshis = prevout.get("value")
        address = prevout.get(
            "scriptpubkey_address"
        )

        if not isinstance(value_satoshis, int):
            continue

        value_btc = (
            value_satoshis / SATOSHIS_PER_BTC
        )

        if value_btc < min_whale_btc:
            continue

        if not address:
            continue

        # Look up the parent transaction to establish
        # the age of the output being spent.
        previous_tx = get_transaction(
            previous_txid
        )

        if not isinstance(previous_tx, dict):
            continue

        previous_status = previous_tx.get(
            "status",
            {},
        )

        if not previous_status.get("confirmed"):
            continue

        previous_block_time = previous_status.get(
            "block_time"
        )

        if not isinstance(previous_block_time, int):
            continue

        if previous_block_time > threshold_timestamp:
            continue

        dormant_days = (
            now - previous_block_time
        ) // 86400

        matches.append(
            {
                "txid": txid,
                "previous_txid": previous_txid,
                "address": address,
                "value_btc": value_btc,
                "block_time": previous_block_time,
                "dormant_days": dormant_days,
            }
        )

    return matches


def scan_dormant_whale_transaction(
    tx,
    min_whale_btc,
    dormancy_years,
):
    """
    Detect qualifying old outputs being spent and send
    a Telegram alert only if the spending transaction
    has not already been recorded.
    """

    if not isinstance(tx, dict):
        return 0

    txid = tx.get("txid")

    if not txid:
        return 0

    state = load_scanner_state()

    alerted_txids = set(
        state.get("alerted_txids", [])
    )

    if txid in alerted_txids:
        return 0

    matches = check_dormant_whale_transaction(
        tx,
        min_whale_btc,
        dormancy_years,
    )

    if not matches:
        return 0

    alert_lines = [
        "DORMANT BITCOIN WHALE ALERT",
        "",
        (
            f"Selected dormancy target: "
            f"{dormancy_years} years"
        ),
        (
            f"Minimum output value: "
            f"{min_whale_btc:.8f} BTC"
        ),
        "",
        (
            "A qualifying old Bitcoin output "
            "was spent in a recent confirmed transaction."
        ),
        "",
        f"Spending transaction: {txid}",
        f"Explorer: {transaction_link(txid)}",
        "",
    ]

    for index, match in enumerate(
        matches[:10],
        start=1,
    ):

        alert_lines.extend(
            [
                f"Match {index}",
                (
                    f"Output value: "
                    f"{match['value_btc']:.8f} BTC"
                ),
                (
                    f"Previous output address: "
                    f"{match['address']}"
                ),
                (
                    f"Dormancy: "
                    f"{match['dormant_days']} days"
                ),
                (
                    f"Previous transaction: "
                    f"{match['previous_txid']}"
                ),
                (
                    f"Previous transaction time: "
                    f"{time_utc(match['block_time'])}"
                ),
                (
                    f"Address explorer: "
                    f"{address_link(match['address'])}"
                ),
                "",
            ]
        )

    message = "\n".join(alert_lines)

    # Do not mark the transaction as alerted if Telegram
    # delivery fails.
    if not send_telegram_alert(message):
        return 0

    alerted_txids.add(txid)

    state["alerted_txids"] = sorted(
        alerted_txids
    )[-5000:]

    save_scanner_state(state)

    return len(matches)


# ============================================================
# DESIGN
# ============================================================

st.markdown(
    """
    <style>
    .stApp {
        background-color: #07111f;
        color: #e6f1ff;
    }

    [data-testid="stSidebar"] {
        background-color: #0b1728;
    }

    .hero {
        padding: 24px;
        border-radius: 16px;
        border: 1px solid #1e4564;
        background: linear-gradient(
            135deg,
            #102b44,
            #07111f
        );
        margin-bottom: 20px;
    }

    .hero h1 {
        color: #61e6ff;
    }

    div[data-testid="stMetric"] {
        background: #0c1b2d;
        border: 1px solid #1b3853;
        padding: 12px;
        border-radius: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


st.markdown(
    """
    <div class="hero">
        <h1>🐋 Dormant Whale Radar</h1>
        <p>Bitcoin On-Chain Analytics Terminal</p>
        <p>
        Live network monitoring · Wallet research ·
        Large unspent outputs · Blockchain verification
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR SETTINGS
# ============================================================

with st.sidebar:

    st.header("Radar Settings")

    min_btc = st.number_input(
        "Minimum output value (BTC)",
        min_value=0.00000001,
        value=10.0,
        step=1.0,
        format="%.8f",
    )

    dormancy_years = st.selectbox(
        "Historical dormancy target",
        [1, 2, 3, 5, 7, 10, 15, 20],
        index=3,
        format_func=lambda n: f"{n} years",
    )

    auto_refresh = st.checkbox(
        "Auto-refresh dashboard",
        value=False,
    )

    refresh_seconds = st.selectbox(
        "Refresh interval",
        [30, 60, 120, 300],
        index=1,
        format_func=lambda n: f"{n} seconds",
    )

    if st.button(
        "Refresh data now",
        use_container_width=True,
    ):
        st.cache_data.clear()
        st.rerun()

    st.caption(
        "Public blockchain information only."
    )

    st.caption(
        "Never enter a wallet recovery phrase "
        "or private key."
    )


# ============================================================
# LIVE BITCOIN NETWORK
# ============================================================

st.header("Live Bitcoin Network")

network = get_network()

blocks = network["blocks"]
mempool = network["mempool"]
fees = network["fees"]

latest = (
    blocks[0]
    if isinstance(blocks, list) and blocks
    else {}
)

c1, c2 = st.columns(2)
c3, c4 = st.columns(2)

with c1:
    st.metric(
        "Latest Block Height",
        number(latest.get("height")),
    )

with c2:
    st.metric(
        "Unconfirmed Transactions",
        number(
            mempool.get("count")
            if isinstance(mempool, dict)
            else None
        ),
    )

with c3:
    size = (
        mempool.get("vsize")
        if isinstance(mempool, dict)
        else None
    )

    st.metric(
        "Mempool Size",
        (
            f"{size / 1_000_000:.2f} MB"
            if isinstance(size, (int, float))
            else "Unavailable"
        ),
    )

with c4:
    st.metric(
        "Latest Block Transactions",
        number(latest.get("tx_count")),
    )

st.caption(
    "Latest block timestamp: "
    + time_utc(latest.get("timestamp"))
)


# ============================================================
# BITCOIN MARKET
# ============================================================

st.header("Bitcoin Market")

price_info = get_btc_price()
market = get_market()

if (
    isinstance(price_info, dict)
    and isinstance(
        price_info.get("bitcoin"),
        dict,
    )
):

    price = price_info["bitcoin"].get("usd")
    change = price_info["bitcoin"].get(
        "usd_24h_change"
    )
    updated = price_info["bitcoin"].get(
        "last_updated_at"
    )

    if isinstance(price, (int, float)):

        st.metric(
            "Current reported BTC price",
            f"${price:,.2f}",
            (
                f"{change:+.2f}% over 24 hours"
                if isinstance(change, (int, float))
                else None
            ),
        )

        st.caption(
            "Provider update time: "
            + time_utc(updated)
            if updated
            else "Provider update timestamp unavailable."
        )

    else:
        st.warning(
            "Current price is unavailable."
        )

else:
    st.warning(
        "Market-price provider is temporarily unavailable."
    )


if (
    isinstance(market, dict)
    and isinstance(market.get("prices"), list)
):

    try:
        import pandas as pd

        chart = pd.DataFrame(
            market["prices"],
            columns=[
                "Timestamp",
                "Price USD",
            ],
        )

        chart["Time"] = pd.to_datetime(
            chart["Timestamp"],
            unit="ms",
            utc=True,
        )

        chart = chart[
            ["Time", "Price USD"]
        ]

        st.subheader(
            "Reported BTC Price History — 24 Hours"
        )

        st.line_chart(
            chart,
            x="Time",
            y="Price USD",
        )

    except Exception:
        st.info(
            "The chart could not be rendered. "
            "Try refreshing the page."
        )


# ============================================================
# BITCOIN TRANSACTION FEES
# ============================================================

st.header("Bitcoin Transaction Fees")

if isinstance(fees, dict):

    f1, f2, f3 = st.columns(3)

    with f1:
        st.metric(
            "High Priority",
            f"{number(fees.get('fastestFee'))} sat/vB",
        )

    with f2:
        st.metric(
            "Medium Priority",
            f"{number(fees.get('halfHourFee'))} sat/vB",
        )

    with f3:
        st.metric(
            "Low Priority",
            f"{number(fees.get('hourFee'))} s
