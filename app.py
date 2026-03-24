import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 系統配置 ---
st.set_page_config(page_title="SMC Pro Matrix", layout="wide")
st_autorefresh(interval=60000, key="final_scan")

# --- 2. 側邊欄：帳戶與風控設定 ---
st.sidebar.header("💰 帳戶風控設定")
ACCOUNT_BALANCE = st.sidebar.number_input("帳戶總資金 (USD)", value=10000)
RISK_PER_TRADE = st.sidebar.slider("單筆風險 (%)", 0.5, 5.0, 1.0) / 100
RR_TARGET = st.sidebar.slider("目標盈虧比 (R/R)", 2.0, 5.0, 3.0)

st.sidebar.divider()
CRYPTO_LIST = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"]
FOREX_LIST = ["GC=F", "EURUSD=X", "GBPUSD=X", "USDJPY=X", "NQ=F"]

selected_cryptos = st.sidebar.multiselect("🌌 加密幣監控", CRYPTO_LIST, default=["BTC-USD"])
selected_forex = st.sidebar.multiselect("💵 外匯/黃金監控", FOREX_LIST, default=["GC=F", "EURUSD=X"])
TOTAL_LIST = selected_cryptos + selected_forex

# --- 3. 核心運算引擎 ---
@st.cache_data(ttl=600)
def get_full_analysis(symbol):
    try:
        df_1h = yf.download(symbol, period='30d', interval='1h', auto_adjust=True, progress=False)
        df_4h = yf.download(symbol, period='60d', interval='4h', auto_adjust=True, progress=False)
        for d in [df_1h, df_4h]:
            if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
        
        # 30D 回測
        df_1h['EMA200'] = df_1h['Close'].ewm(span=200, adjust=False).mean()
        df_1h['ATR'] = (df_1h['High'] - df_1h['Low']).rolling(14).mean()
        bull = (df_1h['Low'] > df_1h['High'].shift(2)) & (df_1h['Close'] > df_1h['EMA200'])
        bear = (df_1h['High'] < df_1h['Low'].shift(2)) & (df_1h['Close'] < df_1h['EMA200'])
        df_1h['Sig'] = 0
        df_1h.loc[bull, 'Sig'], df_1h.loc[bear, 'Sig'] = 1, -1
        rets = (df_1h['Sig'].shift(1) * df_1h['Close'].pct_change()).dropna()
        final_rets = rets.clip(lower=-0.005, upper=0.005*RR_TARGET)
        wr = (len(final_rets[final_rets > 0]) / len(final_rets[final_rets != 0]) * 100) if len(final_rets[final_rets != 0]) > 0 else 0
        
        # HTF 趨勢
        df_4h['EMA200'] = df_4h['Close'].ewm(span=200, adjust=False).mean()
        htf = 1 if df_4h['Close'].iloc[-1] > df_4h['EMA200'].iloc[-1] else -1
        
        return {"df": df_1h, "wr": wr, "htf": htf}
    except: return None

# --- 4. 介面渲染與倉位計算 ---
st.title("🏹 SMC 策略矩陣 & 自動倉位計算")

if not TOTAL_LIST:
    st.info("👈 請在左側勾選要監控的商品")
else:
    cols = st.columns(3)
    for i, symbol in enumerate(TOTAL_LIST):
        with cols[i % 3]:
            data = get_full_analysis(symbol)
            if data:
                df, wr, htf = data['df'], data['wr'], data['htf']
                last = df.iloc[-1]
                curr_p, atr = last['Close'], last['ATR']
                
                st.subheader(f"{symbol}")
                st.caption(f"歷史勝率: **{wr:.1f}%** | 大趨勢: **{'UP' if htf==1 else 'DOWN'}**")
                
                # SMC 判定
                bull_gap = last['Low'] - df.iloc[-3]['High']
                bear_gap = df.iloc[-3]['Low'] - last['High']
                
                if bull_gap > (atr*0.5) and curr_p > last['EMA200']:
                    sig_type = "BUY"
                    sl = curr_p - (atr * 2)
                    st.success(f"🔥 強力多單" if htf==1 else "⚠️ 逆勢多單")
                elif bear_gap > (atr*0.5) and curr_p < last['EMA200']:
                    sig_type = "SELL"
                    sl = curr_p + (atr * 2)
                    st.error(f"🔥 強力空單" if htf==-1 else "⚠️ 逆勢空單")
                else:
                    sig_type = None
                    st.info("🔎 掃描中...")

                if sig_type:
                    # 倉位計算邏輯
                    risk_amt = ACCOUNT_BALANCE * RISK_PER_TRADE
                    price_diff = abs(curr_p - sl)
                    pos_size = risk_amt / price_diff if price_diff != 0 else 0
                    
                    st.warning(f"📏 **倉位建議**")
                    st.write(f"單筆風險金額: `${risk_amt:.0f}`")
                    st.write(f"建議下單量: **{pos_size:.4f}** 單位/手")
                    st.write(f"止損價: `{sl:.4f}` | 止盈價: `{curr_p+(curr_p-sl)*RR_TARGET:.4f}`")
                st.divider()
