import streamlit as st
import requests
import time
import html
from datetime import datetime, timezone

============================================================

PAGE CONFIGURATION

============================================================

st.set_page_config(
page_title="Dormant Whale Radar | Bitcoin Intelligence",
page_icon="🐋",
layout="wide",
initial_sidebar_state="collapsed",
)

============================================================

CONFIGURATION

============================================================

API_BASE = "https://mempool.space/api"
EXPLORER_BASE = "https://mempool.space"

Public receiving address displayed for the proposed VIP feature.

Verify ownership and payment-processing arrangements before use.

BTC_WALLET = "18t9FDLShbkgXZfiaFzSuqFCBgxTitL9aC"

============================================================

CUSTOM DESIGN

============================================================

st.markdown(
"""
<style>
.stApp {
background: #07090e;
color: #f3f4f6;
}

#MainMenu, footer, header {
    visibility: hidden;
}

.block-container {
    max-width: 1250px;
    padding-top: 1.5rem;
    padding-bottom: 3rem;
}

.hero {
    text-align: center;
    padding: 25px 10px 30px 10px;
    background: linear-gradient(145deg, #101827, #07090e);
    border: 1px solid #1f293d;
    border-radius: 18px;
    margin-bottom: 24px;
}

.hero h1 {
    color: #ffffff;
    font-size: clamp(25px, 4vw, 38px);
    margin-bottom: 8px;
}

.hero p {
    color: #9ca3af;
    font-size: 14px;
}

.web-card {
    background: #111522;
    border: 1px solid #1f293d;
    border-radius: 14px;
    padding: 20px;
    margin-bottom: 20px;
}

.section-title {
    font-size: 19px;
    font-weight: 700;
    color: #ffffff;
    margin-bottom: 12px;
}

.terminal-box {
    background: #030712;
    border: 1px solid #1e293b;
    border-radius: 9px;
    padding: 16px;
    color: #38bdf8;
    font-family: monospace;
    font-size: 13px;
    line-height: 1.9;
    overflow-wrap: anywhere;
}

.muted {
    color: #9ca3af;
    font-size: 13px;
    line-height: 1.7;
}

.blue {
    color: #38bdf8;
}

.status {
    color: #22c55e;
    font-weight: 700;
}

.warning-box {
    padding: 14px;
    border: 1px solid #854d0e;
    background: #21180a;
    border-radius: 9px;
    color: #fde68a;
    line-height: 1.7;
    font-size: 13px;
}

.footer-note {
    text-align: center;
    color: #6b7280;
    font-size: 12px;
    padding: 20px;
}

div.stButton > button {
    border-radius: 8px;
    min-height: 42px;
    font-weight: 600;
}
</style>
""",
unsafe_allow_html=True,

)

============================================================

LIVE BITCOIN API

============================================================

@st.cache_data(ttl=30, show_spinner=False)
def fetch_latest_block():
try:
response = requests.get(
f"{API_BASE}/blocks",
timeout=12,
)
response.raise_for_status()

    blocks = response.json()

    if not isinstance(blocks, list) or not blocks:
        return None

    block = blocks[0]

    return {
        "height": block.get("height"),
        "hash": block.get("id"),
        "timestamp": block.get("timestamp"),
        "tx_count": block.get("tx_count"),
    }

except (requests.RequestException, ValueError, TypeError):
    return None

@st.cache_data(ttl=30, show_spinner=False)
def fetch_mempool():
try:
response = requests.get(
f"{API_BASE}/mempool",
timeout=12,
)
response.raise_for_status()

    data = response.json()

    return {
        "count": data.get("count"),
        "vsize": data.get("vsize"),
        "total_fee": data.get("total_fee"),
    }

except (requests.RequestException, ValueError, TypeError):
    return None

@st.cache_data(ttl=30, show_spinner=False)
def fetch_fee_estimates():
try:
response = requests.get(
f"{API_BASE}/v1/fees/recommended",
timeout=12,
)
response.raise_for_status()

    data = response.json()

    return data

except (requests.RequestException, ValueError, TypeError):
    return None

@st.cache_data(ttl=60, show_spinner=False)
def fetch_recent_blocks():
try:
response = requests.get(
f"{API_BASE}/v1/blocks",
timeout=12,
)
response.raise_for_status()

    data = response.json()

    return data if isinstance(data, list) else []

except (requests.RequestException, ValueError, TypeError):
    return []

============================================================

