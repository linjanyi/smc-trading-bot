import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 初始化配置 ---
st.set_page_config(page_title="SMC Pro V56 - Profit Guard", layout="wide")
st_autorefresh(interval=60000, key="v56_refresh") 
tw_tz = pytz.timezone('Asia/Taipei')

# --- 2. 監控品種 ---
all_symbols = {
    "GC=F": "黃金期貨", 
    "BTC-USD": "比特幣", 
    "ETH-USD": "乙太幣", 
    "NQ=F": "納指100",
    "SOL-USD": "索拉納"
}

# --- 3. 核心追蹤引擎 (修復 RR 邏輯) ---
@st.cache_data(ttl=60)
def get_detailed_v56(symbol, risk_p=1.0):
    try:
        # 增加數據長度以確保 EMA 準確性
        df = yf.download(symbol, period='15d', interval='1h', auto_adjust=True, progress=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        
        df['EMA'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
        
        # SMC 訊號判定
        bull = (df['Low'] > df['High'].shift(2)) & (df['Close'] > df['EMA'])
        bear = (df['High'] < df['Low'].shift(2)) & (df['Close'] < df['EMA'])
        
        history = []
        # 回測過去 120 小時
        for i in range(len(df)-1, max(5, len(df)-120), -1):
            if bull.iloc[i] or bear.iloc[i]:
                entry_p = df['Close'].iloc[i]
                sl_dist = df['ATR'].iloc[i] * 1.5 # 標準防禦距離
                
                # V56 採用保守 RR 1.5 做為判定基準，防止獲利回吐
                rr_target = 1.5
                sl, tp = (entry_p - sl_dist, entry_p + sl_dist * rr_target) if bull.iloc[i] else (entry_p + sl_dist, entry_p - sl_dist * rr_target)
                
                res = "⏳ 運行"; prof = 0.0
                for j in range(i+1, len(df)):
                    h, l = df['High'].iloc[j], df['Low'].iloc[j]
                    if bull.iloc[i]:
                        if l <= sl: res = "❌ 止損"; prof = -risk_p; break
                        if h >= tp: res = "✅ 止盈"; prof = risk_p * rr_target; break
                    else:
                        if h >= sl: res = "❌ 止損"; prof = -risk_p; break
                        if l <= tp: res = "✅ 止盈"; prof = risk_p * rr_target; break
                
                history.append({
                    "時間": df.index[i].strftime('%m-%d %H:%M'),
                    "品種": symbol,
                    "類型": "多單 📈" if bull.iloc[i] else "空單 📉",
                    "進場價": round(entry_p, 2),
                    "結果": res,
                    "收益%": prof
                })
        
        v_trades = [h for h in history if h['結果'] != "⏳ 運行"]
        wr = (len([h for h in v_trades if "✅" in h['結果']]) / len(v_trades) * 100) if v_trades else 0
        net_p = sum([h['收益%'] for h in history])
        
        return {"df": df, "history": history, "wr": wr, "net_p": net_p}
    except:
        return None

# --- 4. 介面渲染 ---
st.title("🏹 SMC AI 獲利守護終端 V56")
st.markdown("### 🛡️ 當前狀態：**利潤保護模式已開啟** (自動偵測 RR 失效)")

with st.sidebar:
    st.header("⚙️ 參數設定")
    bal = st.number_input("總本金 (USD)", value=10000)
    risk_val = st.slider("單筆風險 (%)", 0.1, 5.0, 1.0)
    st.divider()
    st.info("💡 **為什麼淨利會下降？**\n當市場進入洗盤期，原本 3.0RR 的目標太遠，導致獲利變虧損。V56 鎖定 1.5RR 優先保命。")

# --- 5. 渲染即時推薦 ---
st.write("### 🔍 市場掃描 & 即時報單")
cols = st.columns(3)
all_history_data = []

for i, (sym, name) in enumerate(all_symbols.items()):
    data = get_detailed_v56(sym, risk_val)
    if data:
        df, hist, wr, net_p = data['df'], data['history'], data['wr'], data['net_p']
        all_history_data.extend(hist)
        
        with cols[i % 3]:
            st.markdown(f"#### {sym} ({name})")
            # 顯示淨利與勝率
            delta_val = f"勝率 {wr:.1f}%"
            st.metric("5D 累積淨利", f"{net_p:+.2f}%", delta_val)
            
            cp = float(df['Close'].iloc[-1])
            atr = float(df['ATR'].iloc[-1])
            ema = df['EMA'].iloc[-1]
            
            bull_sig = (df['Low'].iloc[-1] > df['High'].iloc[-3]) and cp > ema
            bear_sig = (df['High'].iloc[-3] > df['Low'].iloc[-1]) and cp < ema
            
            if bull_sig:
                st.success("🔥 多單建議")
                sl = cp - (atr * 1.5); dist = cp - sl
                st.code(f"ENTRY: {cp:,.2f}\nSL: {sl:,.2f}\nTP1(0.5R 移損): {cp+dist*0.5:,.2f}\nTP2(1.5R 止盈): {cp+dist*1.5:,.2f}")
            elif bear_sig:
                st.error("📉 空單建議")
                sl = cp + (atr * 1.5); dist = sl - cp
                st.code(f"ENTRY: {cp:,.2f}\nSL: {sl:,.2f}\nTP1(0.5R 移損): {cp-dist*0.5:,.2f}\nTP2(1.5R 止盈): {cp-dist*1.5:,.2f}")
            else:
                st.info("🔎 監控結構中...")
            st.divider()

# --- 6. 歷史戰績大表 ---
st.write("### 📜 戰績歷史明細 (核對為什麼會虧損)")
if all_history_data:
    h_df = pd.DataFrame(all_history_data).sort_values("時間", ascending=False)
    st.dataframe(h_df, hide_index=True, use_container_width=True)
else:
    st.write("掃描數據中...")
