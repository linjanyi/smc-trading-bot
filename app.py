import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
import base64
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# --- 1. 配置與音訊準備 ---
st.set_page_config(page_title="SMC Pro V43", layout="wide")
st_autorefresh(interval=60000, key="v43_sync") 
tw_tz = pytz.timezone('Asia/Taipei')

# 準備提示音 (使用 Base64 編碼，避免外部連結失效)
def play_notification():
    # 這是一個簡單的系統嗶聲 Base64
    audio_html = """
        <audio autoplay="true" src="data:audio/wav;base64,UklGRl9vT19XQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YTdvT18AAACAgICAgICAgICA"></audio>
    """
    st.markdown(audio_html, unsafe_allow_html=True)

# --- 2. 數據對照表 ---
crypto_info = {"BTC-USD": "比特幣", "ETH-USD": "乙太幣", "SOL-USD": "索拉納"}
forex_info = {"GC=F": "黃金期貨", "NQ=F": "納指100", "EURUSD=X": "歐美匯率"}

# --- 3. 核心歷史紀錄引擎 ---
@st.cache_data(ttl=60)
def get_recent_history_v43(symbol):
    try:
        df = yf.download(symbol, period='15d', interval='1h', auto_adjust=True, progress=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        
        df['EMA'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
        
        # 捕捉歷史訊號
        bull = (df['Low'] > df['High'].shift(2)) & (df['Close'] > df['EMA'])
        bear = (df['High'] < df['Low'].shift(2)) & (df['Close'] < df['EMA'])
        
        history = []
        # 掃描過去 48 小時的 K 線
        for i in range(len(df)-1, max(0, len(df)-48), -1):
            if bull.iloc[i]:
                history.append({"時間": df.index[i].strftime('%m-%d %H:%M'), "類型": "多單 📈", "價格": round(df['Close'].iloc[i], 2)})
            if bear.iloc[i]:
                history.append({"時間": df.index[i].strftime('%m-%d %H:%M'), "類型": "空單 📉", "價格": round(df['Close'].iloc[i], 2)})
        
        return {"df": df, "history": history}
    except: return None

# --- 4. 介面渲染 ---
st.title("🏹 SMC 全球量化終端 V43")
st.warning("🔔 提示：請先在頁面任意處點擊一下，以啟動瀏覽器音訊通知權限。")

# 側邊欄設定
with st.sidebar:
    st.header("⚙️ 設定")
    bal = st.number_input("總本金 (USD)", value=10000)
    risk_pct = st.slider("單筆風險 (%)", 0.1, 5.0, 1.0)
    st.divider()
    st.subheader("📜 近期成交日誌")
    # 合併所有選中品種的歷史
    full_log = []

# 市場選擇
st.write("### 🔍 市場監控")
c_cols = st.columns(3)
active_c = [s for i, s in enumerate(crypto_info.keys()) if c_cols[i].checkbox(f"{s}", value=True)]
f_cols = st.columns(3)
active_f = [s for i, s in enumerate(forex_info.keys()) if f_cols[i].checkbox(f"{s}", value=True)]

# --- 5. 渲染與訊號偵測 ---
def draw_v43(items, is_c):
    if not items: return
    cols = st.columns(3)
    for i, s in enumerate(items):
        with cols[i % 3]:
            data = get_recent_history_v43(s)
            if data:
                df = data['df']
                cp = float(df['Close'].iloc[-1])
                ema = df['EMA'].iloc[-1]
                atr = float(df['ATR'].iloc[-1])
                
                # 收集日誌
                for entry in data['history']:
                    full_log.append({**entry, "品種": s})
                
                with st.container():
                    st.markdown(f"#### {s}")
                    st.write(f"當前價格: **{cp:,.2f}**")
                    
                    bull = (df['Low'].iloc[-1] - df['High'].iloc[-3]) > (atr*0.3)
                    bear = (df['High'].iloc[-3] - df['Low'].iloc[-1]) > (atr*0.3)
                    
                    if bull and cp > ema:
                        st.success("🔥 新多單訊號"); play_notification()
                        sl = cp - (atr*1.2)
                        st.code(f"SL:{sl:,.2f} | TP:{cp+(cp-sl)*2:,.2f}")
                    elif bear and cp < ema:
                        st.error("📉 新空單訊號"); play_notification()
                        sl = cp + (atr*1.2)
                        st.code(f"SL:{sl:,.2f} | TP:{cp-(sl-cp)*2:,.2f}")
                    else: st.info("🔎 結構觀察中...")
            st.divider()

draw_v43(active_c, True)
draw_v43(active_f, False)

# --- 6. 側邊欄歷史紀錄顯示 ---
with st.sidebar:
    if full_log:
        log_df = pd.DataFrame(full_log).sort_values(by="時間", ascending=False)
        st.table(log_df.head(10)) # 顯示最近 10 筆
    else:
        st.write("目前尚無成交紀錄。")