HELPERS

============================================================

def format_number(value):
if isinstance(value, (int, float)):
return f"{value:,}"
return "N/A"

def format_btc_sats(value):
if isinstance(value, (int, float)):
return f"{value:,} sats"
return "N/A"

def format_utc(timestamp):
if not isinstance(timestamp, (int, float)):
return "N/A"

try:
    dt = datetime.fromtimestamp(
        timestamp,
        tz=timezone.utc,
    )
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
except (ValueError, OSError, OverflowError):
    return "N/A"

============================================================

HERO HEADER

============================================================

st.markdown(
"""
<div class="hero">
<h1>🐋 Bitcoin Dormant Whale Radar</h1>
<p>ON-CHAIN INTELLIGENCE • NETWORK TELEMETRY • BLOCKCHAIN RESEARCH</p>
<p>Monitor Bitcoin network activity through public blockchain data.</p>
</div>
""",
unsafe_allow_html=True,
)

============================================================

SIDEBAR SETTINGS

============================================================

with st.sidebar:
st.title("⚙️ Radar Settings")

min_dormancy_years = st.slider(
    "Minimum output age (years)",
    min_value=1,
    max_value=20,
    value=5,
)

min_whale_btc = st.number_input(
    "Minimum output value (BTC)",
    min_value=0.0,
    max_value=1000000.0,
    value=10.0,
    step=1.0,
)

auto_refresh = st.checkbox(
    "Automatic refresh",
    value=False,
)

refresh_seconds = st.selectbox(
    "Refresh interval",
    [30, 60, 120, 300],
    index=1,
    format_func=lambda x: f"{x} seconds",
    disabled=not auto_refresh,
)

st.markdown("---")
st.caption(
    "The age and value settings are research filters. "
    "Historical UTXO scanning is not yet connected."
)

============================================================

FETCH LIVE DATA

============================================================

with st.spinner("Connecting to the public Bitcoin data API..."):
block = fetch_latest_block()
mempool = fetch_mempool()
fees = fetch_fee_estimates()
recent_blocks = fetch_recent_blocks()

checked_at = datetime.now(timezone.utc).strftime(
"%Y-%m-%d %H:%M:%S UTC"
)

============================================================

NETWORK TELEMETRY

============================================================

st.markdown(
'<div class="section-title">📊 Live Network Telemetry</div>',
unsafe_allow_html=True,
)

if block:
height = block.get("height")
tx_count = block.get("tx_count")

c1, c2, c3 = st.columns(3)

c1.metric(
    "Latest Block Height",
    format_number(height),
)

c2.metric(
    "Latest Block Transactions",
    format_number(tx_count),
)

mempool_count = mempool.get("count") if mempool else None

c3.metric(
    "Unconfirmed Transactions",
    format_number(mempool_count),
)

st.success(f"Bitcoin data endpoint responding • Checked {checked_at}")

else:
st.error(
"The Bitcoin data endpoint could not be reached. "
"Check your internet connection or try refreshing."
)

st.info(
    "The rest of the application remains available, "
    "but live metrics cannot be displayed until the API responds."
)

st.markdown("---")

============================================================

NETWORK FEES AND CONGESTION

============================================================

st.markdown(
'<div class="section-title">⚡ Network Fees & Congestion</div>',
unsafe_allow_html=True,
)

fee_col1, fee_col2, fee_col3 = st.columns(3)

if fees:
fee_col1.metric(
"High Priority Fee",
f"{fees.get('fastestFee', 'N/A')} sat/vB",
)

fee_col2.metric(
    "Medium Priority Fee",
    f"{fees.get('halfHourFee', 'N/A')} sat/vB",
)

fee_col3.metric(
    "Low Priority Fee",
    f"{fees.get('hourFee', 'N/A')} sat/vB",
)

else:
fee_col1.metric("High Priority Fee", "N/A")
fee_col2.metric("Medium Priority Fee", "N/A")
fee_col3.metric("Low Priority Fee", "N/A")

if mempool:
count = mempool.get("count")
vsize = mempool.get("vsize")

st.markdown(
    f"""
    <div class="terminal-box">
    [MEMPOOL NETWORK MONITOR]<br>
    API STATUS: {"RESPONDING" if block else "PARTIAL / UNAVAILABLE"}<br>
    UNCONFIRMED TRANSACTIONS: {format_number(count)}<br>
    MEMPOOL VIRTUAL SIZE: {format_number(vsize)} vB<br>
    LAST CHECK: {html.escape(checked_at)}
    </div>
    """,
    unsafe_allow_html=True,
)

