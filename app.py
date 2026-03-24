import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# --- 1. 初始化 ---
st.set_page_config(page_title="SMC AI-Stable V33", layout="wide")
st_autorefresh(interval=60000, key="v33_sync") 
tw_tz = pytz.timezone('Asia/Taipei')

# --- 2. 數據對照表 ---
crypto_info = {
    "BTC-USD": "比特幣", "ETH-USD": "乙太幣", "SOL-USD": "索拉納",
    "BNB-USD": "幣安幣", "DOGE-USD": "狗狗幣", "XRP-USD": "瑞波幣"
}
forex_info = {
    "GC=F": "黃金", "SI=F": "白銀", "NQ=F": "納指", 
    "CL=F": "原油", "EURUSD=X": "歐美匯率", "USDJPY=X": "美日匯率"
}

if "active_cryptos" not in st.session_state: st.session_state.active_cryptos = ["BTC-USD"]
if "active_forex" not in st.session_state: st.session_state.active_forex = ["GC=F"]

# --- 3. 強化版數據引擎 ---
def get_clean_data(symbol, period='30d', interval='1h'):
    try:
        # 增加數據抓取的穩定性參數
        raw_df = yf.download(symbol, period=period, interval=interval, auto_adjust=True, progress=False, multi_level_download=False)
        
        if raw_df.empty or len(raw_df) < 50:
            return pd.DataFrame()
            
        # 強制整理格式，解決 yfinance 報價位移問題
        df = raw_df.copy()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        # 排除極端異常值（例如 BTC 低於 10000 顯然是抓到舊資料）
        if "BTC-USD" in symbol and df['Close'].iloc[-1] < 10000:
            return pd.DataFrame() 
            
        return df
    except:
        return pd.DataFrame()

@st.cache_data(ttl=600)
def find_best_rr_v33(df):
    if df.empty or len(df) < 50: return 3.0, 0.0, 0.0
    rr_options = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0]
    best_rr, max_p, best_wr = 3.0, -999.0, 0.0
    
    t = df.copy()
    t['EMA'] = t['Close'].ewm(span=200, adjust=False).mean()
    bull = (t['Low'] > t['High'].shift(2)) & (t['Close'] > t['EMA'])
    bear = (t['High'] < t['Low'].shift(2)) & (t['Close'] < t['EMA'])
    t['Sig'] = 0
    t.loc[bull, 'Sig'], t.loc[bear, 'Sig'] = 1, -1
    rets = (t['Sig'].shift(1) * t['Close'].pct_change()).dropna()

    for r in rr_options:
        f_rets = rets.apply(lambda x: 0.005 * r if x > 0 else (-0.005 if x < 0 else 0))
        prof = (np.prod(1 + f_rets) - 1) * 100
        total = len(f_rets[f_rets != 0])
        wr = (len(f_rets[f_rets > 0]) / total * 100) if total > 0 else 0
        if prof > max_p:
            max_p, best_rr, best_wr = prof, r, wr
    return best_rr, max_p, best_wr

@st.cache_data(ttl=30)
def get_analysis_v33(symbol):
    df = get_clean_data(symbol, '30d', '1h')
    df_h = get_clean_data(symbol, '60d', '4h')
    
    if df.empty or df_h.empty: return None
    
    df['EMA'] = df['Close'].ewm(span=200, adjust=False).mean()
    df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
    htf_ema = df_h['Close'].ewm(span=200, adjust=False).mean()
    htf_trend = 1 if df_h['Close'].iloc[-1] > htf_ema.iloc[-1] else -1
    best_rr, max_p, wr = find_best_rr_v33(df)
    
    return {"df": df, "htf": htf_trend, "best_rr": best_rr, "max_p": max_p, "wr": wr}

# --- 4. UI 渲染 ---
st.title("🏹 SMC AI 監控 V33 (數據修正版)")
st.caption(f"🕒 台北時間: {datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M:%S')}")

with st.sidebar:
    st.header("⚙️ 設定")
    bal = st.number_input("本金 (USD)", value=10000)
    risk = st.slider("風險 (%)", 0.1, 5.0, 1.0)
    manual_rr = st.toggle("手動覆蓋 AI 盈虧比", value=False)
    user_rr = st.select_slider("手動 R/R", options=[1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0], value=3.0, disabled=not manual_rr)

# --- 橫向打勾區 ---
st.write("### 🌌 虛擬幣監控")
c_cols = st.columns(len(crypto_info))
new_c = [s for s in crypto_info.keys() if c_cols[list(crypto_info.keys()).index(s)].checkbox(f"**{s.replace('-USD','')}**", value=(s in st.session_state.active_cryptos), key=f"c{s}")]
st.session_state.active_cryptos = new_c

st.write("### 💵 外匯與商品")
f_cols = st.columns(len(forex_info))
new_f = [s for s in forex_info.keys() if f_cols[list(forex_info.keys()).index(s)].checkbox(f"**{s}**", value=(s in st.session_state.active_forex), key=f"f{s}")]
st.session_state.active_forex = new_f

# --- 5. 渲染矩陣 ---
def draw_v33(items, is_crypto):
    if not items: return
    st.divider()
    cols = st.columns(3)
    for i, s in enumerate(items):
        with cols[i % 3]:
            data = get_analysis_v33(s)
            if data:
                df, htf, best_rr, max_p, wr = data['df'], data['htf'], data['best_rr'], data['max_p'], data['wr']
                cp = float(df['Close'].iloc[-1])
                atr = float(df['ATR'].iloc[-1])
                name = crypto_info.get(s) if is_crypto else forex_info.get(s)
                final_rr = user_rr if manual_rr else best_rr
                
                with st.container():
                    st.markdown(f"#### {s} ({name})")
                    st.write(f"🤖 AI 推薦 RR: **{best_rr}** | 📊 預期獲利: **{max_p:.1f}%**")
                    st.write(f"即時報價: **{cp:,.2f}**") # 加上千分位符號，方便檢查
                    
                    # SMC 邏輯
                    fvg_bull = df['Low'].iloc[-1] - df['High'].iloc[-3]
                    fvg_bear = df['High'].iloc[-3] - df['Low'].iloc[-1]
                    
                    sig = None
                    if fvg_bull > (atr*0.3) and cp > df['EMA'].iloc[-1]:
                        sig, status = "BUY", ("🔥 強力多單" if htf==1 else "⚠️ 逆勢多單")
                        st.success(status); sl = cp - (atr * 2)
                    elif fvg_bear > (atr*0.3) and cp < df['EMA'].iloc[-1]:
                        sig, status = "SELL", ("🔥 強力空單" if htf==-1 else "⚠️ 逆勢空單")
                        st.error(status); sl = cp + (atr * 2)
                    else: st.info("🔎 監控中...")
                    
                    if sig:
                        pos = (bal * (risk/100)) / abs(cp - sl)
                        st.code(f"採用 RR: {final_rr}\n量:{pos:.4f}\nSL:{sl:,.2f}\nTP:{(cp + (cp-sl)*final_rr):,.2f}")
            else:
                st.error(f"❌ {s}: 數據檢核未通過，重試中...")

draw_v33(st.session_state.active_cryptos, True)
draw_v33(st.session_state.active_forex, False)
