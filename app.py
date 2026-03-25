import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 配置 ---
st.set_page_config(page_title="SMC AI-Adaptive V49", layout="wide")
st_autorefresh(interval=60000, key="v49_sync") 
tw_tz = pytz.timezone('Asia/Taipei')

# --- 2. 數據對照 ---
crypto_info = {"BTC-USD": "比特幣", "ETH-USD": "乙太幣", "SOL-USD": "索拉納"}
forex_info = {"GC=F": "黃金期貨", "NQ=F": "納指100", "EURUSD=X": "歐美匯率"}

# --- 3. AI 診斷引擎 ---
@st.cache_data(ttl=60)
def ai_diagnostic_v49(symbol, risk_p=1.0):
    try:
        df = yf.download(symbol, period='15d', interval='1h', auto_adjust=True, progress=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        
        df['EMA'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
        
        # 掃描歷史戰績
        bull = (df['Low'] > df['High'].shift(2)) & (df['Close'] > df['EMA'])
        bear = (df['High'] < df['Low'].shift(2)) & (df['Close'] < df['EMA'])
        
        history = []
        for i in range(len(df)-1, max(5, len(df)-120), -1):
            if bull.iloc[i] or bear.iloc[i]:
                entry_p, sl_dist = df['Close'].iloc[i], df['ATR'].iloc[i] * 1.5
                res = "⏳"; prof = 0.0
                # 預設模擬 RR 2.0
                sl, tp = (entry_p - sl_dist, entry_p + sl_dist*2) if bull.iloc[i] else (entry_p + sl_dist, entry_p - sl_dist*2)
                for j in range(i+1, len(df)):
                    h, l = df['High'].iloc[j], df['Low'].iloc[j]
                    if bull.iloc[i]:
                        if l <= sl: res = "❌"; prof = -risk_p; break
                        if h >= tp: res = "✅"; prof = risk_p*2; break
                    else:
                        if h >= sl: res = "❌"; prof = -risk_p; break
                        if l <= tp: res = "✅"; prof = risk_p*2; break
                history.append({"結果": res, "獲利": prof})

        # --- AI 決策邏輯 ---
        total = len([h for h in history if h['結果'] != "⏳"])
        wins = len([h for h in history if h['結果'] == "✅"])
        wr = (wins / total * 100) if total > 0 else 0
        net_p = sum([h['獲利'] for h in history])

        # 自動調整 RR
        suggested_rr = 3.0 if wr > 45 else (1.5 if wr < 30 else 2.0)
        status = "🟢 推薦交易" if wr >= 35 else ("🟡 震盪觀望" if wr >= 20 else "🔴 強烈避開")
        
        return {"df": df, "wr": wr, "net_p": net_p, "rr": suggested_rr, "status": status, "history": history}
    except: return None

# --- 4. UI 渲染 ---
st.title("🏹 SMC AI 汰弱留強終端 V49")
st.info("🤖 AI 已啟動：自動根據各品種近期勝率調整 RR 並標註交易風險。")

with st.sidebar:
    st.header("📊 全局戰績統計")
    all_p = 0.0
    all_win_list = []

# --- 5. 渲染矩陣 ---
st.write("### 🔍 AI 市場掃描")
all_symbols = {**crypto_info, **forex_info}
cols = st.columns(3)

for i, (sym, name) in enumerate(all_symbols.items()):
    with cols[i % 3]:
        data = ai_diagnostic_v49(sym)
        if data:
            df, wr, net_p, rr, status = data['df'], data['wr'], data['net_p'], data['rr'], data['status']
            all_p += net_p
            all_win_list.append(wr)
            
            cp, atr, ema = float(df['Close'].iloc[-1]), float(df['ATR'].iloc[-1]), df['EMA'].iloc[-1]
            
            with st.container():
                # AI 標籤顯示
                st.markdown(f"#### {sym} ({name}) {status}")
                st.write(f"📊 勝率: **{wr:.1f}%** | AI 推薦 RR: **{rr}**")
                
                if "🔴" in status:
                    st.warning("該品種近期行情混亂，AI 建議停止操作以保護資金。")
                else:
                    bull = (df['Low'].iloc[-1] - df['High'].iloc[-3]) > (atr*0.3) and cp > ema
                    bear = (df['High'].iloc[-3] - df['Low'].iloc[-1]) > (atr*0.3) and cp < ema
                    
                    if bull:
                        st.success("🔥 AI 多單建議")
                        sl = cp - (atr*1.5); tp = cp + (cp-sl)*rr
                        st.code(f"SL: {sl:,.2f} | TP: {tp:,.2f}")
                    elif bear:
                        st.error("📉 AI 空單建議")
                        sl = cp + (atr*1.5); tp = cp - (sl-cp)*rr
                        st.code(f"SL: {sl:,.2f} | TP: {tp:,.2f}")
                    else: st.info("🔎 結構掃描中...")
        st.divider()

# --- 6. 側邊欄總結 ---
with st.sidebar:
    avg_wr = sum(all_win_list)/len(all_win_list) if all_win_list else 0
    st.metric("5D 總預計淨利", f"{all_p:+.2f}%", f"平均勝率 {avg_wr:.1f}%")
    st.write("---")
    st.write("💡 **AI 診斷：**")
    if all_p > 0: st.write("目前行情適合 SMC 策略，建議關注「🟢 推薦交易」品種。")
    else: st.write("市場波動劇烈，建議縮小倉位或只操作黃金。")