if isinstance(count, int):
    congestion = min(count / 100000, 1.0)

    st.caption(
        "Relative transaction-count indicator "
        "(not a direct measurement of network capacity)."
    )

    st.progress(congestion)

else:
st.warning("Current mempool statistics are unavailable.")

============================================================

DORMANT WHALE RESEARCH

============================================================

st.markdown("---")

st.markdown(
'<div class="section-title">🐋 Dormant Whale Research Terminal</div>',
unsafe_allow_html=True,
)

st.markdown(
f"""
<div class="web-card">
<div class="muted">CURRENT RESEARCH PARAMETERS</div>
<h3 style="color:#38bdf8">
{min_dormancy_years}-Year Dormancy Threshold
</h3>
<p class="muted">
Minimum output value: {min_whale_btc:,.2f} BTC
</p>
<p class="muted">
Research mode: Historical Bitcoin output analysis
</p>
</div>
""",
unsafe_allow_html=True,
)

st.markdown(
"""
<div class="warning-box">
SCANNER STATUS: HISTORICAL OUTPUT SCANNING NOT YET IMPLEMENTED.<br><br>
This dashboard currently retrieves live network statistics.
It does not yet scan all historical Bitcoin outputs or verify
which older outputs remain unspent. No dormant-whale detections
are claimed until that data pipeline is implemented.
</div>
""",
unsafe_allow_html=True,
)

st.markdown("")

with st.expander("What the completed whale scanner will do"):
st.markdown(
"""
1. Retrieve historical Bitcoin transaction outputs.
2. Verify their current unspent status.
3. Calculate the time elapsed since each output was created.
4. Apply the selected dormancy and BTC-value thresholds.
5. Display qualifying outputs and link to public blockchain records.

    An old output is not automatically a whale wallet. Bitcoin
    addresses, outputs, wallets, and beneficial owners are different
    concepts, and ownership cannot be reliably inferred from age alone.
    """
)

============================================================

RECENT CONFIRMED BLOCKS

============================================================

st.markdown("---")

st.markdown(
'<div class="section-title">🧱 Recent Confirmed Blocks</div>',
unsafe_allow_html=True,
)

if recent_blocks:
for item in recent_blocks[:5]:
block_hash = item.get("id")
block_height = item.get("height")
block_timestamp = item.get("timestamp")

    with st.container(border=True):
        st.markdown(
            f"**Block {format_number(block_height)}**"
        )

        st.caption(
            f"Timestamp: {format_utc(block_timestamp)}"
        )

        if block_hash:
            safe_hash = html.escape(str(block_hash))

            st.code(
                safe_hash,
                language="text",
            )

            st.markdown(
                f"[View block on Mempool.space]"
                f"({EXPLORER_BASE}/block/{safe_hash})"
            )

else:
st.info("Recent block information is temporarily unavailable.")

============================================================

VIP ACCESS INFORMATION

============================================================

st.markdown("---")

st.markdown(
'<div class="section-title">⭐ VIP Pro Access</div>',
unsafe_allow_html=True,
)

st.markdown(
"""
<div class="web-card">
<h3 style="color:#ffffff">Premium Research Access</h3>
<p class="muted">
This section is reserved for future premium features,
including historical output research, saved watchlists,
and configurable blockchain alerts.
</p>
<p class="muted">
Payment processing and account activation are not yet
implemented. Sending Bitcoin does not automatically grant
access through this dashboard.
</p>
</div>
""",
unsafe_allow_html=True,
)

with st.expander("VIP payment setup information"):
st.warning(
"Payment verification is not active. Do not send Bitcoin "
"based solely on this demonstration interface."
)

st.caption(
    "A production payment system must verify the transaction, "
    "receiving address, required amount, confirmation status, "
    "and whether the payment has already been redeemed."
)

============================================================

FOOTER

============================================================

st.markdown(
"""
<div class="footer-note">
DORMANT WHALE RADAR • BITCOIN ON-CHAIN RESEARCH<br>
Public network information provided by mempool.space.<br>
Blockchain research only. Not financial advice.
</div>
""",
unsafe_allow_html=True,
)

============================================================

AUTOMATIC REFRESH

============================================================

if auto_refresh:
time.sleep(refresh_seconds)
st.rerun()
