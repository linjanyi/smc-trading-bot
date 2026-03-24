import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 初始化與環境設定 ---
st.set_page_config(page_title="SMC AI-Stable V35", layout="wide")
st_autorefresh(interval=45000, key="v35_sync") 
tw_tz = pytz.timezone('Asia/Taipei')

# --- 2. 數據對照表 ---
crypto_info = {"BTC-USD": "比特幣", "ETH-USD": "乙太幣", "SOL-USD": "索拉納", "BNB-USD": "幣安幣"}
forex_info = {"GC=F": "黃金", "NQ=F": "納指", "EURUSD=X": "歐美匯率", "USDJPY=X": "美日匯率"}

if "active_cryptos" not in st.session_state: st.session_state.active_cryptos = ["BTC-USD"]
if "active_forex" not in st.session_state: st.session_state.active_forex = ["GC=F"]

# --- 3. AI 盈虧比優化引擎 ---
@st.cache_data(ttl=600)
def find_best_rr_stable(df):
    """AI 掃描器：在 1.5 到 5.0 之間找出最賺錢的 RR"""
    if df is None or df.empty or len(df) < 30: return 3.0, 0.0, 0.0
    rr_options = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0]
    best_rr, max_profit, best_wr = 3.0, -999.0, 0.0
    
    # 建立回測邏輯
    t = df.copy()
    t['EMA'] = t['Close'].ewm(span=200, adjust=False).mean()
    bull = (t['Low'] > t['High'].shift(2)) & (t['Close'] > t['EMA'])
    bear = (t['High'] < t['Low'].shift(2)) & (t['Close'] < t['EMA'])
    t['Sig'] = 0
    t.loc[bull, 'Sig'], t.loc[bear, 'Sig'] = 1, -1
    rets_raw = (t['Sig'].shift(1) * t['Close'].pct_change()).dropna()

    for r in rr_options:
        # 模擬：輸賠 0.5%，贏賺 0.5% * r
        final_rets = rets_raw.apply(lambda x: 0.005 * r if x > 0 else (-0.005 if x < 0 else 0))
        profit = (np.prod(1 + final_rets) - 1) * 100
        total = len(final_rets[final_rets != 0])
        wr = (len(final_rets[final_rets > 0]) / total * 100) if total > 0 else 0
        if profit > max_profit:
            max_profit, best_rr, best_wr = profit, r, wr
    return best_rr, max_profit, best_wr

# --- 4. 數據抓取引擎 ---
def get_analysis_v35(symbol):
    try:
        # 抓取 7 天數據確保速度與準確度
        df = yf.download(symbol, period='7d', interval='1h', auto_adjust=True, progress=False)
        if df.empty: return None
        
        # 關鍵修復：處理 yfinance 多重索引
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        df = df.dropna()
        if len(df) < 20: return None

        # 指標計算
        df['EMA'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
        
        # 執行 AI 優化
        best_rr, max_p, wr = find_best_rr_stable(df)
        
        return {"df": df, "best_rr": best_rr, "max_p": max_p, "wr": wr}
    except:
        return None

# --- 5. 介面渲染 ---
st.title("🏹 SMC AI 穩定監控 V35")
st.caption(f"🕒 台北時間: {datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M:%S')} | AI 盈虧優化器：已啟動")

with st.sidebar:
    st.header("⚙️ 參數設定")
    bal = st.number_input("總本金 (USD)", value=10000)
    risk = st.slider("單筆風險 (%)", 0.1, 5.0, 1.0)
    st.divider()
    manual_rr = st.toggle("手動覆蓋 AI 盈虧比", value=False)
    user_rr = st.select_slider("手動 R/R", options=[1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0], value=3.0, disabled=not manual_rr)

# 橫向打勾區
st.write("### 🔍 市場監控清單")
c_c1, c_c2, c_c3, c_c4 = st.columns(4)
new_c = []
for i, (s, n) in enumerate(crypto_info.items()):
    col = [c_c1, c_c2, c_c3, c_c4][i]
    if col.checkbox(f"**{s}** ({n})", value=(s in st.session_state.active_cryptos), key=f"c{s}"): new_c.append(s)
st.session_state.active_cryptos = new_c

f_c1, f_c2, f_c3, f_c4 = st.columns(4)
new_f = []
for i, (s, n) in enumerate(forex_info.items()):
    col = [f_c1, f_c2, f_c3, f_c4][i]
    if col.checkbox(f"**{s}** ({n})", value=(s in st.session_state.active_forex), key=f"f{s}"): new_f.append(s)
st.session_state.active_forex = new_f

# --- 6. 渲染訊號矩陣 ---
def draw_matrix_v35(items, is_crypto):
    if not items: return
    st.divider()
    cols = st.columns(3)
    for i, s in enumerate(items):
        with cols[i % 3]:
            data = get_analysis_v35(s)
            if data:
                df, best_rr, max_p, wr = data['df'], data['best_rr'], data['max_p'], data['wr']
                cp = float(df['Close'].iloc[-1])
                atr = float(df['ATR'].iloc[-1])
                
                # 決定最終使用的 RR
                final_rr = user_rr if manual_rr else best_rr
                
                with st.container():
                    st.markdown(f"#### {s}")
                    st.write(f"🤖 **AI 推薦 RR: {best_rr}**")
                    st.write(f"📊 勝率: {wr:.1f}% | 價格: **{cp:,.2f}**")
                    
                    # SMC 判定 (FVG 缺口)
                    bull = (df['Low'].iloc[-1] - df['High'].iloc[-3]) > (atr*0.3)
                    bear = (df['High'].iloc[-3] - df['Low'].iloc[-1]) > (atr*0.3)
                    
                    sig = None
                    if bull and cp > df['EMA'].iloc[-1]:
                        sig, status = "BUY", "🔥 多單建議"
                        st.success(status); sl = cp - (atr*2)
                    elif bear and cp < df['EMA'].iloc[-1]:
                        sig, status = "SELL", "📉 空單建議"
                        st.error(status); sl = cp + (atr*2)
                    else:
                        st.info("🔎 結構觀察中...")
                    
                    if sig:
                        pos = (bal * (risk/100)) / abs(cp - sl)
                        st.code(f"採用 RR: {final_rr}\n量:{pos:.4f}\nSL:{sl:,.2f}\nTP:{(cp + (cp-sl)*final_rr):,.2f}")
            else:
                st.error(f"❌ {s} 數據加載失敗")

draw_matrix_v35(st.session_state.active_cryptos, True)
draw_matrix_v35(st.session_state.active_forex, False)
