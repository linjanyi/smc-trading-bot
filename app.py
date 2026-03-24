import streamlit as st
import pandas as pd
import numpy as np
import requests
import yfinance as yf
import pytz
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 初始化與刷新 ---
st.set_page_config(page_title="SMC Binance Official", layout="wide")
st_autorefresh(interval=30000, key="v20_sync") # 幣安 API 很強，30秒刷一次沒問題
tw_tz = pytz.timezone('Asia/Taipei')

# --- 2. 記憶功能 ---
if "active_items" not in st.session_state: 
    st.session_state.active_items = ["BTCUSDT", "ETHUSDT", "GC=F"]

# --- 3. 數據抓取引擎 (幣安官方 Rest API) ---
def get_binance_data(symbol, interval='1h'):
    """直接呼叫幣安公開 API，不需 API Key"""
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=100"
        res = requests.get(url, timeout=5)
        data = res.json()
        df = pd.DataFrame(data, columns=['t','Open','High','Low','Close','v','ct','qv','nt','tbv','tqv','i'])
        df = df[['Open','High','Low','Close']].astype(float)
        return df
    except:
        return pd.DataFrame()

@st.cache_data(ttl=20)
def get_safe_data(symbol):
    try:
        if "USDT" in symbol: # 虛擬幣：走幣安官方 API
            df = get_binance_data(symbol, '1h')
            df_htf = get_binance_data(symbol, '4h')
        else: # 外匯/黃金：走 Yahoo Finance
            df = yf.download(symbol, period='30d', interval='1h', auto_adjust=True, progress=False)
            df_htf = yf.download(symbol, period='60d', interval='4h', auto_adjust=True, progress=False)
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            if isinstance(df_htf.columns, pd.MultiIndex): df_htf.columns = df_htf.columns.get_level_values(0)

        if df.empty or len(df) < 20: return None

        # 指標計算
        df['EMA'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
        
        df_htf['EMA'] = df_htf['Close'].astype(float).ewm(span=200, adjust=False).mean()
        htf_trend = 1 if float(df_htf['Close'].iloc[-1]) > df_htf['EMA'].iloc[-1] else -1
        
        return {"df": df, "htf": htf_trend}
    except:
        return None

# --- 4. 介面渲染 ---
st.title("🏹 SMC 官方實時監控矩陣 (V20)")
now_tw = datetime.now(tw_tz)
st.info(f"🇹🇼 台北時間: `{now_tw.strftime('%H:%M:%S')}` | 數據源: Binance Official API & Yahoo")

with st.sidebar:
    st.header("⚙️ 風控設定")
    bal = st.number_input("本本金 (USD)", value=10000)
    risk = st.slider("單筆風險 (%)", 0.1, 5.0, 1.0)

st.markdown("### 🔍 點擊打勾進行監控")
all_items = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "GC=F", "EURUSD=X", "GBPUSD=X", "NQ=F"]
cols_check = st.columns(len(all_items))
current_selected = []

for i, item in enumerate(all_items):
    with cols_check[i]:
        is_checked = st.checkbox(item, value=(item in st.session_state.active_items))
        if is_checked: current_selected.append(item)
st.session_state.active_items = current_selected

# --- 5. 渲染矩陣 ---
st.divider()
if not st.session_state.active_items:
    st.warning("請先在上方打勾。")
else:
    matrix_cols = st.columns(3)
    for i, sym in enumerate(st.session_state.active_items):
        with matrix_cols[i % 3]:
            data = get_safe_data(sym)
            if data is not None:
                df, htf = data['df'], data['htf']
                last = df.iloc[-1]
                curr_p, atr = float(last['Close']), float(last['ATR'])
                
                with st.container():
                    st.markdown(f"#### {sym}")
                    st.write(f"即時價: **{curr_p:.4f}** | 趨勢: {'📈 多' if htf==1 else '📉 空'}")
                    
                    # SMC 判定 (FVG)
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
                        st.info("🔎 監控中...")

                    if sig:
                        risk_usd = bal * (risk/100)
                        pos_size = risk_usd / abs(curr_p - sl)
                        st.code(f"量: {pos_size:.4f}\nSL: {sl:.4f}\nTP: {curr_p + (curr_p-sl)*3:.4f}")
            else:
                st.error(f"❌ {sym}: 數據加載失敗")
            st.divider()
