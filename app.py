import json
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone

import streamlit as st

st.set_page_config(
    page_title="Dormant Whale Radar",
    page_icon="🐋",
    layout="wide",
)

API = "https://mempool.space/api"
WALLET = "18t9FDLShbkgXZfiaFzSuqFCBgxTitL9aC"


def get_json(url, timeout=12):
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
def load_network():
    return {
        "blocks": get_json(f"{API}/blocks"),
        "mempool": get_json(f"{API}/mempool"),
        "fees": get_json(f"{API}/v1/fees/recommended"),
    }


@st.cache_data(ttl=60)
def load_price():
    url = (
        "https://api.coingecko.com/api/v3/coins/bitcoin/"
        "market_chart?vs_currency=usd&days=1"
    )
    return get_json(url)


@st.cache_data(ttl=30)
def load_address(address):
    encoded = urllib.parse.quote(address, safe="")
    return {
        "info": get_json(f"{API}/address/{encoded}"),
        "history": get_json(f"{API}/address/{encoded}/txs"),
    }


def fmt(value):
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return "Unavailable"


def btc_value(satoshis):
    try:
        return f"{int(satoshis) / 100_000_000:.8f} BTC"
    except (ValueError, TypeError):
        return "Unavailable"


def utc_time(timestamp):
    try:
        return datetime.fromtimestamp(
            int(timestamp), timezone.utc
        ).strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, TypeError, OSError):
        return "Unavailable"


