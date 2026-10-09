import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

import streamlit as st

st.set_page_config(
    page_title="Dormant Whale Radar",
    page_icon="🐋",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE = "https://mempool.space/api"


st.markdown(
    """
    <style>
    .stApp {
        background-color: #07111f;
        color: #e8f0ff;
    }
    [data-testid="stSidebar"] {
        background-color: #0b1728;
    }
    .hero {
        padding: 24px;
        border: 1px solid #1d4260;
        border-radius: 16px;
        background: linear-gradient(135deg, #10243b, #07111f);
        margin-bottom: 20px;
    }
    .hero h1 {
        color: #64e6ff;
        margin-bottom: 8px;
    }
    .hero p {
        color: #b7c9df;
    }
    div[data-testid="stMetric"] {
        background: #0c1b2d;
        border: 1px solid #1b3853;
        padding: 15px;
        border-radius: 12px;
    }
    h2, h3 {
        color: #64e6ff;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_json(endpoint):
    """Fetch public Bitcoin network data safely."""
    url = API_BASE + endpoint
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "DormantWhaleRadar/1.0"},
    )

    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        ValueError,
    ):
        return None


@st.cache_data(ttl=60)
def get_network_data():
    return {
        "blocks": get_json("/blocks"),
        "mempool": get_json("/mempool"),
        "fees": get_json("/v1/fees/recommended"),
    }


def number(value):
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return "Unavailable"


def btc(value):
    try:
        return f"{float(value):,.2f} BTC"
    except (ValueError, TypeError):
        return "Unavailable"


st.markdown(
    """
    <div class="hero">
        <h1>🐋 Bitcoin Dormant Whale Radar</h1>
        <p>
            An on-chain dashboard for monitoring Bitcoin network activity,
            block production, mempool conditions, and transaction fees.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


with st.sidebar:
    st.header("Radar Settings")

    dormancy_years = st.slider(
        "Dormancy threshold (years)",
        min_value=1,
        max_value=20,
        value=5,
    )

    minimum_btc = st.number_input(
        "Minimum whale balance (BTC)",
        min_value=0.1,
        max_value=1000000.0,
        value=10.0,
        step=1.0,
    )

    auto_refresh = st.checkbox(
        "Auto-refresh dashboard",
        value=False,
    )

    refresh_seconds = st.selectbox(
        "Refresh interval",
        options=[30, 60, 120, 300],
        index=1,
        format_func=lambda seconds: f"{seconds} seconds",
    )

    if st.button("Refresh data now", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.caption("Data source: mempool.space public API")
    st.caption("All times are displayed in UTC.")


with st.spinner("Loading live Bitcoin network data..."):
    data = get_network_data()

blocks = data.get("blocks")
mempool = data.get("mempool")
fees = data.get("fees")

latest_block = blocks[0] if isinstance(blocks, list) and blocks else None

st.subheader("Network Overview")

if latest_block:
    block_height = latest_block.get("height", "Unavailable")
    block_time = latest_block.get("timestamp")

    if block_time:
        last_block_time = datetime.fromtimestamp(
            block_time, tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S UTC")
    else:
        last_block_time = "Unavailable"
else:
    block_height = "Unavailable"
    last_block_time = "Unavailable"


if isinstance(mempool, dict):
    mempool_count = mempool.get("count")
    mempool_size = mempool.get("vsize")
    mempool_fees = mempool.get("total_fee")
else:
    mempool_count = None
    mempool_size = None
    mempool_fees = None


col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Latest Block Height", number(block_height))

with col2:
    st.metric("Unconfirmed Transactions", number(mempool_count))

with col3:
    if isinstance(mempool_size, (int, float)):
        st.metric("Mempool Size", f"{mempool_size / 1_000_000:.2f} MB")
    else:
        st.metric("Mempool Size", "Unavailable")


st.caption(f"Latest block time: {last_block_time}")

st.subheader("Transaction Fee Estimates")

if isinstance(fees, dict):
    fee1, fee2, fee3 = st.columns(3)

    with fee1:
        st.metric(
            "High Priority",
            f"{number(fees.get('fastestFee'))} sat/vB",
        )

    with fee2:
        st.metric(
            "Medium Priority",
            f"{number(fees.get('halfHourFee'))} sat/vB",
        )

    with fee3:
        st.metric(
            "Low Priority",
            f"{number(fees.get('hourFee'))} sat/vB",
        )
else:
    st.warning(
        "Fee estimates could not be loaded. "
        "Please refresh the dashboard and try again."
    )


st.subheader("Recent Confirmed Blocks")

if isinstance(blocks, list) and blocks:
    for block in blocks[:8]:
        height = block.get("height", "Unknown")
        tx_count = block.get("tx_count", "Unavailable")
        block_hash = block.get("id", "")
        timestamp = block.get("timestamp")

        if timestamp:
            block_datetime = datetime.fromtimestamp(
                timestamp, tz=timezone.utc
            ).strftime("%Y-%m-%d %H:%M UTC")
        else:
            block_datetime = "Time unavailable"

        st.markdown(
            f"**Block {number(height)}** · "
            f"Transactions: {number(tx_count)} · "
            f"{block_datetime}"
        )

        if block_hash:
            st.markdown(
                f"[View block on mempool.space]"
                f"(https://mempool.space/block/{block_hash})"
            )

        st.divider()
else:
    st.warning(
        "Block data is temporarily unavailable. "
        "Check your internet connection and refresh."
    )


st.subheader("Dormant Whale Search")

st.info(
    f"""
    Your selected search settings are:

    - Dormancy threshold: **{dormancy_years} years**
    - Minimum Bitcoin balance: **{minimum_btc:,.2f} BTC**

    **Important:** These settings are ready, but this version does not
    yet scan historical Bitcoin outputs to identify wallets that have
    remained inactive for the selected period. It does not currently
    identify or verify dormant whales.
    """
)


st.subheader("VIP Access")

st.warning(
    "VIP payments and account activation are not implemented in this "
    "version. Do not send Bitcoin expecting automatic access or a "
    "service that has not been verified."
)


st.caption(
    "Dormant Whale Radar · Live public network data where available. "
    "Network data may occasionally be unavailable."
)


if auto_refresh:
    time.sleep(refresh_seconds)
    st.rerun()
