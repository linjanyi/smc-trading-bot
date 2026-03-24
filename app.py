import streamlit as st
import pandas as pd
import numpy as np
import requests
import yfinance as yf
import pytz
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 初始化與環境設定 ---
st.set_page_config(page_title="SMC Pro Matrix V29", layout="wide")
st_autorefresh(interval=30000, key="v29_sync") 
tw_tz = pytz.timezone('Asia/Taipei')

# --- 2. 數據對照表 ---
crypto_info = {
    "BTCUSDT": "比特幣 (BTC)", "ETHUSDT": "乙太幣 (ETH)", "SOLUSDT": "索拉納 (SOL)",
    "BNBUSDT": "幣安幣 (BNB)", "DOGEUSDT": "狗狗幣 (Doge)", "XRPUSDT": "瑞波幣 (XRP)",
    "ADAUSDT": "艾達幣 (ADA)", "AVAXUSDT": "雪崩幣 (AVAX)"
}
forex_info = {
    "GC=F": "黃金期貨 (Gold)", "SI=F": "白銀期貨 (Silver)", "NQ=F": "納指100 (Nasdaq)", 
    "CL=F": "原油期貨 (Oil)", "EURUSD=X": "歐美外匯 (EUR/USD)", "GBPUSD=X": "鎊美外匯 (GBP/USD)",
    "USDJPY=X": "美日外匯 (USD/JPY)", "ES=F": "標普500 (S&P)"
}

if "active_cryptos" not in st.session_state: st.session_state.active_cryptos = ["BTCUSDT", "ETHUSDT"]
if "active_forex" not in st.session_state: st.session_state.active_forex = ["GC=F", "NQ=F"]
if "ranking_data" not in st.session_state: st.session_state.ranking_data = []

# --- 3. 數據引擎 ---
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
    if df is None or df.empty or len(df) < 50: return 3.0, 0.0, 0.0
    rr_options = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0]
    best_rr, max_profit, best_wr = 3.0, -999.0, 0.0
    temp = df.copy()
    temp['EMA'] = temp['Close'].ewm(span=200, adjust=False).mean()
    bull = (temp['Low'] > temp['High'].shift(2)) & (temp['Close'] > temp['EMA'])
    bear = (temp['High'] < temp['Low'].shift(2)) & (temp['Close'] < temp['EMA'])
    temp['Sig'] = 0
    temp.loc[bull, 'Sig'], temp.loc[bear, 'Sig'] = 1, -1
    rets_raw = (temp['Sig'].shift(1) * temp['Close'].pct_change()).dropna()
    for r in rr_options:
        final_rets = rets_raw.apply(lambda x: 0.005 * r if x > 0 else (-0.005 if x < 0 else 0))
        profit = (np.prod(1 + final_rets) - 1) * 100
        total = len(final_rets[final_rets != 0])
        wr = (len(final_rets[final_rets > 0]) / total * 100) if total > 0 else 0
        if profit > max_profit: max_profit, best_rr, best_wr = profit, r, wr
    return best_rr, max_profit, best_wr

