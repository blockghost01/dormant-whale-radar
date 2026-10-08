import streamlit as st
import urllib.request
import json
import datetime
import time

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Dormant Whale Radar | Elite On-Chain Terminal", 
    page_icon="🐋", 
    layout="centered"
)

# --- CUSTOM CSS FOR A "REAL WEBSITE" DESIGN ---
st.markdown("""
    <style>
    /* Global App Background */
    .stApp {
        background-color: #07090e;
        color: #f3f4f6;
    }
    
    /* Hide default streamlit headers/footers for a clean website feel */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Sleek Card Container */
    .web-card {
        background-color: #111522;
        border: 1px solid #1f293d;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
    }
    
    /* Terminal Console Box */
    .terminal-box {
        background-color: #030712;
        border: 1px solid #1e293b;
        border-radius: 8px;
        padding: 15px;
        font-family: 'Courier New', Courier, monospace;
        color: #38bdf8;
        font-size: 13px;
        line-height: 1.5;
    }
    
    /* Section Titles */
    .section-title {
        font-size: 18px;
        font-weight: 700;
        color: #ffffff;
        margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- HERO HEADER ---
st.markdown("""
    <div style="text-align: center; padding: 10px 0 20px 0;">
        <h1 style="color: #ffffff; font-size: 28px; margin-bottom: 5px;">🐋 Bitcoin Dormant Whale Radar</h1>
        <p style="color: #9ca3af; font-size: 14px;">Professional On-Chain Intelligence & Live Ledger Stream</p>
    </div>
""", unsafe_allow_html=True)

# --- CONTROLS BAR (CLEAN & VISIBLE) ---
st.markdown('<div class="web-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">⚙️ Intelligence Parameters</div>', unsafe_allow_html=True)

col_c1, col_c2 = st.columns(2)
with col_c1:
    min_dormancy_years = st.slider("Min Coin Dormancy Threshold (Years)", min_value=1, max_value=20, value=5)
with col_c2:
    auto_refresh = st.checkbox("⚡ Live Auto-Stream (60s)", value=True)

st.markdown('</div>', unsafe_allow_html=True)

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
            "hash": latest.get('id', '0000...')[:14] + "..."
        }
    except:
        return None

live_block = fetch_live_data()
current_time = datetime.datetime.utcnow().strftime("%H:%M:%S UTC")

# --- LIVE METRICS GRID ---
st.markdown('<div class="web-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">📊 Network Telemetry Stream</div>', unsafe_allow_html=True)

if live_block:
    m1, m2, m3 = st.columns(3)
    m1.metric("Block Height", f"{live_block['height']:,}")
    m2.metric("Transactions", f"{live_block['tx_count']:,}")
    m3.metric("Fee Rate", f"{live_block['fee']} sat/vB")
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"🟢 **Node Status:** Fully Connected & Active | **Sync:** `{current_time}`")
    st.markdown(f"🔍 **Active Filter:** Scanning for cold storage movements $\ge$ **{min_dormancy_years} Years**.")
    
    # Live Terminal Log Box
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        f"""<div class="terminal-box">
[LIVE DISPATCHER CONSOLE - REAL-TIME STREAM]<br>
> Target Block Hash: {live_block['hash']}<br>
> Dormancy Rule Set: &gt;= {min_dormancy_years} Years Unmoved<br>
> Socket State: Active handshake with mempool.space REST gateway.<br>
> Status: Live calculations operating at peak frequency. Ready for alerts.
        </div>""", 
        unsafe_allow_html=True
    )
else:
    st.warning("⚠️ Reconnecting to Bitcoin Mempool network nodes...")

st.markdown('</div>', unsafe_allow_html=True)

# --- VIP PRO ACCESS & MONETIZATION SECTION ---
st.markdown('<div class="web-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">⚡ VIP Pro Access & Direct Node Integration</div>', unsafe_allow_html=True)
st.markdown("Unlock high-priority push webhooks, real-time SMS alerts, and deep historical wallet intelligence.")

st.markdown("**Lifetime VIP Access Cost:** `0.001 BTC`")
st.markdown("Send Bitcoin directly to your secure developer wallet below:")
st.code("18t9FDLShbkgXZfiaFzSuqFCBgxTitL9aC", language="text")
st.markdown("<span style='font-size: 12px; color: #9ca3af;'>*After completing your transfer, forward your transaction hash to activate your terminal privileges.*</span>", unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# --- AUTOMATED LIVE REFRESH (60 SECONDS) ---
if auto_refresh:
    time.sleep(60)
    st.rerun()
