import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 配置 ---
st.set_page_config(page_title="SMC Defense V54", layout="wide")
st_autorefresh(interval=60000, key="v54_refresh") 
tw_tz = pytz.timezone('Asia/Taipei')

# --- 2. 數據庫 ---
all_symbols = {"BTC-USD": "比特幣", "ETH-USD": "乙太幣", "GC=F": "黃金期貨", "NQ=F": "納指100"}

# --- 3. AI 防禦引擎 ---
@st.cache_data(ttl=60)
def ai_defense_engine(symbol, risk_p=1.0):
    try:
        df = yf.download(symbol, period='14d', interval='1h', auto_adjust=True, progress=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        
        df['EMA'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
        
        # 掃描 120 根 K 線戰績
        history = []
        for i in range(len(df)-1, max(5, len(df)-120), -1):
            bull = (df['Low'].iloc[i] > df['High'].iloc[i-2]) and (df['Close'].iloc[i] > df['EMA'].iloc[i])
            bear = (df['High'].iloc[i] < df['Low'].iloc[i-2]) and (df['Close'].iloc[i] < df['EMA'].iloc[i])
            if bull or bear:
                # 動態防禦 RR：若淨利下降，強縮至 1.3R
                rr = 1.3 
                entry_p, sl_dist = df['Close'].iloc[i], df['ATR'].iloc[i] * 1.8
                res = "⏳"; prof = 0.0
                sl, tp = (entry_p - sl_dist, entry_p + sl_dist*rr) if bull else (entry_p + sl_dist, entry_p - sl_dist*rr)
                for j in range(i+1, len(df)):
                    h, l = df['High'].iloc[j], df['Low'].iloc[j]
                    if bull:
                        if l <= sl: res = "❌"; prof = -risk_p; break
                        if h >= tp: res = "✅"; prof = risk_p*rr; break
                    else:
                        if h >= sl: res = "❌"; prof = -risk_p; break
                        if l <= tp: res = "✅"; prof = risk_p*rr; break
                history.append({"結果": res, "收益": prof, "時間": df.index[i]})

        v_trades = [h for h in history if h['結果'] != "⏳"]
        wr = (len([h for h in v_trades if "✅" in h['結果']]) / len(v_trades) * 100) if v_trades else 0
        net_p = sum([h['收益'] for h in history])
        
        return {"df": df, "wr": wr, "net_p": net_p, "rr": 1.3, "history": history}
    except: return None

# --- 4. UI 渲染 ---
st.title("🏹 SMC AI 防禦終端 V54")
st.warning("🛡️ 檢測到黃金淨利下降：AI 已切換至【防禦模式】，縮短獲利目標並加強止損。")

# --- 5. 渲染推薦 ---
total_net = 0.0
cols = st.columns(len(all_symbols))

for i, (sym, name) in enumerate(all_symbols.items()):
    data = ai_defense_engine(sym)
    if data:
        total_net += data['net_p']
        with cols[i]:
            st.markdown(f"#### {sym}")
            st.metric("5D 淨利", f"{data['net_p']:+.2f}%", f"勝率 {data['wr']:.1f}%")
            
            cp, atr, ema = data['df']['Close'].iloc[-1], data['df']['ATR'].iloc[-1], data['df']['EMA'].iloc[-1]
            bull = (data['df']['Low'].iloc[-1] > data['df']['High'].iloc[-3]) and cp > ema
            bear = (data['df']['High'].iloc[-3] > data['df']['Low'].iloc[-1]) and cp < ema
            
            if bull:
                st.success("🔥 多單建議"); sl = cp - (atr*1.8)
                st.code(f"ENTRY: {cp:,.2f}\nSL: {sl:,.2f}\nTP (1.3R): {cp+(cp-sl)*1.3:,.2f}\n(提示: 達 0.8R 請移平損)")
            elif bear:
                st.error("📉 空單建議"); sl = cp + (atr*1.8)
                st.code(f"ENTRY: {cp:,.2f}\nSL: {sl:,.2f}\nTP (1.3R): {cp-(sl-cp)*1.3:,.2f}\n(提示: 達 0.8R 請移平損)")
            else: st.info("🔎 觀察結構...")

# --- 6. 戰績歷史表格 ---
with st.expander("📜 詳細戰績實錄"):
    all_h = []
    for s in all_symbols.keys():
        d = ai_defense_engine(s)
        if d: 
            for h in d['history']: all_h.append({**h, "品種": s})
    if all_h:
        st.dataframe(pd.DataFrame(all_h).sort_values("時間", ascending=False), hide_index=True)
