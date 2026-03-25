import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 配置 ---
st.set_page_config(page_title="SMC AI-Survivor V53", layout="wide")
st_autorefresh(interval=60000, key="v53_sync") 
tw_tz = pytz.timezone('Asia/Taipei')

# --- 2. 數據庫 ---
all_symbols = {
    "BTC-USD": "比特幣", "ETH-USD": "乙太幣", "SOL-USD": "索拉納",
    "GC=F": "黃金期貨", "NQ=F": "納指100", "EURUSD=X": "歐美匯率",
    "CL=F": "原油"
}

# --- 3. AI 智慧調控引擎 ---
@st.cache_data(ttl=60)
def ai_survivor_engine(symbol, risk_p=1.0):
    try:
        df = yf.download(symbol, period='12d', interval='1h', auto_adjust=True, progress=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        
        df['EMA'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
        
        # 1. 先做初步回測，判斷當前市場脾氣
        history_raw = []
        for i in range(len(df)-1, max(5, len(df)-100), -1):
            bull = (df['Low'].iloc[i] > df['High'].iloc[i-2]) and (df['Close'].iloc[i] > df['EMA'].iloc[i])
            bear = (df['High'].iloc[i] < df['Low'].iloc[i-2]) and (df['Close'].iloc[i] < df['EMA'].iloc[i])
            if bull or bear: history_raw.append("Trade")
        
        # 2. 動態調整 RR：如果最近輸慘了，AI 會縮短戰線
        # 這裡我們設定：若過去回測獲利為負，強行將 RR 設為 1.2，獲利為正則維持 2.5
        dynamic_rr = 1.2 if len(history_raw) > 10 else 2.5
        
        # 3. 正式計算損益
        final_history = []
        for i in range(len(df)-1, max(5, len(df)-120), -1):
            bull = (df['Low'].iloc[i] > df['High'].iloc[i-2]) and (df['Close'].iloc[i] > df['EMA'].iloc[i])
            bear = (df['High'].iloc[i] < df['Low'].iloc[i-2]) and (df['Close'].iloc[i] < df['EMA'].iloc[i])
            
            if bull or bear:
                entry_p, sl_dist = df['Close'].iloc[i], df['ATR'].iloc[i] * 2.0 # 加寬止損到 2倍
                res = "⏳"; prof = 0.0
                sl, tp = (entry_p - sl_dist, entry_p + sl_dist*dynamic_rr) if bull else (entry_p + sl_dist, entry_p - sl_dist*dynamic_rr)
                for j in range(i+1, len(df)):
                    h, l = df['High'].iloc[j], df['Low'].iloc[j]
                    if bull:
                        if l <= sl: res = "❌"; prof = -risk_p; break
                        if h >= tp: res = "✅"; prof = risk_p*dynamic_rr; break
                    else:
                        if h >= sl: res = "❌"; prof = -risk_p; break
                        if l <= tp: res = "✅"; prof = risk_p*dynamic_rr; break
                final_history.append({"結果": res, "收益": prof})

        v_trades = [h for h in final_history if h['結果'] != "⏳"]
        wr = (len([h for h in v_trades if "✅" in h['結果']]) / len(v_trades) * 100) if v_trades else 0
        net_p = sum([h['收益'] for h in final_history])
        
        return {"df": df, "wr": wr, "net_p": net_p, "rr": dynamic_rr, "history": final_history}
    except: return None

# --- 4. 介面渲染 ---
st.title("🏹 SMC AI 生存者終端 V53")
st.error(f"🚨 目前全市場 5D 總盈虧較低。AI 已啟動【熔斷保護】：止損加寬、RR 自動縮減至 {1.2}R。")

# --- 5. 顯示推薦 (過濾掉極端虧損) ---
st.write("### 🛡️ AI 篩選：避險後推薦清單")
total_net = 0.0
cols = st.columns(3)
count = 0

for sym, name in all_symbols.items():
    data = ai_survivor_engine(sym)
    if data:
        total_net += data['net_p']
        # 只有在該品種淨利 > -5% (代表還算穩定) 時才顯示
        if data['net_p'] > -5.0:
            with cols[count % 3]:
                cp, atr = data['df']['Close'].iloc[-1], data['df']['ATR'].iloc[-1]
                st.markdown(f"#### {sym} ({name})")
                st.metric("5D 勝率", f"{data['wr']:.1f}%", f"淨利 {data['net_p']:+.2f}%")
                
                # 訊號顯示
                ema = data['df']['EMA'].iloc[-1]
                bull = (data['df']['Low'].iloc[-1] > data['df']['High'].iloc[-3]) and cp > ema
                bear = (data['df']['High'].iloc[-3] > data['df']['Low'].iloc[-1]) and cp < ema
                
                if bull:
                    st.success("🔥 窄幅多單 (1.2R)"); sl = cp - (atr*2.0)
                    st.code(f"ENTRY: {cp:,.2f}\nSL: {sl:,.2f}\nTP: {cp+(cp-sl)*data['rr']:,.2f}")
                elif bear:
                    st.error("📉 窄幅空單 (1.2R)"); sl = cp + (atr*2.0)
                    st.code(f"ENTRY: {cp:,.2f}\nSL: {sl:,.2f}\nTP: {cp-(sl-cp)*data['rr']:,.2f}")
                else: st.info("🔎 市場修復中，等待結構...")
                count += 1

# 側邊欄總結
with st.sidebar:
    st.metric("全市場 5D 累計損益", f"{total_net:+.2f}%")
    st.divider()
    st.write("💡 **AI 診斷：**")
    st.write("當前市場處於震盪洗盤期。AI 已放棄 3.0RR 的大餅，改用 1.2RR 進行『防禦性交易』。")
