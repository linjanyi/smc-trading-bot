import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 配置 ---
st.set_page_config(page_title="SMC Pro V40", layout="wide")
st_autorefresh(interval=60000, key="v40_sync") 
tw_tz = pytz.timezone('Asia/Taipei')

# --- 2. 數據對照 ---
crypto_info = {"BTC-USD": "比特幣", "ETH-USD": "乙太幣", "SOL-USD": "索拉納"}
forex_info = {"GC=F": "黃金期貨", "NQ=F": "納指100", "EURUSD=X": "歐美匯率"}

if "active_cryptos" not in st.session_state: st.session_state.active_cryptos = ["BTC-USD"]
if "active_forex" not in st.session_state: st.session_state.active_forex = ["GC=F"]

# --- 3. AI 核心：限制 RR 避免走太遠 ---
@st.cache_data(ttl=600)
def find_best_stats_v40(df):
    if df is None or len(df) < 30: return 2.5, 0.0, 0.0
    # 這裡強行封頂在 3.0，確保 TP 距離合理
    rr_options = [1.5, 2.0, 2.5, 3.0] 
    best_rr, max_p, best_wr = 2.5, -999.0, 0.0
    
    t = df.copy()
    t['EMA'] = t['Close'].ewm(span=200, adjust=False).mean()
    bull = (t['Low'] > t['High'].shift(2)) & (t['Close'] > t['EMA'])
    bear = (t['High'] < t['Low'].shift(2)) & (t['Close'] < t['EMA'])
    t['Sig'] = 0
    t.loc[bull, 'Sig'], t.loc[bear, 'Sig'] = 1, -1
    rets_raw = (t['Sig'].shift(1) * t['Close'].pct_change()).dropna()

    for r in rr_options:
        final_rets = rets_raw.apply(lambda x: 0.005 * r if x > 0 else (-0.005 if x < 0 else 0))
        profit = (np.prod(1 + final_rets) - 1) * 100
        total = len(final_rets[final_rets != 0])
        wr = (len(final_rets[final_rets > 0]) / total * 100) if total > 0 else 0
        if profit > max_p:
            max_p, best_rr, best_wr = profit, r, wr
    return best_rr, max_p, best_wr

def get_data_v40(symbol):
    try:
        df = yf.download(symbol, period='10d', interval='1h', auto_adjust=True, progress=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        
        # 🛡️ 價格警察：黃金不該超過 3000
        cp = df['Close'].iloc[-1]
        if "GC=F" in symbol and cp > 3000: return "OFFSET" 
        
        df['EMA'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
        brr, mp, wr = find_best_stats_v40(df)
        return {"df": df, "best_rr": brr, "max_p": mp, "wr": wr}
    except: return None

# --- 4. 介面渲染 ---
st.title("🏹 SMC AI 量化終端 V40")
st.caption(f"🕒 台北時間: {datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M:%S')} | 已限制 RR 上限以確保 TP 合理性")

with st.sidebar:
    st.header("⚙️ 帳戶設定")
    bal = st.number_input("總本金 (USD)", value=10000)
    risk = st.slider("單筆風險 (%)", 0.1, 5.0, 1.0)

# 橫向打勾區
st.write("### 🔍 市場選擇")
c_cols = st.columns(4)
new_c = [s for i, s in enumerate(crypto_info.keys()) if c_cols[i].checkbox(f"{s}", value=(s in st.session_state.active_cryptos))]
st.session_state.active_cryptos = new_c

f_cols = st.columns(4)
new_f = [s for i, s in enumerate(forex_info.keys()) if f_cols[i].checkbox(f"{s}", value=(s in st.session_state.active_forex))]
st.session_state.active_forex = new_f

# --- 5. 渲染矩陣 ---
def draw_v40(items, is_crypto):
    if not items: return
    st.divider()
    cols = st.columns(3)
    for i, s in enumerate(items):
        with cols[i % 3]:
            data = get_data_v40(s)
            if data == "OFFSET":
                st.warning(f"⚠️ {s} 數據偏移 (Yahoo Error)\n目前偵測價格異常，暫停報單。")
                continue
            
            if data:
                df, brr, mp, wr = data['df'], data['best_rr'], data['max_p'], data['wr']
                cp = float(df['Close'].iloc[-1])
                atr = float(df['ATR'].iloc[-1])
                
                with st.container():
                    st.markdown(f"#### {s}")
                    st.metric(label="📊 7D 預期收益", value=f"{mp:.2f}%", delta=f"勝率 {wr:.1f}%")
                    st.write(f"當前價格: **{cp:,.2f}** | AI 推薦 RR: **{brr}**")
                    
                    bull = (df['Low'].iloc[-1] - df['High'].iloc[-3]) > (atr*0.3)
                    bear = (df['High'].iloc[-3] - df['Low'].iloc[-1]) > (atr*0.3)
                    
                    sig = None
                    if bull and cp > df['EMA'].iloc[-1]:
                        st.success("🔥 多單建議"); sl = cp - (atr*2); sig = "B"
                    elif bear and cp < df['EMA'].iloc[-1]:
                        st.error("📉 空單建議"); sl = cp + (atr*2); sig = "S"
                    else: st.info("🔎 監控中...")
                    
                    if sig:
                        pos = (bal * (risk/100)) / abs(cp - sl)
                        # 修正後的 TP 計算，不再走太遠
                        tp = cp + (cp-sl)*brr if sig == "B" else cp - (sl-cp)*brr
                        st.code(f"採用 RR: {brr}\n量:{pos:.4f}\nSL:{sl:,.2f}\nTP:{tp:,.2f}")
            else: st.error(f"❌ {s} 數據獲取失敗")

draw_v40(st.session_state.active_cryptos, True)
draw_v40(st.session_state.active_forex, False)
