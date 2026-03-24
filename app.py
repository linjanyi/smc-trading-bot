import streamlit as st
import pandas as pd
import numpy as np
import requests
import yfinance as yf
import pytz
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 初始化與刷新 ---
st.set_page_config(page_title="SMC Global Matrix V21", layout="wide")
st_autorefresh(interval=30000, key="v21_sync") # 30秒自動刷新
tw_tz = pytz.timezone('Asia/Taipei')

# --- 2. 記憶功能 (Session State) ---
if "active_cryptos" not in st.session_state: 
    st.session_state.active_cryptos = ["BTCUSDT", "ETHUSDT"]
if "active_forex" not in st.session_state: 
    st.session_state.active_forex = ["GC=F", "EURUSD=X"]

# --- 3. 數據抓取引擎 (多端點備援) ---
def fetch_binance(symbol, interval='1h'):
    """嘗試多個幣安官方 API 節點，繞過雲端封鎖"""
    endpoints = [
        f"https://api1.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=150",
        f"https://api3.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=150",
        f"https://api.binance.us/api/v3/klines?symbol={symbol}&interval={interval}&limit=150"
    ]
    for url in endpoints:
        try:
            res = requests.get(url, timeout=2)
            if res.status_code == 200:
                data = res.json()
                df = pd.DataFrame(data, columns=['t','O','H','L','C','v','ct','qv','nt','tbv','tqv','i'])
                df = df[['O','H','L','C']].astype(float)
                df.columns = ['Open','High','Low','Close']
                if not df.empty: return df
        except: continue
    return pd.DataFrame()

@st.cache_data(ttl=20)
def get_analysis_data(symbol, is_crypto=True):
    try:
        if is_crypto:
            df = fetch_binance(symbol, '1h')
            df_htf = fetch_binance(symbol, '4h')
        else:
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
    except: return None

# --- 4. 介面渲染：分開的打勾區域 ---
st.title("🏹 SMC 全球實時監控終端 V21")
now_tw = datetime.now(tw_tz)
st.info(f"🇹🇼 台北時間: `{now_tw.strftime('%Y-%m-%d %H:%M:%S')}` | 狀態: 幣安 API 多端點備援已啟動")

# 風控區 (側邊欄)
with st.sidebar:
    st.header("⚙️ 交易設定")
    bal = st.number_input("本金 (USD)", value=10000)
    risk = st.slider("單筆風險 (%)", 0.1, 5.0, 1.0)
    st.divider()
    st.caption("每個人的設定獨立記憶，重新整理不消失。")

# --- 分類打勾選單 ---
st.markdown("### 🌌 虛擬幣監控 (Binance Real-time)")
crypto_all = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "DOGEUSDT", "XRPUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT"]
c_cols = st.columns(5)
c_selected = []
for i, coin in enumerate(crypto_all):
    with c_cols[i % 5]:
        if st.checkbox(coin, value=(coin in st.session_state.active_cryptos)): c_selected.append(coin)
st.session_state.active_cryptos = c_selected

st.markdown("### 💵 外匯與商品監控 (Yahoo Finance)")
forex_all = ["GC=F", "SI=F", "CL=F", "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "NQ=F", "YM=F", "ES=F"]
f_cols = st.columns(5)
f_selected = []
for i, fx in enumerate(forex_all):
    with f_cols[i % 5]:
        if st.checkbox(fx, value=(fx in st.session_state.active_forex)): f_selected.append(fx)
st.session_state.active_forex = f_selected

# --- 5. 渲染矩陣 ---
def render_matrix(items, is_crypto):
    if not items: return
    cols = st.columns(3)
    for i, sym in enumerate(items):
        with cols[i % 3]:
            data = get_analysis_data(sym, is_crypto)
            if data:
                df, htf = data['df'], data['htf']
                last = df.iloc[-1]
                curr_p, atr = float(last['Close']), float(last['ATR'])
                with st.container():
                    st.markdown(f"#### {sym}")
                    st.write(f"價格: **{curr_p:.4f}** | 趨勢: {'📈 多' if htf==1 else '📉 空'}")
                    bull_g = float(last['Low']) - float(df.iloc[-3]['High'])
                    bear_g = float(df.iloc[-3]['Low']) - float(last['High'])
                    
                    sig = None
                    if bull_g > (atr*0.5) and curr_p > last['EMA']:
                        sig, status = "BUY", ("🔥 強力多單" if htf==1 else "⚠️ 逆勢多單")
                        st.success(status); sl = curr_p - (atr * 2)
                    elif bear_g > (atr*0.5) and curr_p < last['EMA']:
                        sig, status = "SELL", ("🔥 強力空單" if htf==-1 else "⚠️ 逆勢空單")
                        st.error(status); sl = curr_p + (atr * 2)
                    else: st.info("🔎 監控中...")

                    if sig:
                        risk_usd = bal * (risk/100)
                        pos_size = risk_usd / abs(curr_p - sl)
                        st.code(f"量: {pos_size:.4f}\nSL: {sl:.4f}\nTP: {curr_p + (curr_p-sl)*3:.4f}")
            else: st.error(f"❌ {sym} 數據獲取失敗")
            st.divider()

st.divider()
st.subheader("🚀 實時訊號矩陣")
render_matrix(st.session_state.active_cryptos, True)
render_matrix(st.session_state.active_forex, False)
