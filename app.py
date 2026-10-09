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
WALLET = "18t9FDLShbkgXZfiaFzSuqFCBgxTitL9aC"
SCANNER_STATE_FILE = "whale_scanner_state.json"
SATOSHIS_PER_BTC = 100_000_000

MAX_BLOCKS_TO_SCAN = 3
MAX_TRANSACTIONS_PER_BLOCK = 25

# ============================================================
# GENERAL DATA HELPERS
# ============================================================

def fetch_json(url, timeout=15):
    """Fetch JSON from a public API; return None if unavailable."""
    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "DormantWhaleRadar/1.0"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def number(value):
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError, OverflowError):
        return "Unavailable"


def btc(satoshis):
    try:
        return f"{int(satoshis) / SATOSHIS_PER_BTC:.8f}"
    except (ValueError, TypeError, OverflowError):
        return "Unavailable"


def time_utc(timestamp):
    try:
        return datetime.fromtimestamp(
            int(timestamp), timezone.utc
        ).strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, TypeError, OverflowError, OSError):
        return "Unavailable"


def address_link(address):
    encoded = urllib.parse.quote(str(address), safe="")
    return f"https://mempool.space/address/{encoded}"


def transaction_link(txid):
    return f"https://mempool.space/tx/{txid}"


def block_link(block_hash):
    return f"https://mempool.space/block/{block_hash}"


# ============================================================# TELEGRAM ALERT CONNECTION
# ============================================================

def send_telegram_alert(message):
    """Send a Telegram message using Streamlit Secrets."""
    try:
        token = st.secrets["TELEGRAM_BOT_TOKEN"]
        chat_id = st.secrets["TELEGRAM_CHAT_ID"]

        if not token or not chat_id:
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": "true",
        }).encode("utf-8")

        request = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "DormantWhaleRadar/1.0",
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=15) as response:
            response_data = json.loads(response.read().decode("utf-8"))
            return response.status == 200 and response_data.get("ok") is True

    except Exception as error:
        print("Telegram alert failed:", type(error).__name__)
        return False


# ============================================================
# SCANNER STATE
# ============================================================

def load_scanner_state():
    """Load transaction IDs already alerted in this app instance."""
    try:
        if not os.path.exists(SCANNER_STATE_FILE):
            return {"alerted_txids": []}

        with open(SCANNER_STATE_FILE, "r", encoding="utf-8") as file:
            state = json.load(file)

        if not isinstance(state, dict):
            return {"alerted_txids": []}

        txids = state.get("alerted_txids", [])
        if not isinstance(txids, list):
            txids = []

        return {"alerted_txids": [str(txid) for txid in txids]}
    except Exception:
        return {"alerted_txids": []}


def save_scanner_state(state):
    try:
        temporary_file = SCANNER_STATE_FILE + ".tmp"
        with open(temporary_file, "w", encoding="utf-8") as file:
            json.dump(state, file)
        os.replace(temporary_file, SCANNER_STATE_FILE)
        return True
    except Exception as error:
        print("Could not save scanner state:", type(error).__name__)
        return False


# ============================================================# NETWORK AND MARKET DATA
# ============================================================

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
        "&include_24hr_change=true"
        "&include_last_updated_at=true"
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
    """Fetch a small sample from recent confirmed blocks, not the whole chain."""
    blocks = fetch_json(f"{API}/blocks")
    if not isinstance(blocks, list):
        return []

    found = []
    seen_txids = set()

    for block in blocks[:MAX_BLOCKS_TO_SCAN]:
        if not isinstance(block, dict):
            continue
        block_hash = block.get("id")
        if not block_hash:
            continue

        txids = fetch_json(f"{API}/block/{block_hash}/txids")
        if not isinstance(txids, list):
            continue

        for txid in txids[:MAX_TRANSACTIONS_PER_BLOCK]:
            if txid in seen_txids:
                continue
            seen_txids.add(txid)
            tx = get_transaction(txid)
            if isinstance(tx, dict):
                found.append(tx)

    return found


# ============================================================# DORMANT WHALE DETECTION
# ============================================================

