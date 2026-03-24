import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 配置 ---
st.set_page_config(page_title="SMC Pro V41", layout="wide")
st_autorefresh(interval=60000, key="v41_sync") 
tw_tz = pytz.timezone('Asia/Taipei')

# --- 2. 穩定數據引擎 ---
def get_analysis_v41(symbol):
    try:
        df = yf.download(symbol, period='10d', interval='1h', auto_adjust=True, progress=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        
        df['EMA'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
        
        # 固定回測 1:2.5 的標準勝率
        temp = df.copy()
        sig = (temp['Low'] > temp['High'].shift(2)) & (temp['Close'] > temp['EMA'])
        temp['Ret'] = np.where(sig.shift(1), (temp['Close']/temp['Open']-1).clip(-0.005, 0.0125), 0)
        wr = (len(temp[temp['Ret']>0])/len(temp[temp['Ret']!=0])*100) if len(temp[temp['Ret']!=0])>0 else 0
        
        return {"df": df, "wr": wr, "pr": temp['Ret'].sum()*100}
    except: return None

# --- 3. 介面渲染 ---
st.title("🏹 SMC 全球量化矩陣 V41")
st.info(f"📊 當前設定：採用 1:2 與 1:3 雙目標止盈，避免單一目標過遠。")

with st.sidebar:
    st.header("💰 帳戶風控")
    bal = st.number_input("總本金 (USD)", value=10000)
    risk_pct = st.slider("單筆風險 (%)", 0.1, 5.0, 1.0)

# 橫向打勾 (簡化)
c_info = {"BTC-USD": "比特幣", "ETH-USD": "乙太幣", "SOL-USD": "索拉納"}
f_info = {"GC=F": "黃金期貨", "NQ=F": "納指100", "EURUSD=X": "歐美匯率"}

c_cols = st.columns(3)
active_c = [s for i, s in enumerate(c_info.keys()) if c_cols[i].checkbox(f"{s}", value=True)]
f_cols = st.columns(3)
active_f = [s for i, s in enumerate(f_info.keys()) if f_cols[i].checkbox(f"{s}", value=True)]

# --- 4. 渲染矩陣 ---
def draw_v41(items, is_c):
    if not items: return
    st.divider()
    cols = st.columns(3)
    for i, s in enumerate(items):
        with cols[i % 3]:
            data = get_analysis_v41(s)
            if data:
                df, wr, pr = data['df'], data['wr'], data['pr']
                cp = float(df['Close'].iloc[-1])
                ema = df['EMA'].iloc[-1]
                atr = float(df['ATR'].iloc[-1])
                
                with st.container():
                    st.markdown(f"#### {s}")
                    st.write(f"📊 7D 勝率: **{wr:.1f}%** | 價格: **{cp:,.2f}**")
                    
                    # SMC 判定
                    bull = (df['Low'].iloc[-1] - df['High'].iloc[-3]) > (atr*0.3)
                    bear = (df['High'].iloc[-3] - df['Low'].iloc[-1]) > (atr*0.3)
                    
                    sig = None
                    if bull and cp > ema:
                        st.success("🔥 多單建議"); sl = cp - (atr*2); sig = "B"
                    elif bear and cp < ema:
                        st.error("📉 空單建議"); sl = cp + (atr*2); sig = "S"
                    else: st.info("🔎 監控中...")
                    
                    if sig:
                        dist = abs(cp - sl)
                        pos = (bal * (risk_pct/100)) / dist
                        # 核心修改：雙止盈位，讓你不再覺得遠
                        tp1 = cp + dist*2 if sig=="B" else cp - dist*2
                        tp2 = cp + dist*3 if sig=="B" else cp - dist*3
                        
                        st.code(f"量:{pos:.4f}\n止損(SL):{sl:,.2f}\n止盈1(RR 2):{tp1:,.2f}\n止盈2(RR 3):{tp2:,.2f}")
            else: st.error(f"❌ {s} 讀取失敗")

draw_v41(active_c, True)
draw_v41(active_f, False)
