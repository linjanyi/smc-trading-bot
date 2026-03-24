import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 配置與刷新 ---
st.set_page_config(page_title="SMC Stable Terminal V31", layout="wide")
st_autorefresh(interval=60000, key="v31_sync") 
tw_tz = pytz.timezone('Asia/Taipei')

# --- 2. 穩定版數據對照表 (統一 Yahoo 格式) ---
crypto_info = {
    "BTC-USD": "比特幣", "ETH-USD": "乙太幣", "SOL-USD": "索拉納",
    "BNB-USD": "幣安幣", "DOGE-USD": "狗狗幣", "XRP-USD": "瑞波幣"
}
forex_info = {
    "GC=F": "黃金", "SI=F": "白銀", "NQ=F": "納指", 
    "CL=F": "原油", "EURUSD=X": "歐美匯率", "USDJPY=X": "美日匯率"
}

if "active_cryptos" not in st.session_state: st.session_state.active_cryptos = ["BTC-USD", "ETH-USD"]
if "active_forex" not in st.session_state: st.session_state.active_forex = ["GC=F"]

# --- 3. 穩定數據引擎 (100% Yahoo Finance) ---
@st.cache_data(ttl=60)
def get_analysis_stable(symbol):
    try:
        # 抓取 1H 與 4H 數據
        df = yf.download(symbol, period='30d', interval='1h', auto_adjust=True, progress=False)
        df_h = yf.download(symbol, period='60d', interval='4h', auto_adjust=True, progress=False)
        
        # 修正 yfinance 多重索引問題
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        if isinstance(df_h.columns, pd.MultiIndex): df_h.columns = df_h.columns.get_level_values(0)
        
        if df.empty or len(df) < 50: return None

        # 指標計算
        df['EMA'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
        
        # 4H 趨勢判定
        htf_ema = df_h['Close'].ewm(span=200, adjust=False).mean()
        htf_trend = 1 if df_h['Close'].iloc[-1] > htf_ema.iloc[-1] else -1
        
        # 30天勝率簡單統計 (RR=3)
        temp = df.copy()
        sig = (temp['Low'] > temp['High'].shift(2)) & (temp['Close'] > temp['EMA'])
        temp['Ret'] = np.where(sig.shift(1), (temp['Close']/temp['Open']-1).clip(-0.005, 0.015), 0)
        total_trades = len(temp[temp['Ret']!=0])
        wr = (len(temp[temp['Ret']>0])/total_trades*100) if total_trades > 0 else 0
        prof = temp['Ret'].sum() * 100
        
        return {"df": df, "htf": htf_trend, "wr": wr, "pr": prof}
    except:
        return None

# --- 4. 介面渲染 ---
st.title("🛡️ SMC 全球監控終端 V31")
st.caption(f"🕒 數據源：Yahoo Finance (穩定版) | 台北時間: {datetime.now(tw_tz).strftime('%H:%M:%S')}")

# 側邊欄風控
with st.sidebar:
    st.header("⚙️ 參數設定")
    bal = st.number_input("本金 (USD)", value=10000)
    risk = st.slider("風險 (%)", 0.1, 5.0, 1.0)
    rr = st.slider("盈虧比 (R/R)", 1.5, 5.0, 3.0, 0.5)

# --- 橫向打勾區 ---
st.write("### 🌌 虛擬幣監控")
c_cols = st.columns(len(crypto_info))
new_c = []
for i, (s, n) in enumerate(crypto_info.items()):
    with c_cols[i]:
        if st.checkbox(f"**{s.replace('-USD','')}**\n{n}", value=(s in st.session_state.active_cryptos), key=f"c{s}"):
            new_c.append(s)
st.session_state.active_cryptos = new_c

st.write("### 💵 外匯與商品")
f_cols = st.columns(len(forex_info))
new_f = []
for i, (s, n) in enumerate(forex_info.items()):
    with f_cols[i]:
        if st.checkbox(f"**{s}**\n{n}", value=(s in st.session_state.active_forex), key=f"f{s}"):
            new_f.append(s)
st.session_state.active_forex = new_f

# --- 5. 渲染訊號矩陣 ---
def draw_matrix(items, is_crypto):
    if not items: return
    st.divider()
    cols = st.columns(3)
    for i, s in enumerate(items):
        with cols[i % 3]:
            data = get_analysis_stable(s)
            if data:
                df, htf, wr, pr = data['df'], data['htf'], data['wr'], data['pr']
                cp = df['Close'].iloc[-1]
                atr = df['High'].iloc[-1] - df['Low'].iloc[-1]
                name = crypto_info.get(s) if is_crypto else forex_info.get(s)
                
                with st.container():
                    st.markdown(f"#### {s} ({name})")
                    st.write(f"📊 勝率: {wr:.1f}% | 獲利: {pr:.1f}%")
                    
                    # SMC 判定邏輯
                    fvg_bull = df['Low'].iloc[-1] - df['High'].iloc[-3]
                    fvg_bear = df['High'].iloc[-3] - df['Low'].iloc[-1]
                    
                    sig = None
                    if fvg_bull > (atr*0.3) and cp > df['EMA'].iloc[-1]:
                        sig, status = "BUY", ("🔥 強力多單" if htf==1 else "⚠️ 逆勢多單")
                        st.success(status); sl = cp - (atr * 2)
                    elif fvg_bear > (atr*0.3) and cp < df['EMA'].iloc[-1]:
                        sig, status = "SELL", ("🔥 強力空單" if htf==-1 else "⚠️ 逆勢空單")
                        st.error(status); sl = cp + (atr * 2)
                    else:
                        st.info("🔎 監控中...")
                    
                    if sig:
                        pos = (bal * (risk/100)) / abs(cp - sl)
                        st.code(f"量:{pos:.4f}\nSL:{sl:.4f}\nTP:{cp + (cp-sl)*rr:.4f}")
            else:
                st.error(f"❌ {s} 數據抓取失敗")
            st.divider()

draw_matrix(st.session_state.active_cryptos, True)
draw_matrix(st.session_state.active_forex, False)
