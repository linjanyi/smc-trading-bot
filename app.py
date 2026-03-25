import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 配置 ---
st.set_page_config(page_title="SMC Pro V51", layout="wide")
st_autorefresh(interval=60000, key="v51_refresh") 
tw_tz = pytz.timezone('Asia/Taipei')

# --- 2. 數據對照 ---
crypto_info = {"BTC-USD": "比特幣", "ETH-USD": "乙太幣", "SOL-USD": "索拉納"}
forex_info = {"GC=F": "黃金期貨", "NQ=F": "納指100", "EURUSD=X": "歐美匯率", "USDJPY=X": "美日匯率"}
all_options = {**crypto_info, **forex_info}

# --- 3. 核心追蹤引擎 (含雙 TP 邏輯) ---
@st.cache_data(ttl=60)
def get_detailed_v51(symbol, risk_p=1.0):
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
                entry_p, sl_dist = df['Close'].iloc[i], df['ATR'].iloc[i] * 1.5
                res = "⏳ 運行"; prof = 0.0
                
                # 判定邏輯以 TP2 (3.0R) 為最終獲利基準
                sl, tp_final = (entry_p - sl_dist, entry_p + sl_dist*3.0) if bull.iloc[i] else (entry_p + sl_dist, entry_p - sl_dist*3.0)
                
                for j in range(i+1, len(df)):
                    h, l = df['High'].iloc[j], df['Low'].iloc[j]
                    if bull.iloc[i]:
                        if l <= sl: res = "❌ 止損"; prof = -risk_p; break
                        if h >= tp_final: res = "✅ 止盈"; prof = risk_p*3.0; break
                    else:
                        if h >= sl: res = "❌ 止損"; prof = -risk_p; break
                        if l <= tp_final: res = "✅ 止盈"; prof = risk_p*3.0; break
                
                history.append({
                    "時間": df.index[i].strftime('%m-%d %H:%M'),
                    "品種": symbol,
                    "類型": "多單 📈" if bull.iloc[i] else "空單 📉",
                    "進場價": round(entry_p, 2),
                    "結果": res,
                    "預估損益%": prof
                })
        
        v_trades = [h for h in history if h['結果'] != "⏳ 運行"]
        wr = (len([h for h in v_trades if "✅" in h['結果']]) / len(v_trades) * 100) if v_trades else 0
        
        return {"df": df, "history": history, "wr": wr}
    except: return None

# --- 4. UI 介面 ---
st.title("🏹 SMC 終極量化終端 V51")

# --- 橫向打勾區 ---
st.write("### 🔍 市場監控 (手動選擇)")
chk_cols = st.columns(len(all_options))
active_symbols = []
for i, (sym, name) in enumerate(all_options.items()):
    if chk_cols[i].checkbox(f"**{sym}**", value=(sym in ["BTC-USD", "GC=F"])):
        active_symbols.append(sym)

# 側邊欄設定
with st.sidebar:
    st.header("⚙️ 參數設定")
    bal = st.number_input("本金 (USD)", value=10000)
    risk_pct = st.slider("單筆風險 (%)", 0.1, 5.0, 1.0)
    st.divider()
    st.write("💡 **雙止盈策略**")
    st.caption("TP1 (1.5R): 減倉位\nTP2 (3.0R): 目標位")

# --- 5. 渲染即時訊號 ---
total_history = []

if active_symbols:
    st.divider()
    sig_cols = st.columns(3)
    for i, s in enumerate(active_symbols):
        data = get_detailed_v51(s, risk_pct)
        if data:
            df, hist, wr = data['df'], data['history'], data['wr']
            for h in hist: total_history.append(h)
            
            cp, atr, ema = float(df['Close'].iloc[-1]), float(df['ATR'].iloc[-1]), df['EMA'].iloc[-1]
            
            with sig_cols[i % 3]:
                st.markdown(f"#### {s} ({all_options[s]})")
                st.metric("5D 勝率", f"{wr:.1f}%")
                
                bull = (df['Low'].iloc[-1] - df['High'].iloc[-3]) > (atr*0.3) and cp > ema
                bear = (df['High'].iloc[-3] - df['Low'].iloc[-1]) > (atr*0.3) and cp < ema
                
                if bull:
                    st.success("🔥 多單建議")
                    sl = cp - (atr*1.5); dist = cp - sl
                    st.code(f"ENTRY: {cp:,.2f}\nSL: {sl:,.2f}\nTP1(1.5R): {cp+dist*1.5:,.2f}\nTP2(3.0R): {cp+dist*3.0:,.2f}")
                elif bear:
                    st.error("📉 空單建議")
                    sl = cp + (atr*1.5); dist = sl - cp
                    st.code(f"ENTRY: {cp:,.2f}\nSL: {sl:,.2f}\nTP1(1.5R): {cp-dist*1.5:,.2f}\nTP2(3.0R): {cp-dist*3.0:,.2f}")
                else:
                    st.info("🔎 監控結構中...")
                st.write(f"現價: **{cp:,.2f}**")
        st.divider()

# --- 6. 歷史紀錄大表格 ---
st.write("### 📜 歷史戰績紀錄 (包含進場價格)")
if total_history:
    h_df = pd.DataFrame(total_history).sort_values(by="時間", ascending=False)
    # 統計
    net_profit = h_df['預估損益%'].sum()
    st.subheader(f"💰 總預期累積收益: {net_profit:+.2f}%")
    
    # 格式化顯示表格
    st.dataframe(h_df, hide_index=True, use_container_width=True)
else:
    st.info("請勾選品種以顯示數據。")
