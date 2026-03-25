import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# --- 1. 配置 ---
st.set_page_config(page_title="SMC Pro V44", layout="wide")
st_autorefresh(interval=60000, key="v44_sync") 
tw_tz = pytz.timezone('Asia/Taipei')

# --- 2. 數據對照 ---
crypto_info = {"BTC-USD": "比特幣", "ETH-USD": "乙太幣", "SOL-USD": "索拉納"}
forex_info = {"GC=F": "黃金期貨", "NQ=F": "納指100", "EURUSD=X": "歐美匯率"}

# --- 3. 核心歷史輸贏追蹤引擎 ---
@st.cache_data(ttl=60)
def get_detailed_history_v44(symbol):
    try:
        df = yf.download(symbol, period='20d', interval='1h', auto_adjust=True, progress=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        
        df['EMA'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
        
        bull = (df['Low'] > df['High'].shift(2)) & (df['Close'] > df['EMA'])
        bear = (df['High'] < df['Low'].shift(2)) & (df['Close'] < df['EMA'])
        
        history = []
        # 掃描過去 5 天的紀錄以追蹤結果
        for i in range(len(df)-24, max(5, len(df)-120), -1):
            if bull.iloc[i] or bear.iloc[i]:
                entry_p = df['Close'].iloc[i]
                atr_v = df['ATR'].iloc[i]
                sl_dist = atr_v * 1.2
                
                if bull.iloc[i]:
                    type_str, sl, tp = "多單 📈", entry_p - sl_dist, entry_p + sl_dist * 2
                else:
                    type_str, sl, tp = "空單 📉", entry_p + sl_dist, entry_p - sl_dist * 2
                
                # 追蹤後續 K 線看結果
                result = "⏳ 運行中"
                for j in range(i+1, len(df)):
                    high, low = df['High'].iloc[j], df['Low'].iloc[j]
                    if bull.iloc[i]:
                        if low <= sl: {result := "❌ 止損"}; break
                        if high >= tp: {result := "✅ 止盈"}; break
                    else:
                        if high >= sl: {result := "❌ 止損"}; break
                        if low <= tp: {result := "✅ 止盈"}; break
                
                history.append({
                    "時間": df.index[i].strftime('%m-%d %H:%M'),
                    "品種": symbol,
                    "類型": type_str,
                    "進場價": f"{entry_p:,.2f}",
                    "結果": result
                })
        return {"df": df, "history": history}
    except: return None

# --- 4. UI 渲染 ---
st.title("🏹 SMC 全球量化終端 V44")

with st.sidebar:
    st.header("⚙️ 設定")
    bal = st.number_input("總本金 (USD)", value=10000)
    risk_pct = st.slider("單筆風險 (%)", 0.1, 5.0, 1.0)
    st.divider()
    st.subheader("📜 歷史輸贏紀錄 (最後 5 天)")
    all_history = []

# 市場選擇
st.write("### 🔍 市場監控")
c_cols = st.columns(3)
active_c = [s for i, s in enumerate(crypto_info.keys()) if c_cols[i].checkbox(f"{s}", value=True)]
f_cols = st.columns(3)
active_f = [s for i, s in enumerate(forex_info.keys()) if f_cols[i].checkbox(f"{s}", value=True)]

# --- 5. 渲染矩陣與結果收集 ---
def draw_v44(items, is_c):
    if not items: return
    cols = st.columns(3)
    for i, s in enumerate(items):
        with cols[i % 3]:
            data = get_detailed_history_v44(s)
            if data:
                df = data['df']
                cp = float(df['Close'].iloc[-1])
                atr = float(df['ATR'].iloc[-1])
                ema = df['EMA'].iloc[-1]
                
                # 收集所有歷史到側邊欄
                for h in data['history']: all_history.append(h)
                
                with st.container():
                    st.markdown(f"#### {s}")
                    st.write(f"當前價格: **{cp:,.2f}**")
                    
                    bull = (df['Low'].iloc[-1] - df['High'].iloc[-3]) > (atr*0.3)
                    bear = (df['High'].iloc[-3] - df['Low'].iloc[-1]) > (atr*0.3)
                    
                    if bull and cp > ema:
                        st.toast(f"🔥 {s} 出現多單訊號！", icon="📈")
                        st.success("🔥 多單建議")
                        sl = cp - (atr*1.2)
                        st.code(f"SL:{sl:,.2f} | TP:{cp+(cp-sl)*2:,.2f}")
                    elif bear and cp < ema:
                        st.toast(f"📉 {s} 出現空單訊號！", icon="📉")
                        st.error("📉 空單建議")
                        sl = cp + (atr*1.2)
                        st.code(f"SL:{sl:,.2f} | TP:{cp-(sl-cp)*2:,.2f}")
                    else: st.info("🔎 監控結構中...")
            st.divider()

draw_v44(active_c, True)
draw_v44(active_f, False)

# --- 6. 側邊欄顯示格式化表格 ---
with st.sidebar:
    if all_history:
        h_df = pd.DataFrame(all_history).sort_values(by="時間", ascending=False)
        # 根據結果著色 (Streamlit Table 特色)
        st.dataframe(h_df, use_container_width=True, hide_index=True)
    else:
        st.write("掃描歷史中...")
