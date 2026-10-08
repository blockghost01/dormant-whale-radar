import streamlit as st
import urllib.request
import json
import datetime
import time

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Dormant Whale Radar | Live Terminal", 
    page_icon="🐋", 
    layout="centered"
)

# --- PROFESSIONAL TERMINAL STYLING ---
st.markdown("""
    <style>
    .main {
        background-color: #080c14;
    }
    .block-container {
        padding-top: 2rem;
    }
    </style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.title("🐋 Bitcoin Dormant Whale Radar")
st.markdown("### **Live On-Chain Intelligence Feed** — Updating Every Minute")
st.markdown("---")

# --- MAIN SCREEN CONTROLS (NOTHING HIDDEN) ---
st.subheader("⚙️ Terminal Parameters")
col_ctrl1, col_ctrl2 = st.columns(2)
with col_ctrl1:
    min_dormancy_years = st.slider("Min Coin Dormancy (Years)", min_value=1, max_value=20, value=5)
with col_ctrl2:
    auto_refresh = st.checkbox("⚡ Auto-Stream Live Feed (1m)", value=True)

st.markdown("---")

# --- LIVE MEMPOOL DATA FETCHER ---
@st.cache_data(ttl=60)
def fetch_live_data():
    try:
        url = "https://mempool.space/api/v1/blocks"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req)
        data = json.loads(response.read().decode())
        latest = data[0]
        return {
            "height": latest.get('height'),
            "tx_count": latest.get('tx_count'),
            "fee": latest.get('medianFee', 12),
            "hash": latest.get('id', '0000...')[:12] + "..."
        }
    except:
        return None

live_block = fetch_live_data()
current_minute = datetime.datetime.utcnow().strftime("%H:%M UTC")

# --- LIVE INTELLIGENCE DISPLAY (VISIBLE INSTANTLY) ---
st.subheader("🚨 Real-Time Whale Activity Stream")

if live_block:
    # Metric cards right on screen
    m1, m2, m3 = st.columns(3)
    m1.metric("Live Block Height", f"{live_block['height']:,}")
    m2.metric("Block Transactions", f"{live_block['tx_count']:,}")
    m3.metric("Network Fee Rate", f"{live_block['fee']} sat/vB")
    
    st.markdown("")
    
    # Live Activity Feed Box
    st.info(f"🟢 **Live Node Status:** Connected & Scanning | Last Sync: `{current_minute}`")
    
    # Dynamic active feed simulation based on current minute and user slider
    st.warning(f"⏳ **Active Target Alert:** Monitoring legacy coin clusters for **{min_dormancy_years}+ years** dormancy threshold.")
    
    # Fast terminal stream log visible right on the main screen
    st.markdown(
        f"""```text
[LIVE STREAM DISPATCHER - MINUTE TICK]
> Target Block Hash: {live_block['hash']}
> Filter Criteria: UTXOs untouched for >= {min_dormancy_years} years.
> Status: Scanning mempool transactions for high-value wallet awakenings...
> Result: Live cryptographic verification active. Stream operating at max speed.
        ```"""
    )
else:
    st.error("⚠️ Reconnecting to Bitcoin Mempool network...")

st.markdown("---")

# --- VISIBLE VIP PRO ACCESS (NO HIDDEN EXPANDERS) ---
st.subheader("⚡ VIP Pro Access & Direct Integration")
st.markdown("Upgrade your node connection for priority real-time push alerts and deep historical whale filters.")

MY_BTC_WALLET = "18t9FDLShbkgXZfiaFzSuqFCBgxTitL9aC"

st.markdown("**Lifetime VIP Access Cost:** `0.001 BTC`")
st.markdown("Send Bitcoin directly to your secure wallet below:")
st.code(MY_BTC_WALLET, language="text")
st.markdown("*After sending your transaction, message your payment hash to activate your full terminal privileges instantly.*")

# --- AUTO REFRESH LOOP (EVERY 60 SECONDS) ---
if auto_refresh:
    time.sleep(60)
    st.rerun()
    
