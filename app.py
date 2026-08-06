"""
=====================================================================================
무한매수법 V4.0 - 레버리지 ETF 퀀트 대시보드 (최종 수정 버전)
=====================================================================================
"""

import math
import os
import json
import threading
from datetime import datetime
from pathlib import Path
import streamlit as st
import yfinance as yf

# =================================================================================
# 0. 페이지 설정 및 디자인 CSS
# =================================================================================
st.set_page_config(page_title="무한매수법 V4.0 대시보드", page_icon="🔥")

CUSTOM_UI_CSS = """
<style>
    .stApp { background-color: #F8F9FA; color: #212529; }
    
    /* 사이드바 스타일 및 keyboard_double 텍스트 완전 숨김 처리 */
    section[data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #E5E7EB; padding-top: 10px; }
    section[data-testid="stSidebar"] * { color: #212529 !important; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] { display: none; }
    section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] { display: none; }
    
    /* 기본설정 셀렉박스를 하단 입력창과 동일한 디자인으로 통일 */
    section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"], 
    section[data-testid="stSidebar"] div[data-testid="stNumberInput"] input {
        background-color: #FAFAFA !important;
        border: 1px solid #E5E7EB !important;
        border-radius: 10px !important;
    }
    
    h1, h2, h3, h4 { color: #111315; font-weight: 800; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
    
    .stTabs [data-baseweb="tab"] { font-weight: 700; font-size: 1rem; color: #4B5563; }
    .stTabs [aria-selected="true"] { color: #2563EB !important; }
    .stTabs [data-baseweb="tab-highlight"] { background-color: #2563EB !important; }
    
    .stButton button[kind="primary"] {
        background-color: #D1FAE5 !important;
        color: #065F46 !important;
        border: 1px solid #A3E635 !important;
        font-weight: 700 !important;
        border-radius: 10px !important;
    }
    .stButton button[kind="primary"]:hover {
        background-color: #A7F3D0 !important;
        color: #047857 !important;
    }
</style>
"""
st.markdown(CUSTOM_UI_CSS, unsafe_allow_html=True)


# =================================================================================
# 1. 영구 데이터 저장소 관리
# =================================================================================
DATA_PATH = Path(__file__).parent / "user_settings.json"
_FILE_LOCK = threading.Lock()

DEFAULT_SETTINGS = {
    "ticker": "SOXL",
    "split_n": 20,
    "total_principal": 30000.0,
    "current_shares": 117,
    "avg_price": 154.07,
    "t_value": 29.5,
    "trade_history": [],
}

def load_settings() -> dict:
    if not DATA_PATH.exists():
        return DEFAULT_SETTINGS.copy()
    try:
        raw = DATA_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        merged = DEFAULT_SETTINGS.copy()
        merged.update(data)
        return merged
    except Exception:
        return DEFAULT_SETTINGS.copy()

def save_settings(settings: dict) -> None:
    payload = json.dumps(settings, ensure_ascii=False, indent=2)
    with _FILE_LOCK:
        tmp_path = DATA_PATH.with_suffix(".tmp")
        try:
            tmp_path.write_text(payload, encoding="utf-8")
            os.replace(tmp_path, DATA_PATH)
        except Exception:
            pass

if "settings_loaded" not in st.session_state:
    saved = load_settings()
    for k, v in saved.items():
        st.session_state[k] = v
    st.session_state.settings_loaded = True

def update_setting(key, value):
    st.session_state[key] = value
    current_data = {k: st.session_state.get(k, DEFAULT_SETTINGS[k]) for k in DEFAULT_SETTINGS.keys()}
    save_settings(current_data)


# =================================================================================
# 2. 야후 파이낸스 데이터 로드
# =================================================================================
@st.cache_data(ttl=600)
def fetch_market_data(ticker_symbol: str):
    try:
        tk = yf.Ticker(ticker_symbol)
        df = tk.history(period="10d")
        if df.empty or len(df) < 5:
            return None, None
        prev_close = float(df['Close'].iloc[-1])
        ma5 = float(df['Close'].iloc[-5:].mean())
        return round(prev_close, 2), round(ma5, 2)
    except Exception:
        return None, None


