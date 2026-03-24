import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 配置與刷新 ---
st.set_page_config(page_title="SMC AI-Stable V32", layout="wide")
st_autorefresh(interval=60000, key="v32_sync") 
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

# --- 3. AI 最佳化引擎 (Backtest Scanner) ---
@st.cache_data(ttl=600)
def find_best_rr_v32(df):
    """AI 掃描器：找出過去30天獲利最高的盈虧比"""
    if df is None or df.empty or len(df) < 50: return 3.0, 0.0, 0.0
    rr_options = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0]
    best_rr, max_profit, best_wr = 3.0, -999.0, 0.0
    
    temp = df.copy()
    temp['EMA'] = temp['Close'].ewm(span=200, adjust=False).mean()
    # SMC 訊號模擬
    bull = (temp['Low'] > temp['High'].shift(2)) & (temp['Close'] > temp['EMA'])
    bear = (temp['High'] < temp['Low'].shift(2)) & (temp['Close'] < temp['EMA'])
    temp['Sig'] = 0
    temp.loc[bull, 'Sig'], temp.loc[bear, 'Sig'] = 1, -1
    rets_raw = (temp['Sig'].shift(1) * temp['Close'].pct_change()).dropna()

    for r in rr_options:
        # 模擬：輸賠 0.5%，贏賺 0.5% * r
        final_rets = rets_raw.apply(lambda x: 0.005 * r if x > 0 else (-0.005 if x < 0 else 0))
        profit = (np.prod(1 + final_rets) - 1) * 100
        total = len(final_rets[final_rets != 0])
        wr = (len(final_rets[final_rets > 0]) / total * 100) if total > 0 else 0
        if profit > max_profit:
            max_profit, best_rr, best_wr = profit, r, wr
    return best_rr, max_profit, best_wr

@st.cache_data(ttl=60)
def get_analysis_v32(symbol):
    try:
        df = yf.download(symbol, period='30d', interval='1h', auto_adjust=True, progress=False)
        df_h = yf.download(symbol, period='60d', interval='4h', auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        if isinstance(df_h.columns, pd.MultiIndex): df_h.columns = df_h.columns.get_level_values(0)
        
        if df.empty or len(df) < 50: return None
        df['EMA'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
        
        htf_ema = df_h['Close'].ewm(span=200, adjust=False).mean()
        htf_trend = 1 if df_h['Close'].iloc[-1] > htf_ema.iloc[-1] else -1
        
        # 呼叫 AI 優化引擎
        best_rr, max_p, wr = find_best_rr_v32(df)
        return {"df": df, "htf": htf_trend, "best_rr": best_rr, "max_p": max_p, "wr": wr}
    except: return None

# --- 4. 介面渲染 ---
st.title("🏹 SMC AI 全球監控 V32 (穩定版)")
st.caption(f"🕒 台北時間: {datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M:%S')} | 數據源: Yahoo Finance")

with st.sidebar:
    st.header("⚙️ 設定")
    bal = st.number_input("本金 (USD)", value=10000)
    risk = st.slider("風險 (%)", 0.1, 5.0, 1.0)
    st.divider()
    manual_rr = st.toggle("手動覆蓋 AI 盈虧比", value=False)
    user_rr = st.select_slider("手動 R/R", options=[1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0], value=3.0, disabled=not manual_rr)

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

# --- 5. 渲染矩陣 ---
def draw_v32(items, is_crypto):
    if not items: return
    st.divider()
    cols = st.columns(3)
    for i, s in enumerate(items):
        with cols[i % 3]:
            data = get_analysis_v32(s)
            if data:
                df, htf, best_rr, max_p, wr = data['df'], data['htf'], data['best_rr'], data['max_p'], data['wr']
                cp, atr = df['Close'].iloc[-1], df['High'].iloc[-1] - df['Low'].iloc[-1]
                name = crypto_info.get(s) if is_crypto else forex_info.get(s)
                
                # 決定 RR
                final_rr = user_rr if manual_rr else best_rr
                
                with st.container():
                    st.markdown(f"#### {s} ({name})")
                    st.write(f"🤖 **AI 推薦 R/R: {best_rr}**")
                    st.write(f"📊 勝率: {wr:.1f}% | 獲利: {max_p:.1f}%")
                    
                    sig = None
                    if (df['Low'].iloc[-1] - df['High'].iloc[-3]) > (atr*0.3) and cp > df['EMA'].iloc[-1]:
                        sig, status = "BUY", ("🔥 強力多單" if htf==1 else "⚠️ 逆勢多單")
                        st.success(status); sl = cp - (atr * 2)
                    elif (df['High'].iloc[-3] - df['Low'].iloc[-1]) > (atr*0.3) and cp < df['EMA'].iloc[-1]:
                        sig, status = "SELL", ("🔥 強力空單" if htf==-1 else "⚠️ 逆勢空單")
                        st.error(status); sl = cp + (atr * 2)
                    else: st.info("🔎 監控中...")
                    
                    if sig:
                        pos = (bal * (risk/100)) / abs(cp - sl)
                        st.code(f"採用 R/R: {final_rr}\n量:{pos:.4f}\nSL:{sl:.4f}\nTP:{cp + (cp-sl)*final_rr:.4f}")
            else: st.error(f"❌ {s} 數據抓取失敗")
            st.divider()

draw_v32(st.session_state.active_cryptos, True)
draw_v32(st.session_state.active_forex, False)