@st.cache_data(ttl=20)
def get_analysis_v29(symbol, is_crypto=True):
    try:
        df = fetch_binance(symbol) if is_crypto else yf.download(symbol, period='30d', interval='1h', auto_adjust=True, progress=False)
        df_htf = fetch_binance(symbol, '4h') if is_crypto else yf.download(symbol, period='60d', interval='4h', auto_adjust=True, progress=False)
        if not is_crypto:
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            if isinstance(df_htf.columns, pd.MultiIndex): df_htf.columns = df_htf.columns.get_level_values(0)
        df['EMA'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
        df_htf['EMA'] = df_htf['Close'].astype(float).ewm(span=200, adjust=False).mean()
        htf_t = 1 if float(df_htf['Close'].iloc[-1]) > df_htf['EMA'].iloc[-1] else -1
        best_rr, max_p, wr = find_best_rr(df)
        return {"df": df, "htf": htf_t, "best_rr": best_rr, "max_p": max_p, "wr": wr}
    except: return None

# --- 4. 介面渲染 ---
st.title("🏹 SMC 全球量化終端 V29")
st.info(f"🇹🇼 台北時間: `{datetime.now(tw_tz).strftime('%H:%M:%S')}`")

with st.sidebar:
    st.header("💰 帳戶設定")
    bal = st.number_input("本金 (USD)", value=10000)
    risk = st.slider("單筆風險 (%)", 0.1, 5.0, 1.0)
    st.divider()
    manual_mode = st.toggle("手動覆蓋 AI 盈虧比", value=False)
    user_rr = st.select_slider("手動 R/R", options=[1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0], value=3.0, disabled=not manual_mode)

# 打勾區
st.markdown("### 🌌 虛擬幣市場")
c_cols = st.columns(4)
c_sel = [s for s, n in crypto_info.items() if st.checkbox(f"{s}({n})", value=(s in st.session_state.active_cryptos), key=f"c_{s}")]
st.session_state.active_cryptos = c_sel

st.markdown("### 💵 外匯與商品")
f_cols = st.columns(4)
f_sel = [s for s, n in forex_info.items() if st.checkbox(f"{s}({n})", value=(s in st.session_state.active_forex), key=f"f_{s}")]
st.session_state.active_forex = f_sel

# --- 5. 渲染矩陣與排行榜數據收集 ---
ranking_list = []

def render_market(title, items, is_crypto):
    st.divider()
    st.subheader(title)
    if not items: return
    cols = st.columns(3)
    for i, sym in enumerate(items):
        with cols[i % 3]:
            data = get_analysis_v29(sym, is_crypto)
            if data:
                df, htf, best_rr, max_p, wr = data['df'], data['htf'], data['best_rr'], data['max_p'], data['wr']
                curr_p, atr = float(df['Close'].iloc[-1]), float(df['ATR'].iloc[-1])
                ranking_list.append({"Symbol": sym, "Name": crypto_info.get(sym) if is_crypto else forex_info.get(sym), "Profit": max_p, "WR": wr})
                
                final_rr = user_rr if manual_mode else best_rr
                with st.container():
                    st.markdown(f"#### {sym}")
                    st.write(f"📊 勝率: {wr:.1f}% | 獲利: {max_p:.1f}%")
                    
                    bull_g = float(df['Low'].iloc[-1]) - float(df['High'].iloc[-3])
                    bear_g = float(df['High'].iloc[-3]) - float(df['Low'].iloc[-1])
                    
                    sig = None
                    if bull_g > (atr*0.5) and curr_p > df['EMA'].iloc[-1]:
                        sig, status = "BUY", ("🔥 強力多單" if htf==1 else "⚠️ 逆勢多單")
                        st.success(status); sl = curr_p - (atr * 2)
                    elif bear_g > (atr*0.5) and curr_p < df['EMA'].iloc[-1]:
                        sig, status = "SELL", ("🔥 強力空單" if htf==-1 else "⚠️ 逆勢空單")
                        st.error(status); sl = curr_p + (atr * 2)
                    else: st.info("🔎 監控中...")
                    
                    if sig:
                        pos = (bal * (risk/100)) / abs(curr_p - sl)
                        st.code(f"採用 R/R: {final_rr}\n量: {pos:.4f}\nSL: {sl:.4f}\nTP: {curr_p + (curr_p-sl)*final_rr:.4f}")
            st.divider()

render_market("🚀 虛擬幣實時訊號", st.session_state.active_cryptos, True)
render_market("🌎 外匯與商品訊號", st.session_state.active_forex, False)

# --- 6. 今日最強趨勢排行榜 ---
st.divider()
st.subheader("🏆 今日最強趨勢排行榜 (Top 5)")
if ranking_list:
    df_rank = pd.DataFrame(ranking_list).sort_values(by="Profit", ascending=False).head(5)
    # 美化顯示
    for idx, row in df_rank.iterrows():
        st.markdown(f"**Top {idx+1}: {row['Symbol']} ({row['Name']})** — 預期獲利: `{row['Profit']:.1f}%` | 勝率: `{row['WR']:.1f}%`")
        st.progress(min(max(row['Profit']/50, 0.0), 1.0)) # 視覺化進度條