# =================================================================================
# 3. 사이드바 설정
# =================================================================================
with st.sidebar:
    st.markdown("<div style='font-size: 1.1rem; font-weight: 800; color: #111315; margin-bottom: 5px;'>🚀 Road to Billionaire</div>", unsafe_allow_html=True)
    st.divider()

    st.markdown("<div style='font-size: 0.85rem; font-weight: 700; color: #4B5563; margin-bottom: 8px;'>⚙️ 기본 설정</div>", unsafe_allow_html=True)
    ticker_val = st.selectbox("종목 선택", ["SOXL", "TQQQ"], index=0 if st.session_state.ticker == "SOXL" else 1, key="sb_ticker")
    if ticker_val != st.session_state.ticker:
        update_setting("ticker", ticker_val)
        st.rerun()

    split_n_val = st.selectbox("분할 수 (Split_N)", [20, 40], index=0 if st.session_state.split_n == 20 else 1, key="sb_split_n")
    if split_n_val != st.session_state.split_n:
        update_setting("split_n", split_n_val)
        st.rerun()

    st.markdown("<div style='font-size: 0.85rem; font-weight: 700; color: #4B5563; margin: 15px 0 8px 0;'>💰 수동 자산 상태 (입력값 유지)</div>", unsafe_allow_html=True)
    total_principal_val = st.number_input("총 투자 원금 ($)", min_value=0.0, step=100.0, value=float(st.session_state.total_principal), key="sb_principal")
    if total_principal_val != st.session_state.total_principal:
        update_setting("total_principal", total_principal_val)

    current_shares_val = st.number_input("현재 보유 주식 수 (주)", min_value=0, step=1, value=int(st.session_state.current_shares), key="sb_shares")
    if current_shares_val != st.session_state.current_shares:
        update_setting("current_shares", current_shares_val)

    avg_price_val = st.number_input("현재 평단가 ($)", min_value=0.0, step=0.01, format="%.2f", value=float(st.session_state.avg_price), key="sb_avg_price")
    if avg_price_val != st.session_state.avg_price:
        update_setting("avg_price", avg_price_val)

    t_val = st.number_input("현재 진행 회차 (T값)", min_value=0.0, step=0.1, format="%.2f", value=float(st.session_state.t_value), key="sb_t_value")
    if t_val != st.session_state.t_value:
        update_setting("t_value", t_val)

    remaining_cash = max(st.session_state.total_principal - (st.session_state.current_shares * st.session_state.avg_price), 0.0)
    
    st.markdown(f"""
    <div style="background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 10px; padding: 12px 14px; margin-top: 10px;">
        <div style="font-size: 0.75rem; color: #6B7280; font-weight: 700;">남은 잔금</div>
        <div style="font-size: 1.1rem; font-weight: 800; color: #111315;">${remaining_cash:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()
    st.markdown("<div style='font-size: 0.85rem; font-weight: 700; color: #4B5563; margin-bottom: 8px;'>🌐 시장 데이터</div>", unsafe_allow_html=True)
    auto_close, auto_ma5 = fetch_market_data(st.session_state.ticker)

    if auto_close is not None:
        prev_close = auto_close
        ma5 = auto_ma5
        st.markdown(f"""
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
            <div style="background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 10px; padding: 10px;">
                <div style="font-size: 0.7rem; color: #6B7280; font-weight: 700;">전일 종가</div>
                <div style="font-size: 0.95rem; font-weight: 800; color: #111315;">${prev_close:,.2f}</div>
            </div>
            <div style="background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 10px; padding: 10px;">
                <div style="font-size: 0.7rem; color: #6B7280; font-weight: 700;">5일 평균가</div>
                <div style="font-size: 0.95rem; font-weight: 800; color: #111315;">${ma5:,.2f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        prev_close, ma5 = 0.0, 0.0
        st.warning("시장 데이터를 불러오지 못했습니다.")


# =================================================================================
# 4. 연산 로직
# =================================================================================
ticker = st.session_state.ticker
split_n = st.session_state.split_n
t_value = st.session_state.t_value
avg_price = st.session_state.avg_price
current_shares = st.session_state.current_shares
total_principal = st.session_state.total_principal
half_split = split_n / 2

target_pct = 0.15 if ticker == "TQQQ" else 0.20
reverse_exit_price = avg_price * (1 - target_pct)

if t_value >= split_n - 1:
    if prev_close > 0 and prev_close > reverse_exit_price:
        detected_mode = "후반전"
        stage_type = "B"
    else:
        stage_type = "D" if t_value >= split_n else "C"
        detected_mode = "리버스모드"
else:
    stage_type = "A" if t_value < half_split else "B"
    detected_mode = "전반전" if t_value < half_split else "후반전"

def get_star_percent(ticker: str, split_n: int, t: float) -> float:
    if ticker == "TQQQ":
        return (15 - 1.5 * t) / 100 if split_n == 20 else (15 - 0.75 * t) / 100
    else:
        return (20 - 2 * t) / 100 if split_n == 20 else (20 - t) / 100

star_pct = get_star_percent(ticker, split_n, t_value)
star_price_normal = avg_price * (1 + star_pct) if avg_price > 0 else 0.0
buy_point_price_normal = star_price_normal - 0.01 if star_price_normal > 0 else 0.0

used_amount_calc = current_shares * avg_price
progress_ratio = min(used_amount_calc / total_principal, 1.0) if total_principal > 0 else 0.0

remaining_cash_calc = max(total_principal - used_amount_calc, 0.0)
daily_buy_amount_normal = remaining_cash_calc / (split_n - t_value) if (split_n - t_value) > 0 else 0.0

def build_fixed_50_ladder(base_price: float, base_amount: float):
    if base_price <= 0 or base_amount <= 0:
        return []
    base_qty = math.floor(base_amount / base_price)
    floor_price = base_price * 0.5
    ladder = []
    n = base_qty + 1
    while True:
        price = base_amount / n
        if price < floor_price:
            break
        ladder.append({"price": round(price, 2), "qty": 1})
        n += 1
        if n - base_qty > 7:
            break
    return ladder


# =================================================================================
# 5. 메인 UI 구성 (좌우 여백 컬럼 및 본문 통합 배치 + unsafe_allow_html 적용)
# =================================================================================
_, main_content_col, _ = st.columns([1, 10, 1])

with main_content_col:
    st.markdown(f"""
    <div style="display: flex; align-items: center; margin-bottom: 20px;">
        <h1 style="margin: 0; font-size: 1.8rem;">{ticker}</h1>
        <span style="background: #DBEAFE; color: #1E40AF; font-weight: 800; border-radius: 6px; padding: 2px 8px; font-size: 0.75rem; margin-left: 8px;">Ver 4</span>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["🎯 오늘의 매수/매도 가이드", "⚡ 거래내역 입력", "🔍 거래내역 크로스체크"])

    # ---------------------------------------------------------------------------------
    # [Tab 1] 오늘의 매수/매도 가이드
    # ---------------------------------------------------------------------------------
    with tab1:
        q_full = math.floor(daily_buy_amount_normal / buy_point_price_normal) if buy_point_price_normal > 0 else 0
        ladder = build_fixed_50_ladder(buy_point_price_normal, daily_buy_amount_normal)
        ladder_html_items = "".join([f"<div style='font-size: 0.82rem; color: #6B7280; margin-bottom: 4px;'>- LOC ${item['price']:,.2f} × {item['qty']}주</div>" for item in ladder])
        ladder_section = f"""
        <div style="background: #FAFAFA; border: 1px solid #F3F4F6; border-radius: 12px; padding: 16px 18px; margin-top: 14px;">
            <div style="font-size: 0.78rem; color: #DC2626; font-weight: 700; margin-bottom: 10px;">+@ 폭락장 대비 추가 매수</div>
            {ladder_html_items}
        </div>
        """ if ladder else ""

        quarter_sell_qty = math.floor(current_shares / 4)
        remain_sell_qty = current_shares - quarter_sell_qty
        target_sell_price = avg_price * (1 + target_pct)
        star_display_str = f"{star_pct*100:.2f}%" if stage_type in ("A", "B") else "—"

        st.markdown(f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
            <!-- 진행 상황 카드 -->
            <div style="background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 16px; padding: 24px; box-shadow: 0 4px 16px rgba(0,0,0,0.02); margin-bottom: 20px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <span style="font-size: 1.1rem; font-weight: 800; color: #111315;">진행 상황</span>
                    <span style="font-size: 0.95rem; font-weight: 700; color: #2563EB;">{progress_ratio*100:.1f}%</span>
                </div>
                <div style="background: #E5E7EB; border-radius: 999px; height: 10px; width: 100%; overflow: hidden; margin-bottom: 20px;">
                    <div style="background: #2563EB; width: {progress_ratio*100}%; height: 100%; border-radius: 999px;"></div>
                </div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
                    <div>
                        <div style="font-size: 0.75rem; color: #6B7280; font-weight: 700; margin-bottom: 4px;">시드</div>
                        <div style="font-size: 1.4rem; font-weight:
