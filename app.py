import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import pytz
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 初始化頁面配置 ---
st.set_page_config(page_title="SMC Smart Matrix V16", layout="wide")
# 每 60 秒全自動刷新介面
st_autorefresh(interval=60000, key="v16_global_refresh")
tw_tz = pytz.timezone('Asia/Taipei')

# --- 2. 獨立會話記憶邏輯 (Session Persistence) ---
# 確保每個使用者打開時都有獨立的預設值，且刷新後不會重置
if "account_balance" not in st.session_state:
    st.session_state.account_balance = 10000
if "risk_ratio" not in st.session_state:
    st.session_state.risk_ratio = 1.0
if "selected_cryptos" not in st.session_state:
    st.session_state.selected_cryptos = ["BTC-USD", "ETH-USD"]
if "selected_forex" not in st.session_state:
    st.session_state.selected_forex = ["GC=F", "EURUSD=X"]

# --- 3. 頂部互動式打勾選單與設定 ---
st.title("🛡️ SMC 智慧量化監控終端 V16")
now_tw = datetime.now(tw_tz)
st.caption(f"🕒 台北時間: {now_tw.strftime('%Y-%m-%d %H:%M:%S')} | 每分鐘自動掃描中")

# 使用橫向佈局讓打勾選單與設定更直觀
config_col1, config_col2, config_col3 = st.columns([1, 2, 2])

with config_col1:
    st.markdown("#### 💰 風控設定")
    st.session_state.account_balance = st.number_input("帳戶本金 (USD)", value=st.session_state.account_balance, step=1000)
    st.session_state.risk_ratio = st.slider("單筆風險 (%)", 0.1, 5.0, st.session_state.risk_ratio)

with config_col2:
    st.markdown("#### 🌌 加密貨幣 (打勾選擇)")
    crypto_list = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "DOGE-USD", "XRP-USD"]
    st.session_state.selected_cryptos = st.multiselect("選取品種", crypto_list, default=st.session_state.selected_cryptos)

with config_col3:
    st.markdown("#### 💵 外匯與商品 (打勾選擇)")
    forex_list = ["GC=F", "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "NQ=F", "BTC-USD"]
    st.session_state.selected_forex = st.multiselect("選取品種", forex_list, default=st.session_state.selected_forex)

# 整合最終監控清單 (去重)
total_monitor = list(dict.fromkeys(st.session_state.selected_cryptos + st.session_state.selected_forex))

# --- 4. 數據計算引擎 (帶快取優化) ---
@st.cache_data(ttl=300)
def analyze_market(symbol):
    try:
        # 抓取 1H 與 4H 數據
        df_1h = yf.download(symbol, period='30d', interval='1h', auto_adjust=True, progress=False)
        df_4h = yf.download(symbol, period='60d', interval='4h', auto_adjust=True, progress=False)
        
        for d in [df_1h, df_4h]:
            if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
        
        if df_1h.empty: return None

        # 1H 指標與 30D 勝率統計
        df_1h['EMA'] = df_1h['Close'].ewm(span=200, adjust=False).mean()
        df_1h['ATR'] = (df_1h['High'] - df_1h['Low']).rolling(14).mean()
        
        # 4H 大趨勢
        df_4h['EMA'] = df_4h['Close'].ewm(span=200, adjust=False).mean()
        htf_trend = 1 if df_4h['Close'].iloc[-1] > df_4h['EMA'].iloc[-1] else -1
        
        return {"df": df_1h, "htf": htf_trend}
    except:
        return None

# --- 5. 矩陣內容渲染 ---
st.divider()

if not total_monitor:
    st.info("💡 請在上方勾選您想監控的品種，系統將自動開始即時掃描。")
else:
    # 根據勾選數量動態分配列數 (最多三列)
    cols = st.columns(3)
    for i, sym in enumerate(total_monitor):
        with cols[i % 3]:
            res = analyze_market(sym)
            if res:
                df, htf = res['df'], res['htf']
                last = df.iloc[-1]
                curr_p, atr = last['Close'], last['ATR']
                
                # 介面顯示卡片
                with st.container():
                    st.markdown(f"### {sym}")
                    st.write(f"當前價格: **{curr_p:.4f}**")
                    st.caption(f"大週期趨勢: {'📈 多頭主導' if htf==1 else '📉 空頭主導'}")
                    
                    # SMC 判定邏輯
                    bull_gap = last['Low'] - df.iloc[-3]['High']
                    bear_gap = df.iloc[-3]['Low'] - last['High']
                    
                    signal = None
                    if bull_gap > (atr * 0.5) and curr_p > last['EMA']:
                        signal = "BUY"
                        status_text = "🔥 強力共振多單" if htf == 1 else "⚠️ 逆勢多單"
                        st.success(status_text)
                        sl = curr_p - (atr * 2)
                    elif bear_gap > (atr * 0.5) and curr_p < last['EMA']:
                        signal = "SELL"
                        status_text = "🔥 強力共振空單" if htf == -1 else "⚠️ 逆勢空單"
                        st.error(status_text)
                        sl = curr_p + (atr * 2)
                    else:
                        st.info("🔎 市場結構觀察中...")

                    # 倉位建議
                    if signal:
                        risk_usd = st.session_state.account_balance * (st.session_state.risk_ratio / 100)
                        price_diff = abs(curr_p - sl)
                        pos_size = risk_usd / price_diff if price_diff != 0 else 0
                        
                        # 使用 code 區塊方便複製數據
                        st.markdown("**📋 交易執行建議**")
                        st.code(f"建議下單量: {pos_size:.4f}\n止損位 (SL): {sl:.4f}\n止盈位 (TP): {curr_p + (curr_p-sl)*3:.4f}")
                st.divider()
            else:
                st.error(f"{sym} 數據加載失敗")
