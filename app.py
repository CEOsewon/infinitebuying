"""
=====================================================================================
무한매수법 V4.0 - 레버리지 ETF 퀀트 대시보드 (스크린샷 레이아웃 최종 버전)
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
st.set_page_config(page_title="무한매수법 V4.0 대시보드", layout="wide", page_icon="🔥")

CUSTOM_UI_CSS = """
<style>
    .stApp { background-color: #F8F9FA; color: #212529; }
    section[data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #E9ECEF; }
    section[data-testid="stSidebar"] * { color: #212529 !important; }
    h1, h2, h3, h4 { color: #111315; font-weight: 800; }
    
    input, div[data-testid="stNumberInput"] input, div[data-baseweb="select"] > div {
        border: 1px solid #CED4DA !important; border-radius: 8px !important;
    }
    div[data-testid="stMetric"] {
        background-color: #F8F9FA; border-radius: 10px; padding: 10px 14px; border: 1px solid #E9ECEF;
    }
    [data-testid="stMetricValue"] { font-size: 1.2rem; font-weight: 800; color: #111315; }
    [data-testid="stMetricLabel"] { font-size: 0.75rem; color: #6C757D; font-weight: 600; }
    
    .stTabs [data-baseweb="tab"] { font-weight: 700; font-size: 1rem; color: #4B5563; }
    .stTabs [aria-selected="true"] { color: #2563EB !important; }
    .stTabs [data-baseweb="tab-highlight"] { background-color: #2563EB !important; }
    
    .badge-v4 { display: inline-block; background: #DBEAFE; color: #1E40AF; font-weight: 800; border-radius: 6px; padding: 2px 8px; font-size: 0.75rem; vertical-align: middle; margin-left: 6px; }
    
    /* 파스텔 그린 커스텀 버튼 */
    .stButton button[kind="primary"] {
        background-color: #D1FAE5 !important;
        color: #065F46 !important;
        border: 1px solid #A3E635 !important;
        font-weight: 700 !important;
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
# 3. 사이드바 설정 (크로스체크 기능 포함)
# =================================================================================
with st.sidebar:
    st.markdown("### 🚀 Road to Billionaire")
    st.divider()

    st.markdown("#### ⚙️ 기본 설정")
    ticker_val = st.selectbox("종목 선택", ["SOXL", "TQQQ"], index=0 if st.session_state.ticker == "SOXL" else 1, key="sb_ticker")
    if ticker_val != st.session_state.ticker:
        update_setting("ticker", ticker_val)
        st.rerun()

    split_n_val = st.selectbox("분할 수 (Split_N)", [20, 40], index=0 if st.session_state.split_n == 20 else 1, key="sb_split_n")
    if split_n_val != st.session_state.split_n:
        update_setting("split_n", split_n_val)
        st.rerun()

    st.markdown("#### 💰 수동 자산 상태 (입력값 유지)")
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
    st.metric("남은 잔금", f"${remaining_cash:,.2f}")

    # 거래내역 기반 자동 계산값 산출 (크로스체크용)
    history_list = st.session_state.get("trade_history", [])
    calc_shares, calc_total_cost, calc_t = 0, 0.0, 0.0
    for h in history_list:
        calc_t += h["t_impact"]
        if "매수" in h["action"]:
            calc_shares += h["shares"]
            calc_total_cost += h["amount"]
        elif "매도" in h["action"] or "전량" in h["action"]:
            calc_shares = max(calc_shares - h["shares"], 0)
    calc_avg = (calc_total_cost / calc_shares) if calc_shares > 0 else 0.0

    st.divider()
    st.markdown("#### 🔍 거래내역 크로스체크")
    st.markdown(f"<div style='font-size:0.8rem; color:#6B7280; margin-bottom:8px;'>입력값과 거래기록 누적값을 비교합니다.</div>", unsafe_allow_html=True)
    st.markdown(f"- **기록된 거래 건수**: {len(history_list)}건")
    st.markdown(f"- **거래기록상 주식수**: {calc_shares}주 (현재 설정: {st.session_state.current_shares}주)")
    st.markdown(f"- **거래기록상 평단가**: ${calc_avg:,.2f} (현재 설정: ${st.session_state.avg_price:,.2f})")
    st.markdown(f"- **거래기록상 T값**: {calc_t:g} (현재 설정: {st.session_state.t_value:g})")

    if len(history_list) > 0 and (calc_shares != st.session_state.current_shares or abs(calc_avg - st.session_state.avg_price) > 0.01):
        if st.button("🔄 거래내역 값으로 사이드바 동기화", use_container_width=True):
            update_setting("current_shares", calc_shares)
            update_setting("avg_price", round(calc_avg, 2))
            update_setting("t_value", round(max(calc_t, 0.0), 2))
            st.rerun()

    st.divider()
    st.markdown("#### 🌐 시장 데이터")
    auto_close, auto_ma5 = fetch_market_data(st.session_state.ticker)

    if auto_close is not None:
        prev_close = auto_close
        ma5 = auto_ma5
        st.metric("전일 종가", f"${prev_close:,.2f}")
        st.metric("5일 평균가", f"${ma5:,.2f}")
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
# 5. 메인 UI 구성 (스크린샷 레이아웃 반영)
# =================================================================================
st.markdown(f"""
<div style="display: flex; align-items: center; margin-bottom: 20px;">
    <h1 style="margin: 0; font-size: 1.8rem;">{ticker}</h1>
    <span class='badge-v4'>Ver 4</span>
</div>
""", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["🎯 오늘의 매수/매도 가이드", "⚡ 거래내역 입력"])

with tab1:
    # 1. 스크린샷 스타일 진행 상황 카드 박스
    st.markdown(f"""
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
                <div style="font-size: 1.4rem; font-weight: 800; color: #111315;">{total_principal:,.0f} <span style="font-size: 0.85rem; color: #6B7280; font-weight: 600;">USD</span></div>
            </div>
            <div>
                <div style="font-size: 0.75rem; color: #6B7280; font-weight: 700; margin-bottom: 4px;">사용한 시드</div>
                <div style="font-size: 1.4rem; font-weight: 800; color: #111315;">{used_amount_calc:,.2f} <span style="font-size: 0.85rem; color: #6B7280; font-weight: 600;">USD</span></div>
            </div>
        </div>
        
        <div style="border-top: 1px solid #F3F4F6; padding-top: 16px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px;">
            <div>
                <div style="font-size: 0.75rem; color: #6B7280; font-weight: 700; margin-bottom: 4px;">매입 금액</div>
                <div style="font-size: 1.1rem; font-weight: 800; color: #111315;">{used_amount_calc:,.2f} <span style="font-size: 0.75rem; color: #6B7280;">USD</span></div>
            </div>
            <div>
                <div style="font-size: 0.75rem; color: #6B7280; font-weight: 700; margin-bottom: 4px;">평단가</div>
                <div style="font-size: 1.1rem; font-weight: 800; color: #111315;">{avg_price:,.3f} <span style="font-size: 0.75rem; color: #6B7280;">USD</span></div>
            </div>
            <div>
                <div style="font-size: 0.75rem; color: #6B7280; font-weight: 700; margin-bottom: 4px;">보유 수량</div>
                <div style="font-size: 1.1rem; font-weight: 800; color: #111315;">{current_shares:,} <span style="font-size: 0.75rem; color: #6B7280;">주</span></div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 2. 무한 매수법 가이드 메인 박스
    col_guide_title, col_t_badge, col_star_badge = st.columns([2, 1, 1])
    
    with col_guide_title:
        st.markdown("<h3 style='margin-top: 10px; font-size: 1.4rem;'>무한 매수법 가이드</h3>", unsafe_allow_html=True)
    with col_t_badge:
        st.markdown(f"""
        <div style="background: #FFFBEB; border: 1px solid #FDE68A; border-radius: 14px; padding: 10px 14px; text-align: center;">
            <div style="font-size: 0.7rem; color: #D97706; font-weight: 700;">T 값</div>
            <div style="font-size: 1.1rem; font-weight: 800; color: #111315;">{t_value:g} <span style="font-size: 0.75rem;">회</span></div>
        </div>
        """, unsafe_allow_html=True)
    with col_star_badge:
        star_display = f"{star_pct*100:.2f}%" if stage_type in ("A", "B") else "—"
        st.markdown(f"""
        <div style="background: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 14px; padding: 10px 14px; text-align: center;">
            <div style="font-size: 0.7rem; color: #2563EB; font-weight: 700;">Star 값</div>
            <div style="font-size: 1.1rem; font-weight: 800; color: #111315;">{star_display}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin: 10px 0;'></div>", unsafe_allow_html=True)

    # Current State 표시
    st.markdown(f"""
    <div style="background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 14px; padding: 14px 20px; display: flex; align-items: center; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.01);">
        <span style="background: #EFF6FF; color: #2563EB; padding: 6px 10px; border-radius: 8px; margin-right: 12px; font-size: 1rem;">📄</span>
        <div>
            <div style="font-size: 0.7rem; color: #6B7280; font-weight: 700; letter-spacing: 0.5px;">CURRENT STATE</div>
            <div style="font-size: 1.1rem; font-weight: 800; color: #111315;">{detected_mode}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 3. 매수 / 매도 가이드 그리드 박스
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        q_full = math.floor(daily_buy_amount_normal / buy_point_price_normal) if buy_point_price_normal > 0 else 0
        ladder = build_fixed_50_ladder(buy_point_price_normal, daily_buy_amount_normal)
        ladder_html = ""
        if ladder:
            ladder_items = "".join([f"<div style='font-size: 0.82rem; color: #6B7280; margin-bottom: 5px;'>- LOC ${item['price']:,.2f} × {item['qty']}주</div>" for item in ladder])
            ladder_html = f"""
            <div style="background: #FAFAFA; border: 1px solid #F3F4F6; border-radius: 12px; padding: 16px 18px; margin-top: 14px;">
                <div style="font-size: 0.78rem; color: #9CA3AF; font-weight: 700; margin-bottom: 10px;">+@ 폭락장 대비 추가 매수</div>
                {ladder_items}
            </div>
            """

        st.markdown(f"""
        <div style="background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 16px; padding: 24px; box-shadow: 0 4px 16px rgba(0,0,0,0.02);">
            <h4 style='color: #DC2626; font-size: 1.1rem; margin-top: 0; margin-bottom: 18px;'>매수 가이드</h4>
            <div style="background: #FFFDFD; border: 1px solid #FEE2E2; border-radius: 12px; padding: 18px 20px;">
                <div style="font-size: 0.8rem; color: #DC2626; font-weight: 700; margin-bottom: 6px;">LOC ★{star_pct*100:.2f}%</div>
                <div style="font-size: 1.5rem; font-weight: 800; color: #111315;">${buy_point_price_normal:,.2f} <span style="font-size: 1rem; color: #6B7280; font-weight: 600;">× {q_full:,}주</span></div>
            </div>
            {ladder_html}
        </div>
        """, unsafe_allow_html=True)

    with col_g2:
        quarter_sell_qty = math.floor(current_shares / 4)
        remain_sell_qty = current_shares - quarter_sell_qty
        target_sell_price = avg_price * (1 + target_pct)

        st.markdown(f"""
        <div style="background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 16px; padding: 24px; box-shadow: 0 4px 16px rgba(0,0,0,0.02);">
            <h4 style='color: #2563EB; font-size: 1.1rem; margin-top: 0; margin-bottom: 18px;'>매도 가이드</h4>
            <div style="background: #F8FAFC; border: 1px solid #DBEAFE; border-radius: 12px; padding: 18px 20px; margin-bottom: 14px;">
                <div style="font-size: 0.8rem; color: #2563EB; font-weight: 700; margin-bottom: 6px;">LOC ★{star_pct*100:.2f}%</div>
                <div style="font-size: 1.5rem; font-weight: 800; color: #111315;">${star_price_normal:,.2f} <span style="font-size: 1rem; color: #6B7280; font-weight: 600;">× {quarter_sell_qty:,}주</span></div>
            </div>
            <div style="background: #F8FAFC; border: 1px solid #DBEAFE; border-radius: 12px; padding: 18px 20px;">
                <div style="font-size: 0.8rem; color: #2563EB; font-weight: 700; margin-bottom: 6px;">지정가 +{target_pct*100:.0f}%</div>
                <div style="font-size: 1.5rem; font-weight: 800; color: #111315;">${target_sell_price:,.2f} <span style="font-size: 1rem; color: #6B7280; font-weight: 600;">× {remain_sell_qty:,}주</span></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

with tab2:
    st.markdown("### 거래 내역 입력")
    
    with st.container(border=True):
        st.markdown("""
        <div style="background-color: #F0F7FF; padding: 10px 14px; border-radius: 8px; border: 1px solid #D0E3FF; margin-bottom: 15px;">
            <span style="color: #1D4ED8; font-weight: 700; font-size: 0.9rem;">📝 거래 유형 선택 및 입력 (사이드바 값에 즉시 영향 주지 않음)</span>
        </div>
        """, unsafe_allow_html=True)

        col_i1, col_i2 = st.columns(2)
        trade_date = col_i1.date_input("체결 날짜", value=datetime.today())
        
        main_category = col_i2.radio("거래 대분류", ["매수", "매도"], horizontal=True)
        
        if main_category == "매수":
            sub_action = st.selectbox("매수 상세 구분", ["매수 +1", "매수 +0.5", "매수 +0"])
        else:
            sub_action = st.selectbox("매도 상세 구분", ["매도 x0.75", "전량 매도 x0"])
        
        if "+1" in sub_action:
            t_impact = 1.0
        elif "+0.5" in sub_action:
            t_impact = 0.5
        elif "+0" in sub_action:
            t_impact = 0.0
        elif "0.75" in sub_action:
            t_impact = -0.75
        else:
            t_impact = -1.0

        col_i3, col_i4 = st.columns(2)
        exec_price = col_i3.number_input("체결가 ($)", min_value=0.0, step=0.01, value=100.0, format="%.2f")
        exec_shares = col_i4.number_input("수량 (주)", min_value=1, step=1, value=1)

        if st.button("➕ 거래 내역 추가", type="primary", use_container_width=True):
            history_list = st.session_state.get("trade_history", [])
            new_record = {
                "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
                "action": sub_action,
                "date": trade_date.strftime("%Y.%m.%d"),
                "price": round(exec_price, 2),
                "shares": int(exec_shares),
                "amount": round(exec_price * exec_shares, 2),
                "t_impact": float(t_impact)
            }
            history_list.insert(0, new_record)
            update_setting("trade_history", history_list)
            st.success("거래 내역이 기록되었습니다! (사이드바 크로스체크 패널에서 비교 및 동기화 가능)")
            st.rerun()

    # 거래 내역 표
    st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
    history_list = st.session_state.get("trade_history", [])
    
    if history_list:
        if st.button("🗑️ 전체 거래기록 초기화"):
            update_setting("trade_history", [])
            st.rerun()

        th1, th2, th3, th4, th5, th6 = st.columns([1, 1.5, 1.8, 1.5, 1, 1.2])
        th1.markdown("<span style='color: #9CA3AF; font-size: 0.8rem; font-weight: 700;'>NO</span>", unsafe_allow_html=True)
        th2.markdown("<span style='color: #9CA3AF; font-size: 0.8rem; font-weight: 700;'>날짜</span>", unsafe_allow_html=True)
        th3.markdown("<span style='color: #9CA3AF; font-size: 0.8rem; font-weight: 700;'>구분</span>", unsafe_allow_html=True)
        th4.markdown("<span style='color: #9CA3AF; font-size: 0.8rem; font-weight: 700;'>체결가</span>", unsafe_allow_html=True)
        th5.markdown("<span style='color: #9CA3AF; font-size: 0.8rem; font-weight: 700;'>수량</span>", unsafe_allow_html=True)
        th6.markdown("<span style='color: #9CA3AF; font-size: 0.8rem; font-weight: 700;'>거래금액</span>", unsafe_allow_html=True)
        st.markdown("<div style='border-bottom: 1px solid #E5E7EB; margin: 8px 0;'></div>", unsafe_allow_html=True)

        total_cnt = len(history_list)
        for idx, item in enumerate(history_list):
            row_no = f"#{total_cnt - idx}"
            col_h1, col_h2, col_h3, col_h4, col_h5, col_h6 = st.columns([1, 1.5, 1.8, 1.5, 1, 1.2])
            
            col_h1.markdown(f"<span style='color: #9CA3AF; font-size: 0.85rem;'>{row_no}</span>", unsafe_allow_html=True)
            col_h2.markdown(f"<span style='color: #4B5563; font-size: 0.85rem;'>{item['date']}</span>", unsafe_allow_html=True)
            
            badge_color = "background: #FEE2E2; color: #DC2626;" if "매수" in item['action'] else "background: #DBEAFE; color: #1D4ED8;"
            col_h3.markdown(f"<span style='{badge_color} padding: 2px 6px; border-radius: 4px; font-size: 0.78rem; font-weight: 700;'>{item['action']}</span>", unsafe_allow_html=True)
            
            col_h4.markdown(f"<span style='font-weight: 700; font-size: 0.88rem;'>${item['price']:,.2f}</span>", unsafe_allow_html=True)
            col_h5.markdown(f"<span style='font-size: 0.88rem;'>{item['shares']}주</span>", unsafe_allow_html=True)
            
            sub_col_amt, sub_col_del = col_h6.columns([3, 1])
            sub_col_amt.markdown(f"<span style='font-weight: 700; font-size: 0.88rem;'>${item['amount']:,.2f}</span>", unsafe_allow_html=True)
            if sub_col_del.button("✕", key=f"del_{item['id']}_{idx}"):
                history_list.pop(idx)
                update_setting("trade_history", history_list)
                st.rerun()
                
            st.markdown("<div style='border-bottom: 1px solid #F3F4F6; margin: 6px 0;'></div>", unsafe_allow_html=True)
    else:
        st.info("기록된 거래 내역이 없습니다.")