def check_dormant_whale_transaction(tx, min_whale_btc, dormancy_years):
    """Identify old outputs spent by a transaction in the sampled blocks."""
    if not isinstance(tx, dict):
        return []

    txid = tx.get("txid")
    if not txid:
        return []

    status = tx.get("status", {})
    if not isinstance(status, dict) or not status.get("confirmed"):
        return []

    now = int(time.time())
    dormancy_seconds = int(dormancy_years) * 365 * 24 * 60 * 60
    threshold_timestamp = now - dormancy_seconds
    matches = []

    for vin in tx.get("vin", []):
        if not isinstance(vin, dict):
            continue

        previous_txid = vin.get("txid")
        previous_output_index = vin.get("vout")
        prevout = vin.get("prevout") or {}

        if not previous_txid or not isinstance(prevout, dict):
            continue

        value_satoshis = prevout.get("value")
        address = prevout.get("scriptpubkey_address")

        if not isinstance(value_satoshis, int) or not address:
            continue

        value_btc = value_satoshis / SATOSHIS_PER_BTC
        if value_btc < min_whale_btc:
            continue

        previous_tx = get_transaction(previous_txid)
        if not isinstance(previous_tx, dict):
            continue

        previous_status = previous_tx.get("status", {})
        if not isinstance(previous_status, dict):
            continue
        if not previous_status.get("confirmed"):
            continue

        previous_block_time = previous_status.get("block_time")
        if not isinstance(previous_block_time, int):
            continue

        previous_outputs = previous_tx.get("vout", [])
        if isinstance(previous_outputs, list) and isinstance(previous_output_index, int):
            if 0 <= previous_output_index < len(previous_outputs):
                exact_output = previous_outputs[previous_output_index]
                if isinstance(exact_output, dict):
                    exact_value = exact_output.get("value")
                    exact_address = exact_output.get("scriptpubkey_address")
                    if isinstance(exact_value, int) and exact_value != value_satoshis:
                        continue
                    if exact_address and exact_address != address:
                        continue

        if previous_block_time > threshold_timestamp:
            continue

        matches.append({
            "txid": txid,
            "previous_txid": previous_txid,
            "address": address,
            "value_btc": value_btc,
            "block_time": previous_block_time,
            "dormant_days": (now - previous_block_time) // 86400,
        })

    return matches


def scan_dormant_whale_transaction(tx, min_whale_btc, dormancy_years):
    """Send an alert for a qualifying transaction if Telegram is configured."""
    if not isinstance(tx, dict):
        return 0

    txid = tx.get("txid")
    if not txid:
        return 0

    state = load_scanner_state()
    alerted_txids = set(state.get("alerted_txids", []))
    if txid in alerted_txids:
        return 0

    matches = check_dormant_whale_transaction(
        tx, min_whale_btc, dormancy_years
    )
    if not matches:
        return 0

    alert_lines = [
        "DORMANT BITCOIN WHALE ALERT",
        "",
        f"Selected dormancy target: {dormancy_years} years",
        f"Minimum output value: {min_whale_btc:.8f} BTC",
        "",
        "A qualifying old Bitcoin output was spent in a recent confirmed transaction.",
        "",
        f"Spending transaction: {txid}",
        f"Explorer: {transaction_link(txid)}",
        "",
    ]

    for index, match in enumerate(matches[:10], start=1):
        alert_lines.extend([
            f"Match {index}",
            f"Output value: {match['value_btc']:.8f} BTC",
            f"Previous output address: {match['address']}",
            f"Dormancy: {match['dormant_days']} days",
            f"Previous transaction: {match['previous_txid']}",
            f"Previous transaction time: {time_utc(match['block_time'])}",
            f"Address explorer: {address_link(match['address'])}",
            "",
        ])

    if not send_telegram_alert("\n".join(alert_lines)):
        return 0

    alerted_txids.add(txid)
    state["alerted_txids"] = sorted(alerted_txids)[-5000:]
    save_scanner_state(state)
    return len(matches)


# ============================================================# DESIGN
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
        Large output research · Blockchain verification
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

# ============================================================
# LIVE BITCOIN NETWORK
# ============================================================

st.header("Live Bitcoin Network")
network = get_network()
blocks = network.get("blocks")
mempool = network.get("mempool")
fees = network.get("fees")

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
    st.metric("Latest Block Transactions", number(latest.get("tx_count")))

st.caption("Latest block timestamp: " + time_utc(latest.get("timestamp")))

# ============================================================
# BITCOIN MARKET
# ============================================================

st.header("Bitcoin Market")
price_info = get_btc_price()
market = get_market()

