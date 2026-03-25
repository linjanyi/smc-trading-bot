import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 初始化 ---
st.set_page_config(page_title="SMC Pro V46", layout="wide")
st_autorefresh(interval=60000, key="v46_sync") 
tw_tz = pytz.timezone('Asia/Taipei')

# --- 2. 數據對照 ---
crypto_info = {"BTC-USD": "比特幣", "ETH-USD": "乙太幣", "SOL-USD": "索拉納"}
forex_info = {"GC=F": "黃金期貨", "NQ=F": "納指100", "EURUSD=X": "歐美匯率"}

# --- 3. 核心歷史追蹤引擎 (強化統計功能) ---
@st.cache_data(ttl=60)
def get_detailed_history_v46(symbol):
    try:
        df = yf.download(symbol, period='15d', interval='1h', auto_adjust=True, progress=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        
        df['EMA'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
        
        bull = (df['Low'] > df['High'].shift(2)) & (df['Close'] > df['EMA'])
        bear = (df['High'] < df['Low'].shift(2)) & (df['Close'] < df['EMA'])
        
        history = []
        for i in range(len(df)-1, max(5, len(df)-120), -1):
            if bull.iloc[i] or bear.iloc[i]:
                entry_p = df['Close'].iloc[i]
                atr_v = df['ATR'].iloc[i]
                sl_dist = atr_v * 1.5
                
                if bull.iloc[i]:
                    type_str, sl, tp = "多單 📈", entry_p - sl_dist, entry_p + sl_dist * 2
                else:
                    type_str, sl, tp = "空單 📉", entry_p + sl_dist, entry_p - sl_dist * 2
                
                result = "⏳ 運行"
                for j in range(i+1, len(df)):
                    high, low = df['High'].iloc[j], df['Low'].iloc[j]
                    if bull.iloc[i]:
                        if low <= sl: result = "❌ 止損"; break
                        if high >= tp: result = "✅ 止盈"; break
                    else:
                        if high >= sl: result = "❌ 止損"; break
                        if low <= tp: result = "✅ 止盈"; break
                
                history.append({
                    "時間": df.index[i].strftime('%m-%d %H:%M'),
                    "品種": symbol,
                    "類型": type_str,
                    "進場價": round(entry_p, 2),
                    "結果": result
                })
        return {"df": df, "history": history}
    except: return None

# --- 4. UI 渲染 ---
st.title("🏹 SMC 全球量化終端 V46")

# 市場選擇
st.write("### 🔍 市場監控")
c_cols = st.columns(3)
active_c = [s for i, s in enumerate(crypto_info.keys()) if c_cols[i].checkbox(f"**{s}**", value=True)]
f_cols = st.columns(3)
active_f = [s for i, s in enumerate(forex_info.keys()) if f_cols[i].checkbox(f"**{s}**", value=True)]

all_history = []

# --- 5. 渲染矩陣 ---
def draw_v46(items):
    if not items: return
    st.divider()
    cols = st.columns(3)
    for i, s in enumerate(items):
        with cols[i % 3]:
            data = get_detailed_history_v46(s)
            if data:
                df, hist = data['df'], data['history']
                cp = float(df['Close'].iloc[-1])
                atr = float(df['ATR'].iloc[-1])
                ema = df['EMA'].iloc[-1]
                for h in hist: all_history.append(h)
                
                with st.container():
                    st.markdown(f"#### {s}")
                    st.write(f"當前價格: **{cp:,.2f}**")
                    
                    bull = (df['Low'].iloc[-1] - df['High'].iloc[-3]) > (atr*0.3)
                    bear = (df['High'].iloc[-3] - df['Low'].iloc[-1]) > (atr*0.3)
                    
                    if bull and cp > ema:
                        st.success("🔥 多單建議")
                        sl = cp - (atr*1.5); tp = cp + (cp-sl)*2
                        st.code(f"ENTRY: {cp:,.2f}\nSL: {sl:,.2f}\nTP: {tp:,.2f}")
                    elif bear and cp < ema:
                        st.error("📉 空單建議")
                        sl = cp + (atr*1.5); tp = cp - (sl-cp)*2
                        st.code(f"ENTRY: {cp:,.2f}\nSL: {sl:,.2f}\nTP: {tp:,.2f}")
                    else: st.info("🔎 監控結構中...")
            st.divider()

draw_v46(active_c + active_f)

# --- 6. 側邊欄：勝率統計與歷史表格 ---
with st.sidebar:
    st.header("📊 戰績統計 (5D)")
    if all_history:
        h_df = pd.DataFrame(all_history)
        # 計算勝率
        valid_trades = h_df[h_df['結果'] != "⏳ 運行"]
        if len(valid_trades) > 0:
            wins = len(valid_trades[valid_trades['結果'] == "✅ 止盈"])
            wr = (wins / len(valid_trades)) * 100
            st.metric("總平均勝率", f"{wr:.1f}%", f"總成交: {len(valid_trades)} 次")
        
        st.divider()
        st.subheader("📜 歷史進場點位")
        # 顯示詳細表格
        st.dataframe(
            h_df.sort_values(by="時間", ascending=False),
            column_config={
                "時間": st.column_config.TextColumn("時間"),
                "品種": st.column_config.TextColumn("品種"),
                "結果": st.column_config.TextColumn("結果"),
                "進場價": st.column_config.NumberColumn("進場價", format="%.2f")
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.write("數據加載中...")
