import json
import os
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Dormant Whale Radar — Elite On-Chain Terminal",
    page_icon="🐋",
    layout="wide",
    initial_sidebar_state="expanded",
)

API = "https://mempool.space/api"
WALLET = "18t9FDLShbkgXZfiaFzSuqFCBgxTitL9aC"
PAYMENT_AMOUNT_BTC = 0.001
SATOSHIS_PER_BTC = 100_000_000
SCANNER_STATE_FILE = "whale_scanner_state.json"
MAX_BLOCKS_TO_SCAN = 3
MAX_TRANSACTIONS_PER_BLOCK = 25

st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #07111f 0%, #101b2b 55%, #07111f 100%);
    color: #e8eef7;
}
[data-testid="stSidebar"] {
    background: #0b1422;
}
[data-testid="stMetric"] {
    background: #111e30;
    border: 1px solid #263951;
    padding: 16px;
    border-radius: 12px;
}
h1, h2, h3 {
    color: #64d9ff !important;
}
div.stButton > button {
    border-radius: 9px;
    border: 1px solid #2a8fb8;
    font-weight: 600;
}
a {
    color: #64d9ff !important;
}
</style>
""", unsafe_allow_html=True)


def fetch_json(url, timeout=15):
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
    except (TypeError, ValueError, OverflowError):
        return "Unavailable"


def btc(satoshis):
    try:
        return f"{int(satoshis) / SATOSHIS_PER_BTC:.8f}"
    except (TypeError, ValueError, OverflowError):
        return "Unavailable"


def time_utc(timestamp):
    try:
        return datetime.fromtimestamp(
            int(timestamp), timezone.utc
        ).strftime("%Y-%m-%d %H:%M UTC")
    except (TypeError, ValueError, OverflowError, OSError):
        return "Unavailable"


def address_link(address):
    return "https://mempool.space/address/" + urllib.parse.quote(
        str(address), safe=""
    )


def transaction_link(txid):
    return "https://mempool.space/tx/" + urllib.parse.quote(
        str(txid), safe=""
    )


def block_link(block_hash):
    return "https://mempool.space/block/" + urllib.parse.quote(
        str(block_hash), safe=""
    )


def send_telegram_alert(message):
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
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
            return response.status == 200 and result.get("ok") is True

    except Exception:
        return False


def load_scanner_state():
    try:
        with open(SCANNER_STATE_FILE, "r", encoding="utf-8") as file:
            state = json.load(file)
        if isinstance(state, dict) and isinstance(
            state.get("alerted_txids", []), list
        ):
            return state
    except Exception:
        pass

    return {"alerted_txids": []}


def save_scanner_state(state):
    try:
        temporary_file = SCANNER_STATE_FILE + ".tmp"
        with open(temporary_file, "w", encoding="utf-8") as file:
            json.dump(state, file)
        os.replace(temporary_file, SCANNER_STATE_FILE)
        return True
    except Exception:
        return False


@st.cache_data(ttl=30)
def get_network():
    return {
        "blocks": fetch_json(f"{API}/blocks"),
        "mempool": fetch_json(f"{API}/mempool"),
        "fees": fetch_json(f"{API}/v1/fees/recommended"),
        "difficulty": fetch_json(f"{API}/v1/difficulty-adjustment"),
        "hashrate": fetch_json(f"{API}/v1/mining/hashrate/3d"),
    }


@st.cache_data(ttl=60)
def get_btc_price():
    return fetch_json(
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=bitcoin&vs_currencies=usd"
        "&include_24hr_change=true"
        "&include_last_updated_at=true"
    )


@st.cache_data(ttl=60)
def get_market_chart():
    return fetch_json(
        "https://api.coingecko.com/api/v3/coins/bitcoin/"
        "market_chart?vs_currency=usd&days=1"
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
    return fetch_json(f"{API}/tx/{urllib.parse.quote(txid, safe='')}")


@st.cache_data(ttl=60)
def get_recent_transactions():
    blocks = fetch_json(f"{API}/blocks")
    if not isinstance(blocks, list):
        return []

    transactions = []
    seen = set()

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
            if txid in seen:
                continue

            seen.add(txid)
            tx = get_transaction(txid)

            if isinstance(tx, dict):
                transactions.append(tx)

    return transactions


def find_dormant_outputs(tx, min_whale_btc, dormancy_years):
    if not isinstance(tx, dict):
        return []

    if not isinstance(tx.get("status"), dict):
        return []

    if not tx["status"].get("confirmed"):
        return []

    now = int(time.time())
    cutoff = now - int(dormancy_years) * 365 * 24 * 60 * 60
    matches = []

    for vin in tx.get("vin", []):
        if not isinstance(vin, dict):
            continue

        previous_txid = vin.get("txid")
        output_index = vin.get("vout")
        previous_output = vin.get("prevout")

        if not previous_txid or not isinstance(previous_output, dict):
            continue

        value = previous_output.get("value")
        address = previous_output.get("scriptpubkey_address")

        if not isinstance(value, int):
            continue

        value_btc = value / SATOSHIS_PER_BTC

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

        previous_time = previous_status.get("block_time")

        if not isinstance(previous_time, int) or previous_time > cutoff:
            continue

        previous_outputs = previous_tx.get("vout", [])

        if isinstance(output_index, int) and isinstance(previous_outputs, list):
            if 0 <= output_index < len(previous_outputs):
                exact_output = previous_outputs[output_index]

                if isinstance(exact_output, dict):
                    exact_value = exact_output.get("value")
                    exact_address = exact_output.get("scriptpubkey_address")

                    if isinstance(exact_value, int) and exact_value != value:
                        continue

                    if exact_address and address and exact_address != address:
                        continue

        matches.append({
            "Spending transaction": tx.get("txid", ""),
            "Previous transaction": previous_txid,
            "Address": address or "Unavailable",
            "Value (BTC)": value_btc,
            "Last received": time_utc(previous_time),
            "Dormant days": (now - previous_time) // 86400,
        })

    return matches


def alert_new_matches(tx, matches):
    if not matches:
        return 0

    state = load_scanner_state()
    alerted = set(state.get("alerted_txids", []))
    txid = tx.get("txid")

    if not txid or txid in alerted:
        return 0

    sent = 0

    for match in matches:
        message = (
            "DORMANT WHALE RADAR ALERT\n\n"
            f"Value: {match['Value (BTC)']:.8f} BTC\n"
            f"Address: {match['Address']}\n"
            f"Dormant days: {match['Dormant days']:,}\n"
            f"Previous transaction: {match['Previous transaction']}\n"
            f"Spending transaction: {match['Spending transaction']}\n"
            f"Last received: {match['Last received']}\n\n"
            "This alert is based on a limited sample of public blockchain data."
        )

        if send_telegram_alert(message):
            sent += 1

    alerted.add(txid)
    state["alerted_txids"] = list(alerted)[-5000:]
    save_scanner_state(state)

    return sent


st.title("🐋 Dormant Whale Radar")
st.subheader("Elite On-Chain Terminal")
st.caption(
    "Bitcoin network monitoring, large-output research, wallet inspection, "
    "and limited-sample dormant-output detection."
)

with st.sidebar:
    st.header("Scanner Settings")

    min_btc = st.number_input(
        "Minimum whale output (BTC)",
        min_value=0.1,
        max_value=1000000.0,
        value=100.0,
        step=10.0,
    )

    dormancy_years = st.selectbox(
        "Dormancy threshold",
        [1, 2, 3, 4, 5, 7, 10],
        index=4,
        format_func=lambda years: f"{years} years",
    )

    auto_refresh = st.toggle("Automatic refresh", value=False)

    refresh_seconds = st.selectbox(
        "Refresh interval",
        [30, 60, 120, 300],
        index=1,
        format_func=lambda seconds: f"{seconds} seconds",
    )

    if st.button("Refresh data now", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

network = get_network()
blocks = network.get("blocks")
mempool = network.get("mempool")
fees = network.get("fees")
difficulty = network.get("difficulty")
price_data = get_btc_price()

st.header("Live Bitcoin Network")

if isinstance(blocks, list) and blocks:
    latest_block = blocks[0]
    block_height = latest_block.get("height", "Unavailable")
else:
    block_height = "Unavailable"

if isinstance(mempool, dict):
    mempool_count = mempool.get("count", "Unavailable")
    mempool_size = mempool.get("vsize", 0)
    mempool_fees = mempool.get("total_fee", 0)
else:
    mempool_count = "Unavailable"
    mempool_size = 0
    mempool_fees = 0

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Latest Block Height", number(block_height))

with c2:
    st.metric("Mempool Transactions", number(mempool_count))

with c3:
    st.metric("Mempool Size", f"{number(mempool_size)} vB")

with c4:
    st.metric("Mempool Fees", f"{number(mempool_fees)} sats")

st.header("Bitcoin Market")

if isinstance(price_data, dict) and isinstance(
    price_data.get("bitcoin"), dict
):
    bitcoin_data = price_data["bitcoin"]
    price = bitcoin_data.get("usd")
    change = bitcoin_data.get("usd_24h_change")

    market_columns = st.columns(2)

    with market_columns[0]:
        if isinstance(price, (int, float)):
            st.metric("BTC Price (USD)", f"${price:,.2f}")
        else:
            st.metric("BTC Price (USD)", "Unavailable")

    with market_columns[1]:
        if isinstance(change, (int, float)):
            st.metric("24-Hour Change", f"{change:.2f}%")
        else:
            st.metric("24-Hour Change", "Unavailable")
else:
    st.warning("Market price data is temporarily unavailable.")

chart_data = get_market_chart()

if isinstance(chart_data, dict) and isinstance(
    chart_data.get("prices"), list
):
    try:
        price_points = chart_data["prices"]
        chart_frame = pd.DataFrame(
            price_points,
            columns=["Timestamp", "Price"],
        )

        chart_frame["Time"] = pd.to_datetime(
            chart_frame["Timestamp"],
            unit="ms",
            utc=True,
        )

        chart_frame = chart_frame.set_index("Time")[["Price"]]

        st.subheader("BTC Price — Last 24 Hours")
        st.line_chart(chart_frame)
    except Exception:
        st.info("The market chart is temporarily unavailable.")
else:
    st.info("Market chart data is temporarily unavailable.")

st.header("Transaction Fees")

if isinstance(fees, dict):
    f1, f2, f3 = st.columns(3)

    with f1:
        st.metric("Fastest Fee", f"{number(fees.get('fastestFee'))} sat/vB")

    with f2:
        st.metric("Half-Hour Fee", f"{number(fees.get('halfHourFee'))} sat/vB")

    with f3:
        st.metric("Hour Fee", f"{number(fees.get('hourFee'))} sat/vB")
else:
    st.warning("Fee estimates are temporarily unavailable.")

st.header("Mining Difficulty")

if isinstance(difficulty, dict):
    d1, d2 = st.columns(2)

    with d1:
        change = difficulty.get("difficultyChange")

        change_text = (
            f"{change:.2f}%"
            if isinstance(change, (int, float))
            else "Unavailable"
        )

        st.metric("Difficulty Adjustment", change_text)

    with d2:
        st.metric(
            "Blocks Until Adjustment",
            number(difficulty.get("remainingBlocks")),
        )

    progress = difficulty.get("progressPercent")

    if isinstance(progress, (int, float)):
        st.progress(max(0.0, min(1.0, progress / 100)))
        st.caption(f"Adjustment progress: {progress:.2f}%")
else:
    st.info("Mining difficulty data is temporarily unavailable.")

hashrate_data = network.get("hashrate")

if isinstance(hashrate_data, dict):
    current_hashrate = hashrate_data.get("currentHashrate")

    if isinstance(current_hashrate, (int, float)):
        st.metric(
            "Estimated Network Hashrate",
            f"{current_hashrate / 1e18:.2f} EH/s",
        )

st.header("Recent Bitcoin Blocks")

if isinstance(blocks, list) and blocks:
    for block in blocks[:5]:
        if not isinstance(block, dict):
            continue

        block_hash = block.get("id")
        height = block.get("height")

        with st.expander(f"Block {number(height)}"):
            b1, b2 = st.columns(2)

            with b1:
                st.write("**Transactions:**", number(block.get("tx_count")))
                st.write("**Timestamp:**", time_utc(block.get("timestamp")))

            with b2:
                st.write("**Block size:**", number(block.get("size")))

                if block_hash:
                    st.link_button(
                        "View Block",
                        block_link(block_hash),
                    )
else:
    st.info("Recent block information is temporarily unavailable.")

st.header("Bitcoin Wallet Inspector")

wallet_address = st.text_input(
    "Bitcoin address",
    value=WALLET,
    help="Enter a public Bitcoin address to inspect its public blockchain data.",
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

            pending_balance = (
                mempool_stats.get("funded_txo_sum", 0)
                - mempool_stats.get("spent_txo_sum", 0)
            )

            w1, w2, w3 = st.columns(3)

            with w1:
                st.metric(
                    "Confirmed Balance",
                    f"{btc(confirmed_balance)} BTC",
                )

            with w2:
                st.metric(
                    "Mempool Balance Change",
                    f"{btc(pending_balance)} BTC",
                )

            with w3:
                st.metric(
                    "Confirmed Transactions",
                    number(chain.get("tx_count")),
                )

            st.markdown(
                f"[Open address in Bitcoin explorer]"
                f"({address_link(wallet_address.strip())})"
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
                        f"- [{txid[:24]}...]({transaction_link(txid)})"
                        f" — {time_utc(status.get('block_time'))}"
                    )
            else:
                st.info("No recent wallet transactions were returned.")
        else:
            st.error(
                "Wallet data could not be retrieved. Check the address "
                "and try again."
            )

st.header("Large Bitcoin Output Research")

st.write(
    "Searches a limited sample of recent confirmed blocks for outputs "
    "meeting your chosen BTC threshold. This is not a complete blockchain scan."
)

if st.button("Find Large Outputs", use_container_width=True):
    with st.spinner("Retrieving a sample of recent transactions..."):
        recent_transactions = get_recent_transactions()

    large_outputs = []

    for tx in recent_transactions:
        txid = tx.get("txid")

        if not txid:
            continue

        status = tx.get("status", {})

        if not isinstance(status, dict):
            status = {}

        for output_index, output in enumerate(tx.get("vout", [])):
            if not isinstance(output, dict):
                continue

            value = output.get("value")

            if not isinstance(value, int):
                continue

            value_btc = value / SATOSHIS_PER_BTC

            if value_btc < min_btc:
                continue

            large_outputs.append({
                "BTC": value_btc,
                "Address": output.get(
                    "scriptpubkey_address",
                    "Unavailable",
                ),
                "Transaction ID": txid,
                "Output index": output_index,
                "Confirmed": bool(status.get("confirmed")),
                "Block time": time_utc(status.get("block_time")),
            })

    if large_outputs:
        large_outputs.sort(
            key=lambda item: item["BTC"],
            reverse=True,
        )

        st.dataframe(
            pd.DataFrame(large_outputs),
            use_container_width=True,
            hide_index=True,
        )

        st.caption(
            "An output found in this sample may already have been spent. "
            "Verify individual transactions and outputs before drawing conclusions."
        )
    else:
        st.info(
            "No outputs meeting your threshold were found in the retrieved sample."
        )

st.header("Dormant Whale Scanner")

st.warning(
    "This scanner examines a
