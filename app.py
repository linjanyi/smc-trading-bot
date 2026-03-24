import streamlit as st
import pandas as pd
import numpy as np
import requests
import yfinance as yf
import pytz
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 初始化 ---
st.set_page_config(page_title="SMC AI-Optimizer V27", layout="wide")
st_autorefresh(interval=30000, key="v27_final") 
tw_tz = pytz.timezone('Asia/Taipei')

# --- 2. 數據表 ---
crypto_info = {"BTCUSDT": "比特幣", "ETHUSDT": "乙太幣", "SOLUSDT": "索拉納", "BNBUSDT": "幣安幣", "DOGEUSDT": "狗狗幣"}
forex_info = {"GC=F": "黃金", "SI=F": "白銀", "NQ=F": "納指", "CL=F": "原油", "EURUSD=X": "歐美", "USDJPY=X": "美日"}

if "active_cryptos" not in st.session_state: st.session_state.active_cryptos = ["BTCUSDT", "ETHUSDT"]
if "active_forex" not in st.session_state: st.session_state.active_forex = ["GC=F", "NQ=F"]

# --- 3. AI 最佳化引擎 ---
def fetch_binance(symbol, interval='1h'):
    endpoints = [f"https://api1.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=500",
                 f"https://api3.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=500"]
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
def find_best_rr(df):
    """AI 掃描器：找出過去30天獲利最高的盈虧比"""
    if df is None or df.empty or len(df) < 50: return 3.0, 0.0, 0.0
    rr_options = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0]
    best_rr, max_profit, best_wr = 3.0, -999, 0
    
    temp = df.copy()
    temp['EMA'] = temp['Close'].ewm(span=200, adjust=False).mean()
    bull = (temp['Low'] > temp['High'].shift(2)) & (temp['Close'] > temp['EMA'])
    bear = (temp['High'] < temp['Low'].shift(2)) & (temp['Close'] < temp['EMA'])
    temp['Sig'] = 0
    temp.loc[bull, 'Sig'], temp.loc[bear, 'Sig'] = 1, -1
    rets_raw = (temp['Sig'].shift(1) * temp['Close'].pct_change()).dropna()

    for r in rr_options:
        # 模擬盈虧
        final_rets = rets_raw.apply(lambda x: 0.005 * r if x > 0 else (-0.005 if x < 0 else 0))
        profit = (np.prod(1 + final_rets) - 1) * 100
        total = len(final_rets[final_rets != 0])
        wr = (len(final_rets[final_rets > 0]) / total * 100) if total > 0 else 0
        if profit > max_profit:
            max_profit, best_rr, best_wr = profit, r, wr
    return best_rr, max_profit, best_wr

@st.cache_data(ttl=20)
def get_analysis_v27(symbol, is_crypto=True):
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
        
        # AI 尋找最佳參數
        best_rr, max_p, wr = find_best_rr(df)
        return {"df": df, "htf": htf_trend, "best_rr": best_rr, "max_p": max_p, "wr": wr}
    except: return None

# --- 4. UI 渲染 ---
st.title("🏹 SMC AI 全球終端 V27")
st.info(f"🇹🇼 台北時間: `{datetime.now(tw_tz).strftime('%H:%M:%S')}` | AI 參數優化引擎：已啟動")

with st.sidebar:
    st.header("⚙️ 設定")
    bal = st.number_input("本金 (USD)", value=10000)
    risk = st.slider("單筆風險 (%)", 0.1, 5.0, 1.0)
    st.divider()
    manual_rr = st.toggle("手動覆蓋 AI 盈虧比", value=False)
    user_rr = st.select_slider("手動 R/R", options=[1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0], value=3.0, disabled=not manual_rr)

# 打勾區
c_sel = [s for s, n in crypto_info.items() if st.checkbox(f"{s}({n})", value=(s in st.session_state.active_cryptos), key=f"c{s}")]
f_sel = [s for s, n in forex_info.items() if st.checkbox(f"{s}({n})", value=(s in st.session_state.active_forex), key=f"f{s}")]
st.session_state.active_cryptos, st.session_state.active_forex = c_sel, f_sel

# --- 5. 顯示矩陣 ---
def render_v27(items, is_crypto):
    if not items: return
    cols = st.columns(3)
    for i, sym in enumerate(items):
        with cols[i % 3]:
            data = get_analysis_v27(sym, is_crypto)
            if data:
                df, htf, best_rr, max_p, wr = data['df'], data['htf'], data['best_rr'], data['max_p'], data['wr']
                last = df.iloc[-1]
                curr_p, atr = float(last['Close']), float(last['ATR'])
                
                # 決定最終使用的 RR
                final_rr = user_rr if manual_rr else best_rr
                
                with st.container():
                    st.markdown(f"#### {sym}")
                    st.write(f"🤖 **AI 推薦 R/R: {best_rr}** (勝率:{wr:.1f}%)")
                    st.write(f"💰 預期月收益: **{max_p:.1f}%**")
                    
                    bull_g = float(last['Low']) - float(df.iloc[-3]['High'])
                    bear_g = float(df.iloc[-3]['Low']) - float(last['High'])
                    
                    if bull_g > (atr*0.5) and curr_p > last['EMA']:
                        st.success("🔥 多單訊號" if htf==1 else "⚠️ 逆勢多單")
                        sl = curr_p - (atr * 2)
                    elif bear_g > (atr*0.5) and curr_p < last['EMA']:
                        st.error("🔥 空單訊號" if htf==-1 else "⚠️ 逆勢空單")
                        sl = curr_p + (atr * 2)
                    else: st.info("🔎 掃描結構中...")
                    
                    if 'sl' in locals():
                        size = (bal * (risk/100)) / abs(curr_p - sl)
                        st.code(f"採用 R/R: {final_rr}\n量: {size:.4f}\nSL: {sl:.4f}\nTP: {curr_p + (curr_p-sl)*final_rr:.4f}")
                st.divider()

render_v27(st.session_state.active_cryptos, True)
render_v27(st.session_state.active_forex, False)
