import json
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

import streamlit as st
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

import streamlit as st

# TELEGRAM ALERT CONNECTION
def send_telegram_alert(message):
    try:
        token = st.secrets["TELEGRAM_BOT_TOKEN"]
        chat_id = st.secrets["TELEGRAM_CHAT_ID"]

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": message
        }).encode("utf-8")

        request = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status == 200

    except Exception as error:
        print(f"Telegram alert failed: {error}")
        return False

st.set_page_config(
    page_title="Dormant Whale Radar",
    page_icon="🐋",
    layout="wide",
    initial_sidebar_state="expanded",
)

API = "https://mempool.space/api"

# Preserve the original Bitcoin receiving address.
WALLET = "18t9FDLShbkgXZfiaFzSuqFCBgxTitL9aC"

# This is a display setting, not a completed payment system.
PAYMENT_AMOUNT_BTC = 0.001


def fetch_json(url, timeout=15):
    """Fetch public data and return None if the service is unavailable."""
    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "DormantWhaleRadar/1.0"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


@st.cache_data(ttl=30)
def get_network():
    return {
        "blocks": fetch_json(f"{API}/blocks"),
        "mempool": fetch_json(f"{API}/mempool"),
        "fees": fetch_json(f"{API}/v1/fees/recommended"),
        "difficulty": fetch_json(f"{API}/v1/difficulty-adjustment"),
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
        "&include_24hr_change=true&include_last_updated_at=true"
    )


@st.cache_data(ttl=30)
def get_address(address):
    encoded = urllib.parse.quote(address, safe="")
    return {
        "info": fetch_json(f"{API}/address/{encoded}"),
        "transactions": fetch_json(f"{API}/address/{encoded}/txs"),
    }


@st.cache_data(ttl=60)
def get_transaction(txid):
    return fetch_json(f"{API}/tx/{txid}")


@st.cache_data(ttl=60)
def get_recent_transactions():
    """
    Fetch transactions from recent confirmed blocks.
    This is a recent-activity scanner, not a full historical scan.
    """
    blocks = fetch_json(f"{API}/blocks")

    if not isinstance(blocks, list):
        return []

    found = []

    for block in blocks[:3]:
        block_hash = block.get("id")

        if not block_hash:
            continue

        txids = fetch_json(f"{API}/block/{block_hash}/txids")

        if not isinstance(txids, list):
            continue

        for txid in txids[:25]:
            tx = get_transaction(txid)

            if isinstance(tx, dict):
                found.append(tx)

    return found


def number(value):
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return "Unavailable"


def btc(satoshis):
    try:
        return f"{int(satoshis) / 100_000_000:.8f}"
    except (ValueError, TypeError):
        return "Unavailable"


def time_utc(timestamp):
    try:
        return datetime.fromtimestamp(
            int(timestamp), timezone.utc
        ).strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, TypeError, OSError):
        return "Unavailable"


def address_link(address):
    encoded = urllib.parse.quote(address, safe="")
    return f"https://mempool.space/address/{encoded}"


def transaction_link(txid):
    return f"https://mempool.space/tx/{txid}"


def block_link(block_hash):
    return f"https://mempool.space/block/{block_hash}"


