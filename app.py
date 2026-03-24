import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 配置與刷新 ---
st.set_page_config(page_title="SMC Stable Pro V34", layout="wide")
st_autorefresh(interval=45000, key="v34_sync") 
tw_tz = pytz.timezone('Asia/Taipei')

# --- 2. 數據對照表 ---
crypto_info = {"BTC-USD": "比特幣", "ETH-USD": "乙太幣", "SOL-USD": "索拉納", "BNB-USD": "幣安幣"}
forex_info = {"GC=F": "黃金", "NQ=F": "納指", "EURUSD=X": "歐美匯率", "USDJPY=X": "美日匯率"}

if "active_cryptos" not in st.session_state: st.session_state.active_cryptos = ["BTC-USD"]
if "active_forex" not in st.session_state: st.session_state.active_forex = ["GC=F"]

# --- 3. 穩定數據引擎 (超簡化版) ---
def get_analysis_v34(symbol):
    try:
        # 只抓最近 7 天，加快速度並減少出錯率
        df = yf.download(symbol, period='7d', interval='1h', auto_adjust=True, progress=False)
        if df.empty: return None
        
        # 這是修復「價格變4000多」的關鍵：強制扁平化並只取 Close
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        # 確保數據完整性
        df = df.dropna()
        if len(df) < 20: return None

        # 計算指標
        df['EMA'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
        
        # 簡單勝率回測 (RR=3)
        temp = df.copy()
        sig = (temp['Low'] > temp['High'].shift(2)) & (temp['Close'] > temp['EMA'])
        temp['Ret'] = np.where(sig.shift(1), (temp['Close']/temp['Open']-1).clip(-0.005, 0.015), 0)
        wr = (len(temp[temp['Ret']>0])/len(temp[temp['Ret']!=0])*100) if len(temp[temp['Ret']!=0])>0 else 0
        
        return {"df": df, "wr": wr, "pr": temp['Ret'].sum()*100}
    except:
        return None

# --- 4. 介面渲染 ---
st.title("🏹 SMC 全球監控 V34 (穩定修復)")
st.caption(f"🕒 台北時間: {datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M:%S')}")

with st.sidebar:
    st.header("⚙️ 設定")
    bal = st.number_input("本金 (USD)", value=10000)
    risk = st.slider("風險 (%)", 0.1, 5.0, 1.0)
    rr = st.slider("目標盈虧比 (R/R)", 1.5, 5.0, 3.0, 0.5)

# 橫向打勾
st.write("### 🌌 市場選擇")
c_c1, c_c2, c_c3, c_c4 = st.columns(4)
new_c = []
for i, (s, n) in enumerate(crypto_info.items()):
    col = [c_c1, c_c2, c_c3, c_c4][i]
    if col.checkbox(f"{s}\n({n})", value=(s in st.session_state.active_cryptos)): new_c.append(s)
st.session_state.active_cryptos = new_c

f_c1, f_c2, f_c3, f_c4 = st.columns(4)
new_f = []
for i, (s, n) in enumerate(forex_info.items()):
    col = [f_c1, f_c2, f_c3, f_c4][i]
    if col.checkbox(f"{s}\n({n})", value=(s in st.session_state.active_forex)): new_f.append(s)
st.session_state.active_forex = new_f

# --- 5. 渲染矩陣 ---
def draw(items, is_crypto):
    if not items: return
    st.divider()
    cols = st.columns(3)
    for i, s in enumerate(items):
        with cols[i % 3]:
            data = get_analysis_v34(s)
            if data:
                df, wr, pr = data['df'], data['wr'], data['pr']
                cp = float(df['Close'].iloc[-1])
                atr = float(df['ATR'].iloc[-1])
                
                with st.container():
                    st.markdown(f"#### {s}")
                    st.write(f"📊 勝率: {wr:.1f}% | 價格: **{cp:,.2f}**")
                    
                    # SMC 判定
                    bull = (df['Low'].iloc[-1] - df['High'].iloc[-3]) > (atr*0.3)
                    bear = (df['High'].iloc[-3] - df['Low'].iloc[-1]) > (atr*0.3)
                    
                    if bull and cp > df['EMA'].iloc[-1]:
                        st.success("🔥 多單建議"); sl = cp - (atr*2)
                        st.code(f"量:{bal*(risk/100)/abs(cp-sl):.4f}\nSL:{sl:,.2f}\nTP:{cp+(cp-sl)*rr:,.2f}")
                    elif bear and cp < df['EMA'].iloc[-1]:
                        st.error("📉 空單建議"); sl = cp + (atr*2)
                        st.code(f"量:{bal*(risk/100)/abs(cp-sl):.4f}\nSL:{sl:,.2f}\nTP:{cp-(sl-cp)*rr:,.2f}")
                    else: st.info("🔎 結構觀察中...")
            else: st.error(f"❌ {s} 讀取中...")

draw(st.session_state.active_cryptos, True)
draw(st.session_state.active_forex, False)
