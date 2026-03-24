import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 初始化與環境 ---
st.set_page_config(page_title="SMC Pro V42", layout="wide")
st_autorefresh(interval=60000, key="v42_sync") 
tw_tz = pytz.timezone('Asia/Taipei')

# --- 2. 核心數據引擎 ---
@st.cache_data(ttl=60)
def get_analysis_v42(symbol):
    try:
        # 抓取 10 天 1 小時數據
        df = yf.download(symbol, period='10d', interval='1h', auto_adjust=True, progress=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        
        # 指標計算
        df['EMA'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
        
        # 回測統計 (採用 V42 的 1:1.5 窄止盈邏輯)
        temp = df.copy()
        sig = (temp['Low'] > temp['High'].shift(2)) & (temp['Close'] > temp['EMA'])
        # 模擬窄止損 (-0.3%) 與 1.5倍 止盈 (+0.45%)
        temp['Ret'] = np.where(sig.shift(1), (temp['Close']/temp['Open']-1).clip(-0.003, 0.0045), 0)
        total_trades = len(temp[temp['Ret']!=0])
        wr = (len(temp[temp['Ret']>0])/total_trades*100) if total_trades > 0 else 0
        
        return {"df": df, "wr": wr, "pr": temp['Ret'].sum()*100}
    except: return None

# --- 3. 介面渲染 ---
st.title("🛡️ SMC 實戰導航 V42")
st.success("✅ 已優化：縮短止損距離 (1.2x ATR)，獲利目標已大幅拉近。")

with st.sidebar:
    st.header("💰 風控設定")
    bal = st.number_input("總本金 (USD)", value=10000)
    risk_pct = st.slider("單筆風險 (%)", 0.1, 5.0, 1.0)

# 橫向打勾 (精簡版)
c_info = {"BTC-USD": "比特幣", "ETH-USD": "乙太幣", "SOL-USD": "索拉納"}
f_info = {"GC=F": "黃金期貨", "NQ=F": "納指100", "EURUSD=X": "歐美匯率"}

c_cols = st.columns(3)
active_c = [s for i, s in enumerate(c_info.keys()) if c_cols[i].checkbox(f"{s}", value=(i==0))]
f_cols = st.columns(3)
active_f = [s for i, s in enumerate(f_info.keys()) if f_cols[i].checkbox(f"{s}", value=True)]

# --- 4. 渲染矩陣 ---
def draw_v42(items, is_c):
    if not items: return
    st.divider()
    cols = st.columns(3)
    for i, s in enumerate(items):
        with cols[i % 3]:
            data = get_analysis_v42(s)
            if data:
                df, wr, pr = data['df'], data['wr'], data['pr']
                cp = float(df['Close'].iloc[-1])
                ema = df['EMA'].iloc[-1]
                atr = float(df['ATR'].iloc[-1])
                
                with st.container():
                    st.markdown(f"#### {s}")
                    st.write(f"📊 7D 勝率: **{wr:.1f}%** | 現價: **{cp:,.2f}**")
                    
                    # SMC 結構判定
                    bull = (df['Low'].iloc[-1] - df['High'].iloc[-3]) > (atr*0.3)
                    bear = (df['High'].iloc[-3] - df['Low'].iloc[-1]) > (atr*0.3)
                    
                    sig = None
                    if bull and cp > ema:
                        st.success("🔥 多單建議"); sig = "B"
                        sl_dist = atr * 1.2  # V42 窄止損
                        sl = cp - sl_dist
                    elif bear and cp < ema:
                        st.error("📉 空單建議"); sig = "S"
                        sl_dist = atr * 1.2  # V42 窄止損
                        sl = cp + sl_dist
                    else: st.info("🔎 監控結構中...")
                    
                    if sig:
                        dist = abs(cp - sl)
                        pos = (bal * (risk_pct/100)) / dist
                        # 止盈 1 設為更近的 1.5 倍，止盈 2 設為 2.5 倍
                        tp1 = cp + dist*1.5 if sig=="B" else cp - dist*1.5
                        tp2 = cp + dist*2.5 if sig=="B" else cp - dist*2.5
                        
                        st.code(f"量:{pos:.4f}\n止損(SL):{sl:,.2f}\n止盈1(RR 1.5):{tp1:,.2f}\n止盈2(RR 2.5):{tp2:,.2f}")
            else: st.error(f"❌ {s} 讀取失敗")

draw_v42(active_c, True)
draw_v42(active_f, False)
