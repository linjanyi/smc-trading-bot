import streamlit as st
import ccxt
import yfinance as yf
import pandas as pd
import numpy as np
import pytz
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 配置與時區 ---
st.set_page_config(page_title="SMC Stable Matrix", layout="wide")
st_autorefresh(interval=30000, key="global_sync") 
tw_tz = pytz.timezone('Asia/Taipei')

# 初始化幣安 (Binance)
exchange = ccxt.binance({'enableRateLimit': True})

# --- 2. 記憶功能 ---
if "active_items" not in st.session_state: 
    st.session_state.active_items = ["BTC/USDT", "GC=F"]

# --- 3. 頂部打勾面板 ---
st.title("⚡ SMC 實時監控矩陣 (穩定修復版)")
now_tw = datetime.now(tw_tz)
st.info(f"🇹🇼 台北時間: `{now_tw.strftime('%Y-%m-%d %H:%M:%S')}`")

with st.sidebar:
    st.header("⚙️ 風控設定")
    bal = st.number_input("本金 (USD)", value=10000)
    risk = st.slider("單筆風險 (%)", 0.1, 5.0, 1.0)

st.markdown("### 🔍 監控清單 (直接打勾)")
all_items = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "GC=F", "EURUSD=X", "GBPUSD=X", "NQ=F"]
cols_check = st.columns(len(all_items))
current_selected = []

for i, item in enumerate(all_items):
    with cols_check[i]:
        is_checked = st.checkbox(item, value=(item in st.session_state.active_items))
        if is_checked: current_selected.append(item)
st.session_state.active_items = current_selected

# --- 4. 強化版數據抓取引擎 ---
@st.cache_data(ttl=20)
def get_data(symbol):
    try:
        if "/" in symbol: # 幣安數據
            bars = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=100)
            df = pd.DataFrame(bars, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
            df_htf_bars = exchange.fetch_ohlcv(symbol, timeframe='4h', limit=100)
            df_htf = pd.DataFrame(df_htf_bars, columns=['t', 'O', 'H', 'L', 'Close', 'V'])
        else: # Yahoo 數據
            df = yf.download(symbol, period='30d', interval='1h', auto_adjust=True, progress=False)
            df_htf = yf.download(symbol, period='60d', interval='4h', auto_adjust=True, progress=False)
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            if isinstance(df_htf.columns, pd.MultiIndex): df_htf.columns = df_htf.columns.get_level_values(0)

        # --- 核心防禦：檢查 DataFrame 是否為空 ---
        if df.empty or len(df) < 5 or df_htf.empty:
            return None

        # 統一計算指標
        df['EMA'] = df['Close'].astype(float).ewm(span=200, adjust=False).mean()
        df['ATR'] = (df['High'].astype(float) - df['Low'].astype(float)).rolling(14).mean()
        df_htf['EMA'] = df_htf['Close'].astype(float).ewm(span=200, adjust=False).mean()
        htf_trend = 1 if float(df_htf['Close'].iloc[-1]) > df_htf['EMA'].iloc[-1] else -1
        
        return {"df": df, "htf": htf_trend}
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None

# --- 5. 渲染矩陣 ---
st.divider()
if not st.session_state.active_items:
    st.warning("請在上方清單中「打勾」想要監控的品種。")
else:
    matrix_cols = st.columns(3)
    for i, sym in enumerate(st.session_state.active_items):
        with matrix_cols[i % 3]:
            data = get_data(sym)
            
            # 這裡檢查數據是否獲取成功
            if data is not None:
                df, htf = data['df'], data['htf']
                last = df.iloc[-1] # 此時保證有數據，不會報 Index Error
                curr_p, atr = float(last['Close']), float(last['ATR'])
                
                with st.container():
                    st.markdown(f"#### {sym}")
                    st.write(f"即時價: **{curr_p:.4f}** | 趨勢: {'📈 多' if htf==1 else '📉 空'}")
                    
                    bull_g = float(last['Low']) - float(df.iloc[-3]['High'])
                    bear_g = float(df.iloc[-3]['Low']) - float(last['High'])
                    
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
                        risk_usd = bal * (risk/100)
                        pos_size = risk_usd / abs(curr_p - sl)
                        st.code(f"量: {pos_size:.4f}\nSL: {sl:.4f}\nTP: {curr_p + (curr_p-sl)*3:.4f}")
            else:
                st.error(f"❌ {sym}: 數據抓取失敗 (休市或代碼錯誤)")
            st.divider()