# Design
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
        background: linear-gradient(135deg, #102b44, #07111f);
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

    auto_refresh = st.checkbox("Auto-refresh dashboard", value=False)

    refresh_seconds = st.selectbox(
        "Refresh interval",
        [30, 60, 120, 300],
        index=1,
        format_func=lambda n: f"{n} seconds",
    )

    if st.button("Refresh data now", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.caption("Public blockchain information only.")
    st.caption("Never enter a wallet recovery phrase or private key.")

# Network overview
st.header("Live Bitcoin Network")

network = get_network()
blocks = network["blocks"]
mempool = network["mempool"]
fees = network["fees"]

latest = blocks[0] if isinstance(blocks, list) and blocks else {}

c1, c2 = st.columns(2)
c3, c4 = st.columns(2)

with c1:
    st.metric("Latest Block Height", number(latest.get("height")))

with c2:
    st.metric(
        "Unconfirmed Transactions",
        number(mempool.get("count") if isinstance(mempool, dict) else None),
    )

with c3:
    size = mempool.get("vsize") if isinstance(mempool, dict) else None
    st.metric(
        "Mempool Size",
        f"{size / 1_000_000:.2f} MB"
        if isinstance(size, (int, float))
        else "Unavailable",
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

# Market information
st.header("Bitcoin Market")

price_info = get_btc_price()
market = get_market()

if isinstance(price_info, dict) and isinstance(
    price_info.get("bitcoin"), dict
):
    price = price_info["bitcoin"].get("usd")
    change = price_info["bitcoin"].get("usd_24h_change")
    updated = price_info["bitcoin"].get("last_updated_at")

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
            "Provider update time: " + time_utc(updated)
            if updated
            else "Provider update timestamp unavailable."
        )
    else:
        st.warning("Current price is unavailable.")
else:
    st.warning("Market-price provider is temporarily unavailable.")

if isinstance(market, dict) and isinstance(market.get("prices"), list):
    try:
        import pandas as pd

        price_rows = market["prices"]

        chart = pd.DataFrame(
            price_rows,
            columns=["Timestamp", "Price USD"],
        )

        chart["Time"] = pd.to_datetime(
            chart["Timestamp"], unit="ms", utc=True
        )

        chart = chart[["Time", "Price USD"]]

        st.subheader("Reported BTC Price History — 24 Hours")
        st.line_chart(chart, x="Time", y="Price USD")
    except Exception:
        st.info("The chart could not be rendered. Try refreshing the page.")

# Fees
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
            f"{number(fees.get('hourFee'))} sat/vB",
        )
else:
    st.warning("Fee estimates are unavailable.")

# Recent blocks
st.header("Recent Confirmed Blocks")

if isinstance(blocks, list) and blocks:
    for block in blocks[:6]:
        block_hash = block.get("id")

        st.markdown(
            f"**Block {number(block.get('height'))}** · "
            f"Transactions: {number(block.get('tx_count'))} · "
            f"{time_utc(block.get('timestamp'))}"
        )

        if block_hash:
            st.markdown(
                f"[Verify block in explorer]({block_link(block_hash)})"
            )

        st.divider()
else:
    st.warning("Block information is unavailable.")

# Wallet inspection
st.header("Bitcoin Wallet Inspector")

wallet = st.text_input(
    "Public Bitcoin address",
    value=WALLET,
)

if st.button("Inspect wallet", type="primary"):
    result = get_address(wallet.strip())

    info = result.get("info")
    history = result.get("transactions")

    if isinstance(info, dict):
        chain = info.get("chain_stats", {})
        pending = info.get("mempool_stats", {})

        confirmed_balance = (
            chain.get("funded_txo_sum", 0)
            - chain.get("spent_txo_sum", 0)
        )

        pending_balance = (
            pending.get("funded_txo_sum", 0)
            - pending.get("spent_txo_sum", 0)
        )

        a, b, c = st.columns(3)

        a.metric("Confirmed Balance", f"{btc(confirmed_balance)} BTC")
        b.metric("Pending Balance Change", f"{btc(pending_balance)} BTC")
        c.metric(
            "Confirmed Transactions",
            number(chain.get("tx_count")),
        )

        st.markdown(
            f"[Open address in blockchain explorer]({address_link(wallet.strip())})"
        )

        st.subheader("Recent Address Transactions")

        if isinstance(history, list) and history:
            for tx in history[:10]:
                txid = tx.get("txid", "")
                status = tx.get("status", {})

                state = (
                    "Confirmed"
                    if status.get("confirmed")
                    else "Unconfirmed"
                )

                st.write(f"{state}: `{txid}`")

                if txid:
                    st.markdown(
                        f"[Verify transaction]({transaction_link(txid)})"
                    )
        else:
            st.info("No recent transactions were returned.")
    else:
        st.error("Wallet lookup failed. Check the address and try again.")

# Recent large unspent outputs
st.header("Large Unspent Output Scanner")

st.write(
    "This scanner inspects outputs in recent confirmed transactions. "
    "It does not search the entire historical blockchain."
)

if st.button("Scan recent transactions"):
    with st.spinner("Retrieving recent transactions and checking outputs..."):
        transactions = get_recent_transactions()

    matches = []

    for tx in transactions:
        txid = tx.get("txid", "")
        status = tx.get("status", {})

        if not status.get("confirmed"):
            continue

        for index, output in enumerate(tx.get("vout", [])):
            value = output.get("value", 0)
            address = output.get("scriptpubkey_address")

            if not isinstance(value, int):
                continue

            if value < int(min_btc * 100_000_000):
                continue

            if not address:
                continue

            matches.append({
                "txid": txid,
                "output_index": index,
                "value": value,
                "address": address,
                "block_time": status.get("block_time"),
            })

    if matches:
        st.success(
            f"Found {len(matches)} matching outputs in the inspected "
            "recent transactions."
        )

        st.caption(
            "These are large outputs from recent confirmed transactions. "
            "Their present unspent status has not yet been independently "
            "verified by this scanner, and they are not proven dormant whales."
        )

        for item in matches[:50]:
            st.markdown(
                f"**{btc(item['value'])} BTC** · "
                f"Transaction output #{item['output_index']}"
            )

            st.caption(
                "Transaction time: " + time_utc(item["block_time"])
            )

            st.markdown(
                f"[Inspect transaction]({transaction_link(item['txid'])})"
            )

            st.divider()
    else:
        st.info(
            "No matching outputs were found in the transactions inspected. "
            "Try a smaller minimum or scan again later."
        )

st.subheader("Historical Dormancy Status")

st.info(
    f"Selected target: {dormancy_years} years. "
    f"Minimum value: {min_btc:.8f} BTC."
)

st.warning(
    "A genuine historical dormant-output scan still requires historical "
    "blockchain indexing and verification of whether each output remains "
    "unspent. The recent-output scan above does not complete that task."
)

# Payment information
st.header("Bitcoin Payment Information")

st.write("Configured receiving address:")
st.code(WALLET)

st.write(f"Displayed payment amount: {PAYMENT_AMOUNT_BTC:.3f} BTC")

qr_data = urllib.parse.quote(
    f"bitcoin:{WALLET}?amount={PAYMENT_AMOUNT_BTC}",
    safe="",
)

st.image(
    "https://api.qrserver.com/v1/create-qr-code/"
    f"?size=220x220&data={qr_data}",
    caption="QR code for the configured Bitcoin payment",
)

st.markdown(
    f"[Verify receiving address]({address_link(WALLET)})"
)

st.warning(
    "This version does not automatically verify customer payments, "
    "send payment emails, store payment records, prevent duplicate claims, "
    "or activate paid accounts. Do not advertise automatic payment "
    "verification until those features are implemented and tested."
)

# Footer
st.divider()
st.caption(
    "Dormant Whale Radar · Independent Bitcoin on-chain analytics"
)
st.caption(
    "Market and blockchain data are supplied by external providers. "
    "This dashboard does not provide investment advice."
)

if auto_refresh:
    time.sleep(refresh_seconds)
    st.rerun()
