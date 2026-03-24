import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import pytz
from datetime import datetime
import time
from streamlit_autorefresh import st_autorefresh

# --- 1. 初始化頁面與時區 ---
st.set_page_config(page_title="SMC Binance Real-time Matrix", layout="wide")
st_autorefresh(interval=30000, key="binance_sync") # 幣安數據快，我們改為 30 秒刷新一次
tw_tz = pytz.timezone('Asia/Taipei')

# 初始化幣安客戶端 (不需 API Key 即可抓取公開數據)
exchange = ccxt.binance({'enableRateLimit': True})

# --- 2. 獨立會話記憶 (Session State) ---
if "balance" not in st.session_state: st.session_state.balance = 10000
if "risk" not in st.session_state: st.session_state.risk = 1.0
# 預設勾選的幣種
if "active_coins" not in st.session_state: st.session_state.active_coins = ["BTC/USDT", "ETH/USDT"]

# --- 3. 頂部「全展開打勾」監控面板 ---
st.title("⚡ SMC 幣安實時監控終端 V18")
now_tw = datetime.now(tw_tz)
st.info(f"🇹🇼 台北時間: `{now_tw.strftime('%H:%M:%S')}` | 數據源: Binance Real-time (CCXT)")

# 風控設定 (橫向)
set1, set2, set3 = st.columns([1, 1, 2])
with set1:
    st.session_state.balance = st.number_input("本金 (USD)", value=st.session_state.account_balance if "account_balance" in st.session_state else 10000)
with set2:
    st.session_state.risk = st.slider("單筆風險 (%)", 0.1, 5.0, 1.0)

st.markdown("### 🔍 虛擬幣監控清單 (直接打勾)")
# 定義想要顯示的打勾清單
all_coins = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "DOGE/USDT", "XRP/USDT", "ADA/USDT", "AVAX/USDT"]

cols_check = st.columns(len(all_coins))
current_selected = []

for i, coin in enumerate(all_coins):
    with cols_check[i]:
        # 這裡實現真正的「打勾」介面
        is_checked = st.checkbox(coin, value=(coin in st.session_state.active_coins))
        if is_checked:
            current_selected.append(coin)
st.session_state.active_coins = current_selected

# --- 4. 幣安數據抓取引擎 ---
@st.cache_data(ttl=20) # 幣安實時數據快取僅設 20 秒
def get_binance_data(symbol):
    try:
        # 抓取 1H 數據 (100 根)
        bars_1h = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=100)
        df = pd.DataFrame(bars_1h, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df['Close'] = df['Close'].astype(float)
        
        # 抓取 4H 數據 (趨勢用)
        bars_4h = exchange.fetch_ohlcv(symbol, timeframe='4h', limit=100)
        df_htf = pd.DataFrame(bars_4h, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
        
        # 指標計算
        df['EMA'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
        
        # 4H 趨勢
        df_htf['EMA'] = df_htf['Close'].astype(float).ewm(span=200, adjust=False).mean()
        htf_trend = 1 if float(df_htf['Close'].iloc[-1]) > df_htf['EMA'].iloc[-1] else -1
        
        return {"df": df, "htf": htf_trend}
    except Exception as e:
        return None

# --- 5. 渲染矩陣 ---
st.divider()
if not st.session_state.active_coins:
    st.warning("請在上方清單中「打勾」想要監控的幣種。")
else:
    matrix_cols = st.columns(3)
    for i, sym in enumerate(st.session_state.active_coins):
        with matrix_cols[i % 3]:
            data = get_binance_data(sym)
            if data:
                df, htf = data['df'], data['htf']
                last = df.iloc[-1]
                curr_p, atr = last['Close'], last['ATR']
                
                with st.container():
                    st.markdown(f"#### {sym}")
                    st.write(f"即時價: **{curr_p:.4f}** | 4H趨勢: {'📈' if htf==1 else '📉'}")
                    
                    # SMC 判定 (FVG 缺口)
                    bull_g = last['Low'] - df.iloc[-3]['High']
                    bear_g = df.iloc[-3]['Low'] - last['High']
                    
                    sig = None
                    if bull_g > (atr*0.5) and curr_p > last['EMA']:
                        sig = "BUY"
                        st.success("🔥 強力共振多單" if htf==1 else "⚠️ 逆勢多單")
                        sl = curr_p - (atr * 2)
                    elif bear_g > (atr*0.5) and curr_p < last['EMA']:
                        sig = "SELL"
                        st.error("🔥 強力共振空單" if htf==-1 else "⚠️ 逆勢空單")
                        sl = curr_p + (atr * 2)
                    else:
                        st.info("🔎 結構監控中...")

                    if sig:
                        risk_usd = st.session_state.balance * (st.session_state.risk/100)
                        pos_size = risk_usd / abs(curr_p - sl)
                        st.code(f"建議單量: {pos_size:.4f}\n止損位: {sl:.4f}\n止盈位: {curr_p + (curr_p-sl)*3:.4f}")
                st.divider()
