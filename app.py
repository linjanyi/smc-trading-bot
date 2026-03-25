import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 配置 ---
st.set_page_config(page_title="SMC AI-AutoPilot V52", layout="wide")
st_autorefresh(interval=60000, key="v52_sync") 
tw_tz = pytz.timezone('Asia/Taipei')

# --- 2. 數據庫 ---
all_symbols = {
    "BTC-USD": "比特幣", "ETH-USD": "乙太幣", "SOL-USD": "索拉納",
    "GC=F": "黃金期貨", "NQ=F": "納指100", "EURUSD=X": "歐美匯率",
    "USDJPY=X": "美日匯率", "CL=F": "原油"
}

# --- 3. AI 自動診斷引擎 ---
@st.cache_data(ttl=60)
def ai_auto_scan_v52(symbol, risk_p=1.0):
    try:
        df = yf.download(symbol, period='12d', interval='1h', auto_adjust=True, progress=False)
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
                sl, tp2 = (entry_p - sl_dist, entry_p + sl_dist*3) if bull.iloc[i] else (entry_p + sl_dist, entry_p - sl_dist*3)
                for j in range(i+1, len(df)):
                    h, l = df['High'].iloc[j], df['Low'].iloc[j]
                    if bull.iloc[i]:
                        if l <= sl: res = "❌ 止損"; prof = -risk_p; break
                        if h >= tp2: res = "✅ 止盈"; prof = risk_p*3; break
                    else:
                        if h >= sl: res = "❌ 止損"; prof = -risk_p; break
                        if l <= tp2: res = "✅ 止盈"; prof = risk_p*3; break
                history.append({"時間": df.index[i], "結果": res, "收益": prof})

        # AI 統計
        v_trades = [h for h in history if h['結果'] != "⏳ 運行"]
        wr = (len([h for h in v_trades if "✅" in h['結果']]) / len(v_trades) * 100) if v_trades else 0
        net_profit = sum([h['收益'] for h in history])
        
        # AI 評級：勝率 > 30% 且 獲利為正 才推薦
        recommend = True if (wr >= 30 and net_profit > 0) else False
        
        return {"df": df, "wr": wr, "net_p": net_profit, "rec": recommend, "history": history}
    except: return None

# --- 4. 介面渲染 ---
st.title("🏹 SMC AI 自動駕駛終端 V52")
st.info("🤖 AI 正在掃描全球市場... 自動過濾低勝率品種，僅顯示「強趨勢」推薦。")

# 側邊欄：顯示所有品種狀態
with st.sidebar:
    st.header("📊 AI 市場掃描日誌")
    total_net = 0.0
    rec_list = []
    watch_list = []

# --- 5. 執行 AI 掃描與過濾 ---
for sym, name in all_symbols.items():
    data = ai_auto_scan_v52(sym)
    if data:
        if data['rec']: rec_list.append({"sym": sym, "name": name, "data": data})
        else: watch_list.append({"sym": sym, "name": name, "data": data})
        total_net += data['net_p']

# --- 6. 顯示推薦交易 (勝率高) ---
st.write("### 🔥 AI 推薦交易品種 (勝率 > 30%)")
if rec_list:
    cols = st.columns(3)
    for i, item in enumerate(rec_list):
        with cols[i % 3]:
            d = item['data']
            cp, atr, ema = d['df']['Close'].iloc[-1], d['df']['ATR'].iloc[-1], d['df']['EMA'].iloc[-1]
            with st.container():
                st.markdown(f"#### {item['sym']} ({item['name']}) ✅")
                st.metric("5D 勝率", f"{d['wr']:.1f}%", f"淨利 {d['net_p']:+.2f}%")
                
                bull = (d['df']['Low'].iloc[-1] - d['df']['High'].iloc[-3]) > (atr*0.3) and cp > ema
                bear = (d['df']['High'].iloc[-3] - d['df']['Low'].iloc[-1]) > (atr*0.3) and cp < ema
                
                if bull:
                    st.success("🔥 AI 多單訊號")
                    sl = cp - (atr*1.5); dist = cp - sl
                    st.code(f"AI ENTRY: {cp:,.2f}\nAI SL: {sl:,.2f}\nAI TP1: {cp+dist*1.5:,.2f}\nAI TP2: {cp+dist*3:,.2f}")
                elif bear:
                    st.error("📉 AI 空單訊號")
                    sl = cp + (atr*1.5); dist = sl - cp
                    st.code(f"AI ENTRY: {cp:,.2f}\nAI SL: {sl:,.2f}\nAI TP1: {cp-dist*1.5:,.2f}\nAI TP2: {cp-dist*3:,.2f}")
                else: st.info("🔎 結構良好，等待進場...")
else:
    st.warning("目前市場震盪強烈，AI 尚未發現高勝率推薦品種，建議觀望。")

# --- 7. 顯示觀察名單 (勝率低) ---
with st.expander("👁️ 觀察名單 (最近表現不佳，AI 建議避開)"):
    for item in watch_list:
        st.write(f"⚠️ **{item['sym']} ({item['name']})** | 勝率: {item['data']['wr']:.1f}% | 近期淨損益: {item['data']['net_p']:+.2f}%")

# 側邊欄戰績總結
with st.sidebar:
    st.metric("全市場 5D 總盈虧", f"{total_net:+.2f}%")
    st.divider()
    st.caption("AI 會自動根據數據更新推薦名單，無需手動勾選。")
