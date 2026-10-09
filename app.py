import json
import time
import urllib.request
import urllib.parse
import urllib.error
import html
import streamlit as st

st.set_page_config(
    page_title="Dormant Whale Radar",
    page_icon="🐋",
    layout="wide"
)

API = "https://mempool.space/api"

# Original wallet and notification configuration
WALLET = "18t9FDLShbkgXZfiaFzSuqFCBgxTitL9aC"
PAYMENT_EMAIL = "ayoceo938@gmail.com"
PAYMENT_AMOUNT_BTC = 0.001

def get_json(url, timeout=12):
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "DormantWhaleRadar/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception:
        return None

def get_text(url, timeout=12):
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "DormantWhaleRadar/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.read().decode("utf-8")
    except Exception:
        return None

@st.cache_data(ttl=30)
def network_data():
    return {
        "blocks": get_json(f"{API}/blocks"),
        "mempool": get_json(f"{API}/mempool"),
        "fees": get_json(f"{API}/v1/fees/recommended"),
    }

@st.cache_data(ttl=60)
def bitcoin_price():
    return get_json(
        "https://api.coingecko.com/api/v3/coins/bitcoin/"
        "market_chart?vs_currency=usd&days=1"
    )

@st.cache_data(ttl=30)
def address_data(address):
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

def btc(satoshis):
    try:
        return f"{int(satoshis) / 100_000_000:.8f} BTC"
    except (ValueError, TypeError):
        return "Unavailable"

def explorer_address(address):
    return "https://mempool.space/address/" + urllib.parse.quote(
        address, safe=""
    )

def explorer_tx(txid):
    return "https://mempool.space/tx/" + urllib.parse.quote(
        txid, safe=""
    )

