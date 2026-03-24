import streamlit as st
import pandas as pd
import numpy as np
import requests
import yfinance as yf
import pytz
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 配置與刷新 ---
st.set_page_config(page_title="SMC Strategy Matrix V23", layout="wide")
st_autorefresh(interval=30000, key="v23_sync") 
tw_tz = pytz.timezone('Asia/Taipei')

# --- 2. 數據對照表 ---
crypto_info = {
    "BTCUSDT": "比特幣 (BTC)", "ETHUSDT": "乙太幣 (ETH)", "SOLUSDT": "索拉納 (SOL)",
    "BNBUSDT": "幣安幣 (BNB)", "DOGEUSDT": "狗狗幣 (DOGE)", "XRPUSDT": "瑞波幣 (XRP)"
}
forex_info = {
    "GC=F": "黃金 (Gold)", "NQ=F": "納指 (Nasdaq)", "CL=F": "原油 (Oil)",
    "EURUSD=X": "歐美 (EUR/USD)", "GBPUSD=X": "鎊美 (GBP/USD)", "USDJPY=X": "美日 (USD/JPY)"
}

# --- 3. 記憶功能 ---
if "active_cryptos" not in st.session_state: st.session_state.active_cryptos = ["BTCUSDT"]
if "active_forex" not in st.session_state: st.session_state.active_forex = ["GC=F"]

# --- 4. 數據抓取與 30D 回測引擎 ---
def fetch_binance(symbol, interval='1h'):
    endpoints = [f"https://api1.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=500",
                 f"https://api3.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=500"]
    for url in endpoints:
        try:
            res = requests.get(url, timeout=2)
            if res.status_code == 200:
                data = res.json()
                df = pd.DataFrame(data, columns=['t','O','H','L','C','v','ct','qv','nt','tbv','tqv','i'])
                df = df[['O','H','L','C']].astype(float)
                df.columns = ['Open','High','Low','Close']
                return df
        except: continue
    return pd.DataFrame()

@st.cache_data(ttl=600) # 回測數據每 10 分鐘計算一次即可，節省效能
def get_backtest_stats(df, rr=3.0):
    if df is None or df.empty or len(df) < 50: return 0, 0
    temp_df = df.copy()
    temp_df['EMA'] = temp_df['Close'].ewm(span=200, adjust=False).mean()
    # 簡化版 SMC 訊號模擬
    bull = (temp_df['Low'] > temp_df['High'].shift(2)) & (temp_df['Close'] > temp_df['EMA'])
    bear = (temp_df['High'] < temp_df['Low'].shift(2)) & (temp_df['Close'] < temp_df['EMA'])
    temp_df['Sig'] = 0
    temp_df.loc[bull, 'Sig'], temp_df.loc[bear, 'Sig'] = 1, -1
    
    # 計算盈虧
    rets = (temp_df['Sig'].shift(1) * temp_df['Close'].pct_change()).dropna()
    final_rets = rets.clip(lower=-0.005, upper=0.005 * rr) # 模擬止損與止盈
    total_trades = len(final_rets[final_rets != 0])
    wr = (len(final_rets[final_rets > 0]) / total_trades * 100) if total_trades > 0 else 0
    profit = (np.prod(1 + final_rets) - 1) * 100
    return wr, profit

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
        
        if df.empty or df_htf.empty: return None
        
        # 指標計算
        df['EMA'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
        df_htf['EMA'] = df_htf['Close'].astype(float).ewm(span=200, adjust=False).mean()
        htf_trend = 1 if float(df_htf['Close'].iloc[-1]) > df_htf['EMA'].iloc[-1] else -1
        
        wr, profit = get_backtest_stats(df)
        return {"df": df, "htf": htf_trend, "wr": wr, "profit": profit}
    except: return None

# --- 5. 介面渲染 ---
st.title("🏹 SMC 全球量化導航 V23")
st.info(f"🇹🇼 台北時間: `{datetime.now(tw_tz).strftime('%H:%M:%S')}` | 狀態: 30D 勝率統計已回歸")

with st.sidebar:
    st.header("💰 風控設定")
    bal = st.number_input("總本金 (USD)", value=10000)
    risk = st.slider("單筆風險 (%)", 0.1, 5.0, 1.0)

# 橫向打勾選單 (帶中文)
st.markdown("### 🌌 虛擬幣監控")
c_sel = [s for s, n in crypto_info.items() if st.sidebar.checkbox(f"{s} ({n})", value=(s in st.session_state.active_cryptos))]
st.session_state.active_cryptos = c_sel # 這裡簡化為放在側邊欄，避免主頁太亂

st.markdown("### 💵 外匯與商品")
f_sel = [s for s, n in forex_info.items() if st.sidebar.checkbox(f"{s} ({n})", value=(s in st.session_state.active_forex))]
st.session_state.active_forex = f_sel

# --- 6. 矩陣渲染 ---
def render_matrix(items, is_crypto):
    if not items: return
    cols = st.columns(3)
    for i, sym in enumerate(items):
        with cols[i % 3]:
            data = get_analysis_data(sym, is_crypto)
            if data:
                df, htf, wr, profit = data['df'], data['htf'], data['wr'], data['profit']
                last = df.iloc[-1]
                curr_p, atr = float(last['Close']), float(last['ATR'])
                name = crypto_info.get(sym) if is_crypto else forex_info.get(sym)
                
                with st.container():
                    st.markdown(f"#### {sym} ({name})")
                    st.write(f"📈 **30D 勝率: {wr:.1f}%** | 獲利: **{profit:.1f}%**")
                    st.write(f"價格: `{curr_p:.4f}` | 趨勢: {'📈 多' if htf==1 else '📉 空'}")
                    
                    bull_g = float(last['Low']) - float(df.iloc[-3]['High'])
                    bear_g = float(df.iloc[-3]['Low']) - float(last['High'])
                    
                    if bull_g > (atr*0.5) and curr_p > last['EMA']:
                        st.success("🔥 強力共振多單" if htf==1 else "⚠️ 逆勢多單")
                        sl = curr_p - (atr * 2)
                        size = (bal * (risk/100)) / abs(curr_p - sl)
                        st.code(f"量: {size:.4f}\nSL: {sl:.4f}\nTP: {curr_p+(curr_p-sl)*3:.4f}")
                    elif bear_g > (atr*0.5) and curr_p < last['EMA']:
                        st.error("🔥 強力共振空單" if htf==-1 else "⚠️ 逆勢空單")
                        sl = curr_p + (atr * 2)
                        size = (bal * (risk/100)) / abs(curr_p - sl)
                        st.code(f"量: {size:.4f}\nSL: {sl:.4f}\nTP: {curr_p-(sl-curr_p)*3:.4f}")
                    else: st.info("🔎 監控中...")
                st.divider()

render_matrix(st.session_state.active_cryptos, True)
render_matrix(st.session_state.active_forex, False)
