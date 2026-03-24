import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 頁面基礎設置 ---
st.set_page_config(page_title="SMC Intelligence Terminal", layout="wide")
st_autorefresh(interval=60000, key="global_scan")

# --- 2. 側邊欄：專業風控設定 ---
with st.sidebar:
    st.header("👤 帳戶個人化設定")
    balance = st.number_input("您的總本金 (USD)", value=10000, step=1000)
    risk_pct = st.slider("單筆想虧損幾 % ?", 0.5, 5.0, 1.0) / 100
    st.divider()
    st.header("🌍 市場選擇")
    cryptos = st.multiselect("加密貨幣", ["BTC-USD", "ETH-USD", "SOL-USD"], default=["BTC-USD"])
    forex = st.multiselect("外匯/黃金/美指", ["GC=F", "EURUSD=X", "USDJPY=X", "NQ=F"], default=["GC=F"])
    total_list = cryptos + forex

# --- 3. 分析引擎 ---
@st.cache_data(ttl=600)
def get_analysis(symbol):
    try:
        d1 = yf.download(symbol, period='30d', interval='1h', auto_adjust=True, progress=False)
        d4 = yf.download(symbol, period='60d', interval='4h', auto_adjust=True, progress=False)
        for d in [d1, d4]:
            if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
        
        # 回測勝率
        d1['EMA200'] = d1['Close'].ewm(span=200, adjust=False).mean()
        d1['ATR'] = (d1['High'] - d1['Low']).rolling(14).mean()
        bull = (d1['Low'] > d1['High'].shift(2)) & (d1['Close'] > d1['EMA200'])
        bear = (d1['High'] < d1['Low'].shift(2)) & (d1['Close'] < d1['EMA200'])
        d1['Sig'] = 0
        d1.loc[bull, 'Sig'], d1.loc[bear, 'Sig'] = 1, -1
        rets = (d1['Sig'].shift(1) * d1['Close'].pct_change()).dropna()
        wr = (len(rets[rets > 0]) / len(rets[rets != 0]) * 100) if len(rets[rets != 0]) > 0 else 0
        
        # 4H 趨勢
        d4['EMA'] = d4['Close'].ewm(span=200, adjust=False).mean()
        htf = 1 if d4['Close'].iloc[-1] > d4['EMA'].iloc[-1] else -1
        
        return {"df": d1, "wr": wr, "htf": htf}
    except: return None

# --- 4. 介面渲染 ---
st.title("🏹 SMC 量化導航終端")
st.info(f"💡 目前設定：每筆單虧損預算 `${balance * risk_pct:.0f}` USD | 掃描時間: {datetime.now().strftime('%H:%M:%S')}")

if not total_list:
    st.warning("請在左側選單勾選監控目標。")
else:
    cols = st.columns(3)
    for i, sym in enumerate(total_list):
        with cols[i % 3]:
            res = get_analysis(sym)
            if res:
                df, wr, htf = res['df'], res['wr'], res['htf']
                last = df.iloc[-1]
                curr_p, atr = last['Close'], last['ATR']
                
                st.subheader(sym)
                st.write(f"📊 30D 勝率: `{wr:.1f}%` | 4H 趨勢: `{'📈 多' if htf==1 else '📉 空'}`")
                
                # 訊號判斷
                bull_g = last['Low'] - df.iloc[-3]['High']
                bear_g = df.iloc[-3]['Low'] - last['High']
                
                # 倉位計算與顯示
                if bull_g > (atr*0.5) and curr_p > last['EMA200']:
                    st.success("🔥 強力共振多單" if htf==1 else "⚠️ 逆勢反彈買入")
                    sl = curr_p - (atr * 2)
                    size = (balance * risk_pct) / abs(curr_p - sl)
                    st.write(f"👉 **建議下單量: {size:.4f}**")
                    st.write(f"🛑 止損: `{sl:.4f}` | 🎯 止盈: `{curr_p+(curr_p-sl)*3:.4f}`")
                elif bear_g > (atr*0.5) and curr_p < last['EMA200']:
                    st.error("🔥 強力共振空單" if htf==-1 else "⚠️ 逆勢回測賣出")
                    sl = curr_p + (atr * 2)
                    size = (balance * risk_pct) / abs(curr_p - sl)
                    st.write(f"👉 **建議下單量: {size:.4f}**")
                    st.write(f"🛑 止損: `{sl:.4f}` | 🎯 止盈: `{curr_p-(sl-curr_p)*3:.4f}`")
                else:
                    st.info("🔎 掃描中...")
                st.divider()
