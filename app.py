import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 初始化 ---
st.set_page_config(page_title="SMC Wealth V47", layout="wide")
st_autorefresh(interval=60000, key="v47_sync") 
tw_tz = pytz.timezone('Asia/Taipei')

# --- 2. 數據對照 ---
crypto_info = {"BTC-USD": "比特幣", "ETH-USD": "乙太幣", "SOL-USD": "索拉納"}
forex_info = {"GC=F": "黃金期貨", "NQ=F": "納指100", "EURUSD=X": "歐美匯率"}

# --- 3. 核心追蹤引擎 (含損益計算) ---
@st.cache_data(ttl=60)
def get_detailed_history_v47(symbol, risk_p=1.0):
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
                sl_dist = df['ATR'].iloc[i] * 1.5
                
                if bull.iloc[i]:
                    type_str, sl, tp_final = "多單 📈", entry_p - sl_dist, entry_p + sl_dist * 3
                else:
                    type_str, sl, tp_final = "空單 📉", entry_p + sl_dist, entry_p - sl_dist * 3
                
                result = "⏳ 運行"
                profit = 0.0
                for j in range(i+1, len(df)):
                    h, l = df['High'].iloc[j], df['Low'].iloc[j]
                    if bull.iloc[i]:
                        if l <= sl: result = "❌ 止損"; profit = -risk_p; break
                        if h >= tp_final: result = "✅ 止盈"; profit = risk_p * 3; break
                    else:
                        if h >= sl: result = "❌ 止損"; profit = -risk_p; break
                        if l <= tp_final: result = "✅ 止盈"; profit = risk_p * 3; break
                
                history.append({
                    "時間": df.index[i].strftime('%m-%d %H:%M'),
                    "品種": symbol,
                    "類型": type_str,
                    "進場價": round(entry_p, 2),
                    "結果": result,
                    "獲利%": profit
                })
        return {"df": df, "history": history}
    except: return None

# --- 4. UI 渲染 ---
st.title("🏹 SMC 全球財富終端 V47")

with st.sidebar:
    st.header("⚙️ 設定")
    bal = st.number_input("總本金 (USD)", value=10000)
    user_risk = st.slider("每筆風險 (%)", 0.1, 5.0, 1.0)
    all_history = []

# 市場選擇
st.write("### 🔍 市場監控")
c_cols = st.columns(3)
active_c = [s for i, s in enumerate(crypto_info.keys()) if c_cols[i].checkbox(f"**{s}**", value=True)]
f_cols = st.columns(3)
active_f = [s for i, s in enumerate(forex_info.keys()) if f_cols[i].checkbox(f"**{s}**", value=True)]

# --- 5. 渲染矩陣 ---
def draw_v47(items):
    if not items: return
    st.divider()
    cols = st.columns(3)
    for i, s in enumerate(items):
        with cols[i % 3]:
            data = get_detailed_history_v47(s, user_risk)
            if data:
                df, hist = data['df'], data['history']
                cp = float(df['Close'].iloc[-1])
                atr = float(df['ATR'].iloc[-1])
                for h in hist: all_history.append(h)
                
                with st.container():
                    st.markdown(f"#### {s}")
                    st.write(f"現價: **{cp:,.2f}**")
                    
                    bull = (df['Low'].iloc[-1] - df['High'].iloc[-3]) > (atr*0.3)
                    bear = (df['High'].iloc[-3] - df['Low'].iloc[-1]) > (atr*0.3)
                    
                    if bull and cp > df['EMA'].iloc[-1]:
                        st.success("🔥 多單建議")
                        sl = cp - (atr*1.5)
                        dist = cp - sl
                        st.code(f"ENTRY: {cp:,.2f}\nSL: {sl:,.2f}\nTP1(1.5R): {cp+dist*1.5:,.2f}\nTP2(3.0R): {cp+dist*3:,.2f}")
                    elif bear and cp < df['EMA'].iloc[-1]:
                        st.error("📉 空單建議")
                        sl = cp + (atr*1.5)
                        dist = sl - cp
                        st.code(f"ENTRY: {cp:,.2f}\nSL: {sl:,.2f}\nTP1(1.5R): {cp-dist*1.5:,.2f}\nTP2(3.0R): {cp-dist*3:,.2f}")
                    else: st.info("🔎 監控結構中...")
            st.divider()

draw_v47(active_c + active_f)

# --- 6. 側邊欄：總盈虧與歷史紀錄 ---
with st.sidebar:
    st.header("📊 5D 戰績統計")
    if all_history:
        h_df = pd.DataFrame(all_history)
        valid_trades = h_df[h_df['結果'] != "⏳ 運行"]
        
        if len(valid_trades) > 0:
            total_prof = valid_trades['獲利%'].sum()
            wins = len(valid_trades[valid_trades['結果'] == "✅ 止盈"])
            wr = (wins / len(valid_trades)) * 100
            
            # 顯示總獲利 %
            color = "normal" if total_prof >= 0 else "inverse"
            st.metric("總預期淨利", f"{total_prof:+.2f}%", f"勝率 {wr:.1f}%")
            st.write(f"💰 預估收益: **${bal * (total_prof/100):,.2f}**")
        
        st.divider()
        st.subheader("📜 歷史明細")
        st.dataframe(h_df.sort_values(by="時間", ascending=False), hide_index=True, use_container_width=True)