# Styling
st.markdown("""
<style>
.stApp {
    background: #07111f;
    color: #e6f1ff;
}
[data-testid="stSidebar"] {
    background: #0b1728;
}
.hero {
    padding: 24px;
    border: 1px solid #1e4564;
    border-radius: 16px;
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
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
<h1>🐋 Dormant Whale Radar</h1>
<p>Bitcoin on-chain monitoring and blockchain analytics terminal.</p>
<p>Live network data · Wallet inspection · Whale research</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("Radar Settings")
    dormancy_years = st.selectbox(
        "Dormancy threshold",
        [1, 2, 3, 5, 7, 10, 15, 20],
        index=3,
        format_func=lambda n: f"{n} years"
    )
    minimum_btc = st.number_input(
        "Minimum BTC amount",
        min_value=0.00000001,
        value=10.0,
        step=1.0
    )
    auto_refresh = st.checkbox("Auto-refresh", value=False)
    refresh_seconds = st.selectbox(
        "Refresh interval",
        [30, 60, 120, 300],
        index=1
    )
    if st.button("Refresh data now"):
        st.cache_data.clear()
        st.rerun()

# Network dashboard
st.header("Live Bitcoin Network")

data = network_data()
blocks = data["blocks"]
mempool = data["mempool"]
fees = data["fees"]

latest = blocks[0] if isinstance(blocks, list) and blocks else {}

a, b, c = st.columns(3)

with a:
    st.metric("Latest Block", fmt(latest.get("height")))

with b:
    st.metric(
        "Unconfirmed Transactions",
        fmt(mempool.get("count") if isinstance(mempool, dict) else None)
    )

with c:
    size = mempool.get("vsize") if isinstance(mempool, dict) else None
    st.metric(
        "Mempool Size",
        f"{size / 1_000_000:.2f} MB"
        if isinstance(size, (int, float))
        else "Unavailable"
    )

st.caption(
    "Latest block timestamp: "
    + (
        time.strftime(
            "%Y-%m-%d %H:%M:%S UTC",
            time.gmtime(latest["timestamp"])
        )
        if isinstance(latest.get("timestamp"), (int, float))
        else "Unavailable"
    )
)

# Bitcoin market chart
st.header("Bitcoin Market Price")

market = bitcoin_price()

if isinstance(market, dict) and market.get("prices"):
    import pandas as pd

    rows = market["prices"]
    frame = pd.DataFrame(rows, columns=["Timestamp", "Price USD"])
    frame["Time"] = pd.to_datetime(frame["Timestamp"], unit="ms", utc=True)
    frame = frame[["Time", "Price USD"]]

    st.line_chart(frame, x="Time", y="Price USD")

    current_price = float(frame["Price USD"].iloc[-1])
    previous_price = (
        float(frame["Price USD"].iloc[-2])
        if len(frame) > 1 else current_price
    )

    st.metric(
        "Latest Available BTC Price",
        f"${current_price:,.2f}",
        f"{current_price - previous_price:+,.2f} since previous point"
    )
    st.caption("Source: CoinGecko. Prices may be delayed.")
else:
    st.warning("Market-price service is temporarily unavailable.")

# Transaction fees
st.header("Transaction Fee Estimates")

if isinstance(fees, dict):
    x, y, z = st.columns(3)
    with x:
        st.metric("High Priority", f"{fmt(fees.get('fastestFee'))} sat/vB")
    with y:
        st.metric("Medium Priority", f"{fmt(fees.get('halfHourFee'))} sat/vB")
    with z:
        st.metric("Low Priority", f"{fmt(fees.get('hourFee'))} sat/vB")
else:
    st.warning("Fee estimates are unavailable.")

# Blocks
st.header("Recent Confirmed Blocks")

if isinstance(blocks, list) and blocks:
    for block in blocks[:6]:
        block_hash = block.get("id", "")
        st.markdown(
            f"**Block {fmt(block.get('height'))}** · "
            f"Transactions: {fmt(block.get('tx_count'))}"
        )
        if block_hash:
            st.markdown(
                f"[Inspect block](https://mempool.space/block/{block_hash})"
            )
        st.divider()
else:
    st.warning("Block data is unavailable.")

# Wallet scanner
st.header("Bitcoin Wallet Scanner")

address = st.text_input("Public Bitcoin address", value=WALLET)

if st.button("Scan wallet", type="primary"):
    address = address.strip()

    if not address or len(address) > 100:
        st.error("Enter a valid public Bitcoin address.")
    else:
        result = address_data(address)
        info = result.get("info")
        history = result.get("history")

        if isinstance(info, dict):
            chain = info.get("chain_stats", {})
            pending = info.get("mempool_stats", {})

            balance = (
                chain.get("funded_txo_sum", 0)
                - chain.get("spent_txo_sum", 0)
            )
            pending_balance = (
                pending.get("funded_txo_sum", 0)
                - pending.get("spent_txo_sum", 0)
            )

            x, y, z = st.columns(3)
            x.metric("Confirmed Balance", btc(balance))
            y.metric("Pending Balance Change", btc(pending_balance))
            z.metric("Confirmed Transactions", fmt(chain.get("tx_count")))

            st.markdown(
                f"[Open wallet in blockchain explorer]({explorer_address(address)})"
            )

            st.subheader("Recent Transactions")

            if isinstance(history, list) and history:
                for tx in history[:10]:
                    txid = tx.get("txid", "")
                    status = tx.get("status", {})
                    label = (
                        "Confirmed"
                        if status.get("confirmed")
                        else "Unconfirmed"
                    )
                    st.write(f"{label}: {txid}")
                    if txid:
                        st.markdown(f"[View transaction]({explorer_tx(txid)})")
            else:
                st.info("No recent transactions returned.")
        else:
            st.error("Address lookup failed. Check the address and retry.")

# Payment details
st.header("Bitcoin Payment")

st.write("Configured receiving address:")
st.code(WALLET)

st.write(f"Configured payment amount: {PAYMENT_AMOUNT_BTC:.3f} BTC")

qr_url = (
    "https://api.qrserver.com/v1/create-qr-code/"
    f"?size=220x220&data=bitcoin:{WALLET}"
    f"%3Famount%3D{PAYMENT_AMOUNT_BTC}"
)

st.image(qr_url, caption="Bitcoin receiving address QR code")

st.markdown(
    f"[Inspect receiving address on the blockchain]({explorer_address(WALLET)})"
)

st.caption(
    "Never send funds until you have independently confirmed the address "
    "and payment terms."
)

st.subheader("Submit Transaction ID")

txid_input = st.text_input("Bitcoin transaction ID")
contact_input = st.text_input("Contact handle or email")

if st.button("Check payment transaction"):
    txid = txid_input.strip()

    if len(txid) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in txid):
        st.error("Enter a valid 64-character Bitcoin transaction ID.")
    else:
        tx = get_json(f"{API}/tx/{txid}")

        if not isinstance(tx, dict):
            st.error("Transaction not found or the blockchain service is unavailable.")
        else:
            status = tx.get("status", {})
            outputs = tx.get("vout", [])

            received_sats = sum(
                int(output.get("value", 0))
                for output in outputs
                if output.get("scriptpubkey_address") == WALLET
            )

            st.write("Transaction:", txid)
            st.write("Amount sent to configured address:", btc(received_sats))
            st.write(
                "Confirmation status:",
                "Confirmed" if status.get("confirmed") else "Pending"
            )

            required_sats = int(PAYMENT_AMOUNT_BTC * 100_000_000)

            if received_sats >= required_sats and status.get("confirmed"):
                st.success("The transaction meets the configured amount and confirmation checks.")
                st.info(
                    "This single-file version does not yet store payment claims, "
                    "prevent duplicate claims persistently, or send email notifications."
                )
            elif received_sats >= required_sats:
                st.warning("The required amount appears in the transaction, but confirmation is pending.")
            else:
                st.error("The transaction does not show the configured amount sent to the receiving address.")

            if contact_input.strip():
                st.caption(
                    "Your contact information has not been emailed or saved by this version."
                )

# Dormancy scanner status
st.header("Dormant Whale Research")

st.info(
    f"Selected threshold: {dormancy_years} years. "
    f"Minimum amount: {minimum_btc:,.8f} BTC."
)

st.warning(
    "Global historical dormant-output scanning is not implemented in this "
    "single-file version. Address lookup does not scan the entire blockchain."
)

# Footer
st.divider()
st.caption("Dormant Whale Radar · Bitcoin On-Chain Analytics")
st.caption("Market and blockchain data depend on external service availability.")

if auto_refresh:
    time.sleep(refresh_seconds)
    st.rerun()