if isinstance(price_info, dict) and isinstance(price_info.get("bitcoin"), dict):
    price = price_info["bitcoin"].get("usd")
    change = price_info["bitcoin"].get("usd_24h_change")
    updated = price_info["bitcoin"].get("last_updated_at")

    if isinstance(price, (int, float)):
        st.metric(
            "Current reported BTC price",
            f"${price:,.2f}",
            f"{change:+.2f}% over 24 hours"
            if isinstance(change, (int, float))
            else None,
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

        chart = pd.DataFrame(market["prices"], columns=["Timestamp", "Price USD"])
        chart["Time"] = pd.to_datetime(chart["Timestamp"], unit="ms", utc=True)
        chart = chart[["Time", "Price USD"]]

        st.subheader("Reported BTC Price History — 24 Hours")
        st.line_chart(chart, x="Time", y="Price USD")
    except Exception:
        st.info("The chart could not be rendered. Try refreshing the page.")

# ============================================================# BITCOIN TRANSACTION FEES
# ============================================================

st.header("Bitcoin Transaction Fees")

if isinstance(fees, dict):
    f1, f2, f3 = st.columns(3)

    with f1:
        st.metric("High Priority", f"{number(fees.get('fastestFee'))} sat/vB")

    with f2:
        st.metric("Medium Priority", f"{number(fees.get('halfHourFee'))} sat/vB")

    with f3:
        st.metric("Low Priority", f"{number(fees.get('hourFee'))} sat/vB")
else:
    st.warning("Transaction fee data is temporarily unavailable.")

# ============================================================
# NETWORK DIFFICULTY
# ============================================================

st.header("Mining Difficulty")
difficulty = network.get("difficulty")

if isinstance(difficulty, dict):
    d1, d2 = st.columns(2)

    with d1:
        change = difficulty.get("difficultyChange")
        change_text = f"{change:.2f}%" if isinstance(change, (int, float)) else "Unavailable"
        st.metric("Difficulty Adjustment", change_text)

    with d2:
        st.metric("Blocks Until Adjustment", number(difficulty.get("remainingBlocks")))

    progress = difficulty.get("progressPercent")
    if isinstance(progress, (int, float)):
        st.progress(max(0.0, min(1.0, progress / 100)))
        st.caption(f"Adjustment progress: {progress:.2f}%")
else:
    st.info("Mining difficulty data is temporarily unavailable.")

# ============================================================
# RECENT BLOCKS
# ============================================================

st.header("Recent Bitcoin Blocks")

if isinstance(blocks, list) and blocks:
    for block in blocks[:5]:
        if not isinstance(block, dict):
            continue

        height = block.get("height")
        block_hash = block.get("id")

        with st.expander(f"Block {number(height)}"):
            col1, col2 = st.columns(2)

            with col1:
                st.write("**Transactions:**", number(block.get("tx_count")))
                st.write("**Timestamp:**", time_utc(block.get("timestamp")))

            with col2:
                st.write("**Block size:**", number(block.get("size")))
                if block_hash:
                    st.link_button("View Block", block_link(block_hash))
else:
    st.info("Recent block information is temporarily unavailable.")

# ============================================================
# WALLET INSPECTOR
# ============================================================

st.header("Bitcoin Wallet Inspector")

wallet_address = st.text_input(
    "Bitcoin address",
    value=WALLET,
    help="Enter a public Bitcoin address to inspect.",
)

if st.button("Inspect Wallet", use_container_width=True):
    if not wallet_address.strip():
        st.warning("Enter a Bitcoin address first.")
    else:
        with st.spinner("Fetching wallet information..."):
            wallet_data = get_address(wallet_address.strip())

        info = wallet_data.get("info")
        transactions = wallet_data.get("transactions")

        if isinstance(info, dict):
            chain = info.get("chain_stats", {})
            mempool_stats = info.get("mempool_stats", {})

            if not isinstance(chain, dict):
                chain = {}
            if not isinstance(mempool_stats, dict):
                mempool_stats = {}

            confirmed_balance = (
                chain.get("funded_txo_sum", 0)
                - chain.get("spent_txo_sum", 0)
            )
            mempool_balance = (
                mempool_stats.get("funded_txo_sum", 0)
                - mempool_stats.get("spent_txo_sum", 0)
            )

            w1, w2, w3 = st.columns(3)
            with w1:
                st.metric("Confirmed Balance", f"{btc(confirmed_balance)} BTC")
            with w2:
                st.metric("Mempool Balance Change", f"{btc(mempool_balance)} BTC")
            with w3:
                st.metric("Confirmed Transactions", number(chain.get("tx_count")))

            st.markdown(
                f"[Open address in Bitcoin explorer]({address_link(wallet_address.strip())})"
            )

            if isinstance(transactions, list) and transactions:
                st.subheader("Recent Wallet Transactions")
                for tx in transactions[:10]:
                    if not isinstance(tx, dict):
                        continue
                    txid = tx.get("txid")
                    if not txid:
                        continue
                    status = tx.get("status", {})
                    if not isinstance(status, dict):
                        status = {}
                    st.markdown(
                        f"- [{txid[:20]}...]({transaction_link(txid)})"
                        f" — {time_utc(status.get('block_time'))}"
                    )
            else:
                st.info("No recent transactions were returned.")
        else:
            st.error("Wallet data could not be retrieved. Check the address and try again.")

# ============================================================# LARGE OUTPUT RESEARCH
# ============================================================

st.header("Large Bitcoin Output Research")
st.write(
    "This section checks outputs from a limited sample of recent transactions. "
    "It does not scan every Bitcoin output and does not prove that an output "
    "remains unspent."
)

if st.button("Find Large Outputs in Sample", use_container_width=True):
    with st.spinner("Retrieving a limited sample of recent transactions..."):
        recent_transactions = get_recent_transactions()

    large_outputs = []
    for tx in recent_transactions:
        txid = tx.get("txid")
        status = tx.get("status", {})
        if not txid or not isinstance(status, dict):
            continue

        for output_index, output in enumerate(tx.get("vout", [])):
            if not isinstance(output, dict):
                continue

            value = output.get("value")
            address = output.get("scriptpubkey_address")
            if not isinstance(value, int):
                continue

            value_btc = value / SATOSHIS_PER_BTC
            if value_btc >= min_btc:
                large_outputs.append({
                    "BTC": value_btc,
                    "Address": address or "Address not available",
                    "Transaction ID": txid,
                    "Output index": output_index,
                    "Confirmed": bool(status.get("confirmed")),
                    "Transaction time": time_utc(status.get("block_time")),
                })

    if large_outputs:
        import pandas as pd

        large_outputs.sort(key=lambda item: item["BTC"], reverse=True)
        st.dataframe(
            pd.DataFrame(large_outputs),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            "Research results are a sample. An output may already have been spent; "
            "verify it with a trusted block explorer before drawing conclusions."
        )
    else:
        st.info("No outputs meeting the threshold were found in the retrieved sample.")

# ============================================================
# DORMANT WHALE SCANNER
# ============================================================

st.header("Dormant Whale Scanner")
st.warning(
    "The scanner examines a limited sample of transactions in recent blocks. "
    "It does not scan the entire blockchain and cannot guarantee every dormant "
    "whale transaction will be found."
)
st.write(f"Minimum output: **{min_btc:.8f} BTC**")
st.write(f"Dormancy target: **{dormancy_years} years**")

if st.button("Run Dormant Whale Scan", type="primary", use_container_width=True):
    with st.spinner("Examining a limited sample of recent transactions..."):
        recent_transactions = get_recent_transactions()
        total_matches = 0
        total_alerts = 0
        progress_bar = st.progress(0.0)
        total = len(recent_transactions)

        for index, tx in enumerate(recent_transactions):
            matches = check_dormant_whale_transaction(tx, min_btc, dormancy_years)
            total_matches += len(matches)
            total_alerts += scan_dormant_whale_transaction(
                tx, min_btc, dormancy_years
            )
            if total:
                progress_bar.progress((index + 1) / total)

        progress_bar.empty()

    s1, s2, s3 = st.columns(3)
    s1.metric("Transactions Examined", number(total))
    s2.metric("Qualifying Old Outputs Found", number(total_matches))
    s3.metric("Alert Matches Sent to Telegram", number(total_alerts))

    if total == 0:
        st.warning("No transactions were retrieved. The blockchain API may be unavailable.")
    elif total_matches == 0:
        st.info("No qualifying dormant outputs were found in this limited sample.")
    else:
        st.success("Scan completed. Check the Telegram alert count for delivery results.")

# ============================================================
# TELEGRAM CONNECTION TEST
# ============================================================

st.header("Telegram Alerts")
st.write("Send a test message to the Telegram destination configured in Streamlit Secrets.")

if st.button("Send Telegram Test", use_container_width=True):
    with st.spinner("Sending Telegram test..."):
        success = send_telegram_alert(
            "Dormant Whale Radar: Telegram connection test successful."
        )

    if success:
        st.success("Telegram accepted the test message.")
    else:
        st.error(
            "Telegram test failed. Check that TELEGRAM_BOT_TOKEN and "
            "TELEGRAM_CHAT_ID are configured correctly in Streamlit Secrets."
        )

# ============================================================# PAYMENT INFORMATION
# ============================================================

st.header("Payment Information")

st.write("Configured payment address:")
st.code(WALLET)

st.write("Configured reference amount:")
st.metric("Reference Amount", f"{0.001:.3f} BTC")

st.caption(
    "This section displays payment information only. It does not verify payments, "
    "activate accounts, or confirm that a transaction has been received."
)

# ============================================================
# FOOTER AND AUTO-REFRESH
# ============================================================

st.divider()
st.caption(
    "Dormant Whale Radar · Public blockchain data research tool. "
    "Results depend on third-party API availability and the limited sample scanned."
)

if auto_refresh:
    st.caption(f"Dashboard refresh interval: {refresh_seconds} seconds.")
    time.sleep(refresh_seconds)
    st.rerun()
