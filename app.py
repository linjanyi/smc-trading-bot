import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import pytz
import time
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 頁面與時區配置 ---
st.set_page_config(page_title="SMC Pro Matrix", layout="wide", initial_sidebar_state="expanded")
# 每 60 秒自動刷新全域數據
st_autorefresh(interval=60000, key="global_sync_scan")
tw_tz = pytz.timezone('Asia/Taipei')

# --- 2. 側邊欄：專業風控與選單 ---
with st.sidebar:
    st.header("👤 帳戶風控設定")
    balance = st.number_input("帳戶總資金 (USD)", value=10000, step=1000)
    risk_pct = st.slider("單筆風險 (%)", 0.5, 5.0, 1.0) / 100
    rr_target = st.sidebar.slider("目標盈虧比 (R/R)", 2.0, 5.0, 3.0)
    is_mute = st.checkbox("🔇 靜音模式 (隱藏警報音)", value=False)
    
    st.divider()
    st.header("🌍 市場篩選")
    crypto_options = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "DOGE-USD"]
    forex_options = ["GC=F", "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "NQ=F"]
    
    selected_cryptos = st.multiselect("🌌 加密貨幣", crypto_options, default=["BTC-USD", "ETH-USD"])
    selected_forex = st.multiselect("💵 外匯/黃金/美指", forex_options, default=["GC=F", "EURUSD=X"])
    total_list = selected_cryptos + selected_forex

# --- 3. 核心數據運算引擎 (含 30D 回測) ---
@st.cache_data(ttl=600)
def get_full_analysis(symbol):
    try:
        # 下載 1H 與 4H 數據
        df_1h = yf.download(symbol, period='30d', interval='1h', auto_adjust=True, progress=False)
        df_4h = yf.download(symbol, period='60d', interval='4h', auto_adjust=True, progress=False)
        
        for d in [df_1h, df_4h]:
            if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
        
        if df_1h.empty or df_4h.empty: return None

        # --- 30D 歷史勝率回測 ---
        df_1h['EMA200'] = df_1h['Close'].ewm(span=200, adjust=False).mean()
        df_1h['ATR'] = (df_1h['High'] - df_1h['Low']).rolling(14).mean()
        
        # 簡單模擬進場
        bull_hits = (df_1h['Low'] > df_1h['High'].shift(2)) & (df_1h['Close'] > df_1h['EMA200'])
        bear_hits = (df_1h['High'] < df_1h['Low'].shift(2)) & (df_1h['Close'] < df_1h['EMA200'])
        
        df_1h['Backtest_Sig'] = 0
        df_1h.loc[bull_hits, 'Backtest_Sig'] = 1
        df_1h.loc[bear_hits, 'Backtest_Sig'] = -1
        
        rets = (df_1h['Backtest_Sig'].shift(1) * df_1h['Close'].pct_change()).dropna()
        # 模擬止損(-0.5%)與止盈(+1.5%)
        final_rets = rets.clip(lower=-0.005, upper=0.005 * rr_target)
        
        total_trades = len(final_rets[final_rets != 0])
        wins = len(final_rets[final_rets > 0])
        wr = (wins / total_trades * 100) if total_trades > 0 else 0
        profit = (np.prod(1 + final_rets) - 1) * 100
        
        # --- 4H 大週期趨勢 ---
        df_4h['EMA'] = df_4h['Close'].ewm(span=200, adjust=False).mean()
        htf_trend = 1 if df_4h['Close'].iloc[-1] > df_4h['EMA'].iloc[-1] else -1
        
        return {"df": df_1h, "wr": wr, "profit": profit, "htf": htf_trend}
    except Exception as e:
        return None

# --- 4. 介面渲染與即時監控 ---
now_tw = datetime.now(tw_tz)
st.title("🏹 SMC 全球量化導航終端")
st.info(f"🇹🇼 台灣時間: `{now_tw.strftime('%Y-%m-%d %H:%M:%S')}` | 每筆虧損預算: `${balance * risk_pct:.0f}` USD")

if not total_list:
    st.warning("👈 請在左側選單勾選監控目標 (如 BTC, 黃金, 歐美)")
else:
    cols = st.columns(3)
    # 用於防止重複報警的快取
    if "last_signals" not in st.session_state: st.session_state.last_signals = {}

    for i, symbol in enumerate(total_list):
        with cols[i % 3]:
            res = get_full_analysis(symbol)
            if res:
                df, wr, profit, htf = res['df'], res['wr'], res['profit'], res['htf']
                last = df.iloc[-1]
                curr_p, atr = last['Close'], last['ATR']
                
                st.subheader(f"{symbol}")
                st.write(f"📊 30D 獲利: **{profit:.1f}%** | 勝率: **{wr:.1f}%**")
                st.caption(f"4H 大趨勢: **{'📈 看多' if htf==1 else '📉 看空'}**")
                
                # SMC 實時判定
                bull_g = last['Low'] - df.iloc[-3]['High']
                bear_g = df.iloc[-3]['Low'] - last['High']
                
                sig_key = f"{symbol}_{last.name}"
                signal_type = None

                if bull_g > (atr * 0.5) and curr_p > last['EMA200']:
                    signal_type = "BUY"
                    status = "🔥 強力多單" if htf == 1 else "⚠️ 逆勢多單"
                    st.success(status)
                    sl = curr_p - (atr * 2)
                elif bear_g > (atr * 0.5) and curr_p < last['EMA200']:
                    signal_type = "SELL"
                    status = "🔥 強力空單" if htf == -1 else "⚠️ 逆勢空單"
                    st.error(status)
                    sl = curr_p + (atr * 2)
                else:
                    st.info("🔎 監控中 (無缺口)")

                # 報警與倉位建議
                if signal_type:
                    # 計算建議下單量
                    risk_amt = balance * risk_pct
                    price_diff = abs(curr_p - sl)
                    pos_size = risk_amt / price_diff if price_diff != 0 else 0
                    
                    st.warning(f"📏 **倉位建議**")
                    st.write(f"下單量: **{pos_size:.4f}**")
                    st.write(f"止損: `{sl:.4f}` | 止盈: `{curr_p + (curr_p-sl)*rr_target:.4f}`")
                    
                    # 觸發警報 (若為強力共振且未報過警)
                    if "🔥" in status and st.session_state.last_signals.get(symbol) != sig_key:
                        if not is_mute:
                            st.components.v1.html('<audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3"></audio>', height=0)
                        st.session_state.last_signals[symbol] = sig_key
                        st.toast(f"🔔 {symbol} 偵測到強力進場訊號！", icon='🚀')
                
                st.divider()
            else:
                st.error(f"{symbol} 數據獲取失敗")