st.markdown(
    """
    <style>
    .stApp {
        background: #07111f;
        color: #e6f1ff;
    }
    [data-testid="stSidebar"] {
        background: #0b1728;
    }
    .hero {
        padding: 25px;
        border-radius: 15px;
        border: 1px solid #1e4564;
        background: linear-gradient(130deg, #102b44, #07111f);
        margin-bottom: 20px;
    }
    .hero h1 {
        color: #61e6ff;
    }
    div[data-testid="stMetric"] {
        background: #0c1b2d;
        border: 1px solid #1b3853;
        padding: 14px;
        border-radius: 12px;
    }
    h2, h3 {
        color: #61e6ff;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
        <h1>🐋 Dormant Whale Radar</h1>
        <p>Bitcoin on-chain monitoring and blockchain analytics terminal.</p>
        <p>Live network data • Wallet inspection • Whale research</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Radar Controls")

    dormancy_years = st.selectbox(
        "Dormancy threshold",
        [1, 2, 3, 5, 7, 10, 15, 20],
        index=3,
        format_func=lambda n: f"{n} years",
    )

    minimum_btc = st.number_input(
        "Minimum BTC amount",
        min_value=0.00000001,
        value=10.0,
        step=1.0,
        format="%.8f",
    )

    refresh_seconds = st.selectbox(
        "Refresh interval",
        [30, 60, 120, 300],
        index=1,
        format_func=lambda n: f"{n} seconds",
    )

    auto_refresh = st.checkbox("Enable automatic refresh", value=False)

    if st.button("Refresh now", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.caption("Times shown in UTC.")
    st.caption("Public blockchain data only.")

network = load_network()
blocks = network.get("blocks")
mempool = network.get("mempool")
fees = network.get("fees")

latest = blocks[0] if isinstance(blocks, list) and blocks else {}

st.subheader("Live Bitcoin Network")

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Block Height", fmt(latest.get("height")))

with c2:
    st.metric(
        "Unconfirmed Transactions",
        fmt(mempool.get("count") if isinstance(mempool, dict) else None),
    )

with c3:
    if isinstance(mempool, dict):
        size = mempool.get("vsize")
        size_label = (
            f"{size / 1_000_000:.2f} MB"
            if isinstance(size, (int, float))
            else "Unavailable"
        )
    else:
        size_label = "Unavailable"
    st.metric("Mempool Size", size_label)

with c4:
    st.metric(
        "Latest Block Time",
        utc_time(latest.get("timestamp")),
    )

st.subheader("Bitcoin Price")

price_data = load_price()

if isinstance(price_data, dict) and price_data.get("prices"):
    prices = price_data["prices"]
    chart_rows = [
        {
            "Time": datetime.fromtimestamp(
                item[0] / 1000, timezone.utc
            ),
            "Price (USD)": item[1],
        }
        for item in prices
        if isinstance(item, list) and len(item) >= 2
    ]

    if chart_rows:
        st.line_chart(
            chart_rows,
            x="Time",
            y="Price (USD)",
        )
        latest_price = chart_rows[-1]["Price (USD)"]
        previous_price = chart_rows[-2]["Price (USD)"] if len(chart_rows) > 1 else latest_price

        delta = latest_price - previous_price

        st.metric(
            "Latest available BTC price",
            f"${latest_price:,.2f}",
            delta=f"${delta:,.2f} since previous chart point",
        )
        st.caption(
            "Market data is supplied by CoinGecko and may be delayed. "
            "The chart shows reported historical points, not guaranteed tick-by-tick prices."
        )
    else:
        st.warning("Price data was returned in an unexpected format.")
else:
    st.warning(
        "Bitcoin price data is temporarily unavailable. "
        "The network dashboard can still operate."
    )

st.subheader("Transaction Fee Estimates")

if isinstance(fees, dict):
    a, b, c = st.columns(3)

    with a:
        st.metric("High Priority", f"{fmt(fees.get('fastestFee'))} sat/vB")

    with b:
        st.metric("Medium Priority", f"{fmt(fees.get('halfHourFee'))} sat/vB")

    with c:
        st.metric("Low Priority", f"{fmt(fees.get('hourFee'))} sat/vB")
else:
    st.warning("Transaction fee estimates are temporarily unavailable.")

st.subheader("Recent Confirmed Blocks")

if isinstance(blocks, list) and blocks:
    for block in blocks[:8]:
        block_hash = block.get("id", "")
        height = block.get("height")
        tx_count = block.get("tx_count")

        st.markdown(
            f"**Block {fmt(height)}** · "
            f"Transactions: {fmt(tx_count)} · "
            f"{utc_time(block.get('timestamp'))}"
        )

        if block_hash:
            st.markdown(
                f"[Inspect block on mempool.space]"
                f"(https://mempool.space/block/{block_hash})"
            )

        st.divider()
else:
    st.warning("Block information is currently unavailable.")

st.subheader("Bitcoin Wallet Scanner")

wallet = st.text_input(
    "Bitcoin address to inspect",
    value=WALLET,
    help="Enter a public Bitcoin address. Never enter a private key or recovery phrase.",
)

if st.button("Scan wallet", type="primary"):
    wallet = wallet.strip()

    if not wallet or len(wallet) > 100:
        st.error("Enter a valid-looking public Bitcoin address.")
    else:
        with st.spinner("Looking up address on the Bitcoin network..."):
            result = load_address(wallet)

        info = result.get("info")
        history = result.get("history")

        if isinstance(info, dict):
            chain = info.get("chain_stats", {})
            mempool_stats = info.get("mempool_stats", {})

            confirmed_received = chain.get("funded_txo_sum", 0)
            confirmed_sent = chain.get("spent_txo_sum", 0)
            pending_received = mempool_stats.get("funded_txo_sum", 0)
            pending_sent = mempool_stats.get("spent_txo_sum", 0)

            confirmed_balance = confirmed_received - confirmed_sent
            pending_balance = pending_received - pending_sent

            w1, w2, w3 = st.columns(3)

            with w1:
                st.metric("Confirmed Balance", btc_value(confirmed_balance))

            with w2:
                st.metric("Pending Balance Change", btc_value(pending_balance))

            with w3:
                st.metric(
                    "Confirmed Transactions",
                    fmt(chain.get("tx_count")),
                )

            st.markdown(
                f"[Open this address in the blockchain explorer]"
                f"(https://mempool.space/address/{urllib.parse.quote(wallet, safe='')})"
            )

            st.caption(
                "A balance lookup does not establish who owns an address "
                "or prove that its owner is dormant."
            )

            st.markdown("#### Recent Address Transactions")

            if isinstance(history, list) and history:
                for tx in history[:10]:
                    txid = tx.get("txid", "")
                    status = tx.get("status", {})
                    confirmed = status.get("confirmed", False)

                    if confirmed:
                        block_time = utc_time(status.get("block_time"))
                        state = f"Confirmed · {block_time}"
                    else:
                        state = "Unconfirmed"

                    st.markdown(
                        f"**{state}**  \n"
                        f"Transaction: `{txid}`"
                    )

                    if txid:
                        st.markdown(
                            f"[View transaction]"
                            f"(https://mempool.space/tx/{txid})"
                        )

                    st.divider()
            elif history == []:
                st.info("No recent transactions were returned for this address.")
            else:
                st.warning("Transaction history could not be loaded.")
        else:
            st.error(
                "The address lookup failed. Check the address and try again. "
                "The data provider may also be temporarily unavailable."
            )

st.subheader("Dormant Whale Research")

st.info(
    f"""
    Selected minimum balance: **{minimum_btc:,.8f} BTC**  
    Selected dormancy threshold: **{dormancy_years} years**

    The wallet scanner above performs address lookups. It does not yet
    conduct a global historical search for all Bitcoin outputs that have
    remained unspent for the selected number of years.

    A genuine global scanner requires a suitable historical blockchain
    index or additional Bitcoin infrastructure. No dormant-whale results
    are fabricated by this dashboard.
    """
)

st.subheader("VIP Access")

st.warning(
    "Payment verification and automatic VIP activation are not enabled "
    "in this version. Do not send Bitcoin expecting automatic access "
    "until a complete payment-verification system has been tested."
)

st.caption(
    f"Last page render: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
)

st.caption("Dormant Whale Radar | Bitcoin On-Chain Analytics")

if auto_refresh:
    time.sleep(refresh_seconds)
    st.rerun()
