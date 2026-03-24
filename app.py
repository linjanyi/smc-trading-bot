import streamlit as st
import pandas as pd
import numpy as np
import requests
import yfinance as yf
import pytz
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 配置與刷新 ---
st.set_page_config(page_title="SMC R/R Optimizer V26", layout="wide")
st_autorefresh(interval=30000, key="v26_sync") 
tw_tz = pytz.timezone('Asia/Taipei')

# --- 2. 數據對照表 ---
crypto_info = {"BTCUSDT": "比特幣", "ETHUSDT": "乙太幣", "SOLUSDT": "索拉納", "BNBUSDT": "幣安幣"}
forex_info = {"GC=F": "黃金", "NQ=F": "納指", "EURUSD=X": "歐美", "GBPUSD=X": "鎊美"}

if "active_cryptos" not in st.session_state: st.session_state.active_cryptos = ["BTCUSDT"]
if "active_forex" not in st.session_state: st.session_state.active_forex = ["GC=F"]

# --- 3. 核心引擎：動態 R/R 回測 ---
def fetch_binance(symbol, interval='1h'):
    endpoints = [f"https://api1.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=500",
                 f"https://api.binance.us/api/v3/klines?symbol={symbol}&interval={interval}&limit=500"]
    for url in endpoints:
        try:
            res = requests.get(url, timeout=2)
            if res.status_code == 200:
                df = pd.DataFrame(res.json(), columns=['t','O','H','L','C','v','ct','qv','nt','tbv','tqv','i'])
                df = df[['O','H','L','C']].astype(float)
                df.columns = ['Open','High','Low','Close']
                return df
        except: continue
    return pd.DataFrame()

@st.cache_data(ttl=600)
def get_stats(df, rr_ratio):
    if df is None or df.empty or len(df) < 50: return 0.0, 0.0
    temp = df.copy()
    temp['EMA'] = temp['Close'].ewm(span=200, adjust=False).mean()
    bull = (temp['Low'] > temp['High'].shift(2)) & (temp['Close'] > temp['EMA'])
    bear = (temp['High'] < temp['Low'].shift(2)) & (temp['Close'] < temp['EMA'])
    temp['Sig'] = 0
    temp.loc[bull, 'Sig'], temp.loc[bear, 'Sig'] = 1, -1
    
    # 核心邏輯：根據使用者設定的 RR 計算盈虧
    rets = (temp['Sig'].shift(1) * temp['Close'].pct_change()).dropna()
    # 模擬：輸了賠 0.5%，贏了賺 0.5% * rr_ratio
    final_rets = rets.apply(lambda x: 0.005 * rr_ratio if x > 0 else (-0.005 if x < 0 else 0))
    
    total = len(final_rets[final_rets != 0])
    wr = (len(final_rets[final_rets > 0]) / total * 100) if total > 0 else 0.0
    profit = (np.prod(1 + final_rets) - 1) * 100
    return wr, profit

@st.cache_data(ttl=20)
def get_analysis(symbol, rr_val, is_crypto=True):
    try:
        df = fetch_binance(symbol) if is_crypto else yf.download(symbol, period='30d', interval='1h', progress=False)
        df_htf = fetch_binance(symbol, '4h') if is_crypto else yf.download(symbol, period='60d', interval='4h', progress=False)
        if not is_crypto:
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            if isinstance(df_htf.columns, pd.MultiIndex): df_htf.columns = df_htf.columns.get_level_values(0)
        
        df['EMA'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
        df_htf['EMA'] = df_htf['Close'].astype(float).ewm(span=200, adjust=False).mean()
        htf_trend = 1 if float(df_htf['Close'].iloc[-1]) > df_htf['EMA'].iloc[-1] else -1
        wr, profit = get_stats(df, rr_val)
        return {"df": df, "htf": htf_trend, "wr": wr, "profit": profit}
    except: return None

# --- 4. 介面渲染 ---
st.title("🏹 SMC 策略優化終端 V26")
with st.sidebar:
    st.header("⚙️ 全域參數優化")
    bal = st.number_input("總本金 (USD)", value=10000)
    risk = st.slider("單筆風險 (%)", 0.1, 5.0, 1.0)
    st.divider()
    # 這就是你要的「盈虧比調節器」
    target_rr = st.select_slider("🎯 目標盈虧比 (R/R Ratio)", options=[1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0], value=3.0)
    st.write(f"當前策略：虧 1 賠 {target_rr}")

# 主頁打勾區
st.markdown("### 🔍 監控清單")
c_cols = st.columns(4)
c_sel = [s for s, n in crypto_info.items() if st.checkbox(f"{s}({n})", value=(s in st.session_state.active_cryptos))]
f_cols = st.columns(4)
f_sel = [s for s, n in forex_info.items() if st.checkbox(f"{s}({n})", value=(s in st.session_state.active_forex))]
st.session_state.active_cryptos, st.session_state.active_forex = c_sel, f_sel

# --- 5. 顯示矩陣 ---
def render(items, is_crypto):
    if not items: return
    cols = st.columns(3)
    for i, sym in enumerate(items):
        with cols[i % 3]:
            data = get_analysis(sym, target_rr, is_crypto)
            if data:
                df, htf, wr, profit = data['df'], data['htf'], data['wr'], data['profit']
                last = df.iloc[-1]
                curr_p, atr = float(last['Close']), float(last['ATR'])
                with st.container():
                    st.markdown(f"#### {sym}")
                    st.write(f"📊 **30D 勝率: {wr:.1f}%** | 預期獲利: **{profit:.1f}%**")
                    
                    bull_g = float(last['Low']) - float(df.iloc[-3]['High'])
                    bear_g = float(df.iloc[-3]['Low']) - float(last['High'])
                    
                    if bull_g > (atr*0.5) and curr_p > last['EMA']:
                        st.success("🔥 強力多單" if htf==1 else "⚠️ 逆勢多單")
                        sl = curr_p - (atr * 2)
                    elif bear_g > (atr*0.5) and curr_p < last['EMA']:
                        st.error("🔥 強力空單" if htf==-1 else "⚠️ 逆勢空單")
                        sl = curr_p + (atr * 2)
                    else: st.info("🔎 監控中...")
                    
                    if 'sl' in locals():
                        size = (bal * (risk/100)) / abs(curr_p - sl)
                        st.code(f"建議單量: {size:.4f}\n止損: {sl:.4f}\n止盈: {curr_p + (curr_p-sl)*target_rr:.4f}")
                st.divider()

render(st.session_state.active_cryptos, True)
render(st.session_state.active_forex, False)
