"""
=====================================================================================
무한매수법 V4.0 - 레버리지 ETF 퀀트 대시보드 (거래 내역 이미지 완벽 연동 버전)
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
# 0. 페이지 설정 및 깔끔한 라이트 테마 & 입력창 테두리 CSS
# =================================================================================
st.set_page_config(page_title="무한매수법 V4.0 대시보드", layout="wide", page_icon="🔥")

CLEAN_LIGHT_CSS = """
<style>
    .stApp { background-color: #F8F9FA; color: #212529; }
    section[data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #E9ECEF; }
    section[data-testid="stSidebar"] * { color: #212529 !important; }
    h1, h2, h3, h4 { color: #111315; font-weight: 800; }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF; border-radius: 14px !important;
        border: 1px solid #CED4DA !important; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.02);
    }
    input, div[data-testid="stNumberInput"] input, div[data-baseweb="select"] > div {
        border: 1px solid #CED4DA !important; border-radius: 8px !important;
    }
    div[data-testid="stMetric"] {
        background-color: #F8F9FA; border-radius: 10px; padding: 10px 14px; border: 1px solid #E9ECEF;
    }
    [data-testid="stMetricValue"] { font-size: 1.4rem; font-weight: 800; color: #111315; }
    [data-testid="stMetricLabel"] { font-size: 0.82rem; color: #6C757D; font-weight: 600; }
    .stTabs [data-baseweb="tab"] { font-weight: 700; font-size: 0.95rem; color: #495057; }
    .stTabs [aria-selected="true"] { color: #2563EB !important; }
    .stTabs [data-baseweb="tab-highlight"] { background-color: #2563EB !important; }
    .badge-v4 { display: inline-block; background: #DCFCE7; color: #166534; font-weight: 800; border-radius: 6px; padding: 3px 8px; font-size: 0.8rem; border: 1px solid #BBF7D0; vertical-align: middle; margin-left: 8px; }
    .badge-orange { display: inline-block; background: #FFF4ED; color: #C2410C; font-weight: 800; border-radius: 8px; padding: 6px 12px; font-size: 0.85rem; border: 1px solid #FFEDD5; }
    .badge-purple { display: inline-block; background: #F3E8FF; color: #7E22CE; font-weight: 800; border-radius: 8px; padding: 6px 12px; font-size: 0.85rem; border: 1px solid #E9D5FF; }
    .badge-blue { display: inline-block; background: #EFF6FF; color: #1D4ED8; font-weight: 800; border-radius: 8px; padding: 6px 12px; font-size: 0.85rem; border: 1px solid #DBEAFE; }
</style>
"""
st.markdown(CLEAN_LIGHT_CSS, unsafe_allow_html=True)


# =================================================================================
# 1. 영구 데이터 저장소 (Atomic Save & Auto-Save)
# =================================================================================
DATA_PATH = Path(__file__).parent / "user_settings.json"
_FILE_LOCK = threading.Lock()

DEFAULT_SETTINGS = {
    "ticker": "TQQQ",
    "split_n": 20,
    "total_principal": 10000.0,
    "current_shares": 0,
    "avg_price": 0.0,
    "t_value": 0.0,
    "use_manual_market_data": False,
    "manual_prev_close": 0.0,
    "manual_ma5": 0.0,
    "trade_history": [],  # 스크린샷 형태의 거래 내역 리스트
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
# 2. 야후 파이낸스 데이터 자동 로드 함수
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
    st.markdown("### 🚀 Road to Billionaire")
    st.divider()

    st.markdown("#### ⚙️ 기본 설정")
    ticker_val = st.selectbox("종목 선택", ["TQQQ", "SOXL"], index=0 if st.session_state.ticker == "TQQQ" else 1, key="sb_ticker")
    if ticker_val != st.session_state.ticker:
        update_setting("ticker", ticker_val)
        st.rerun()

    split_n_val = st.selectbox("분할 수 (Split_N)", [20, 40], index=0 if st.session_state.split_n == 20 else 1, key="sb_split_n")
    if split_n_val != st.session_state.split_n:
        update_setting("split_n", split_n_val)
        st.rerun()

    st.markdown("#### 💰 자산 상태")
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
    st.metric("남은 잔금 (자동계산)", f"${remaining_cash:,.2f}")

    st.divider()
    st.markdown("#### 🌐 시장 데이터")
    auto_close, auto_ma5 = fetch_market_data(st.session_state.ticker)

    use_manual = st.checkbox("수동으로 가격 입력하기", value=st.session_state.use_manual_market_data, key="sb_use_manual")
    if use_manual != st.session_state.use_manual_market_data:
        update_setting("use_manual_market_data", use_manual)
        st.rerun()

    if use_manual:
        m_close = st.number_input("전일 종가 수동 입력 ($)", value=float(st.session_state.manual_prev_close), step=0.01, key="sb_m_close")
        if m_close != st.session_state.manual_prev_close:
            update_setting("manual_prev_close", m_close)
        m_ma5 = st.number_input("5일 평균 수동 입력 ($)", value=float(st.session_state.manual_ma5), step=0.01, key="sb_m_ma5")
        if m_ma5 != st.session_state.manual_ma5:
            update_setting("manual_ma5", m_ma5)
        prev_close = m_close
        ma5 = m_ma5
    else:
        if auto_close is not None:
            prev_close = auto_close
            ma5 = auto_ma5
            st.success(f"야후 연동 성공!\n- 전일종가: ${prev_close}\n- 5일평균: ${ma5}")
        else:
            st.warning("야후 데이터를 불러오지 못했습니다. 수동 입력을 켜주세요.")
            prev_close, ma5 = 0.0, 0.0


# =================================================================================
# 4. 핵심 연산 로직
# =================================================================================
ticker = st.session_state.ticker
split_n = st.session_state.split_n
t_value = st.session_state.t_value
avg_price = st.session_state.avg_price
current_shares = st.session_state.current_shares
half_split = split_n / 2

target_pct = 0.15 if ticker == "TQQQ" else 0.20
reverse_exit_price = avg_price * (1 - target_pct)

if t_value >= split_n - 1:
    if prev_close > 0 and prev_close > reverse_exit_price:
        detected_mode = "일반모드 - 후반전"
        stage_type = "B"
    else:
        stage_type = "D" if t_value >= split_n else "C"
        detected_mode = "리버스모드"
else:
    stage_type = "A" if t_value < half_split else "B"
    detected_mode = "일반모드 - 전반전" if t_value < half_split else "일반모드 - 후반전"

def get_star_percent(ticker: str, split_n: int, t: float) -> float:
    if ticker == "TQQQ":
        return (15 - 1.5 * t) / 100 if split_n == 20 else (15 - 0.75 * t) / 100
    else:
        return (20 - 2 * t) / 100 if split_n == 20 else (20 - t) / 100

star_pct = get_star_percent(ticker, split_n, t_value)
star_price_normal = avg_price * (1 + star_pct) if avg_price > 0 else 0.0
buy_point_price_normal = star_price_normal - 0.01 if star_price_normal > 0 else 0.0

remaining_cash_calc = max(st.session_state.total_principal - (current_shares * avg_price), 0.0)
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
        if n - base_qty > 500:
            break
    return ladder


# =================================================================================
# 5. 메인 화면 UI 구성
# =================================================================================
st.markdown(f"<h1>{ticker} <span class='badge-v4'>V4.0</span></h1>", unsafe_allow_html=True)

# 상단 포트폴리오 진행 상황 카드
with st.container(border=True):
    st.markdown("#### 📊 포트폴리오 진행 상황")
    progress_ratio = min(t_value / split_n, 1.0) if split_n > 0 else 0.0
    st.progress(progress_ratio, text=f"진행률: {progress_ratio*100:.1f}% (T = {t_value:g} / {split_n}분할)")

    invested_amount = current_shares * avg_price

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("총 시드", f"${st.session_state.total_principal:,.0f}")
    c2.metric("사용한 시드", f"${invested_amount:,.2f}")
    c3.metric("평단가", f"${avg_price:,.2f}")
    c4.metric("보유 수량", f"{current_shares:,} 주")
    c5.metric("현재 모드", detected_mode.split(" ")[0])

    badge_c1, badge_c2 = st.columns([1, 4])
    with badge_c1:
        st.markdown(f"<span class='badge-orange'>T값 {t_value:g}</span>", unsafe_allow_html=True)
    with badge_c2:
        star_display = f"{star_pct*100:.2f}%" if stage_type in ("A", "B") else "—"
        st.markdown(f"<span class='badge-purple'>Star값 {star_display}</span> &nbsp; <span class='badge-blue'>{detected_mode}</span>", unsafe_allow_html=True)


# 탭 구성
tab1, tab2 = st.tabs(["🎯 오늘의 매수/매도 가이드", "⚡ 거래 내역 빠른 입력 (이미지 연동)"])

with tab1:
    st.subheader("오늘의 주문 전략 가이드")
    
    if stage_type in ("A", "B"):
        col_m1, col_m2 = st.columns(2)
        quarter_sell_qty = math.floor(current_shares / 4)
        remain_sell_qty = current_shares - quarter_sell_qty
        target_sell_price = avg_price * (1 + target_pct)

        with col_m1:
            with st.container(border=True):
                st.markdown("#### 🔴 매도 가이드")
                st.markdown(f"**① 1/4 수량 · 별지점 LOC 매도**")
                st.metric("매도 단가", f"${star_price_normal:,.2f}", delta=f"Star {star_pct*100:.2f}%")
                st.metric("매도 수량", f"{quarter_sell_qty:,} 주")
                st.divider()
                st.markdown(f"**② 나머지 3/4 수량 · 지정가(+{target_pct*100:.0f}%) 매도**")
                st.metric("목표가 단가", f"${target_sell_price:,.2f}")
                st.metric("매도 수량", f"{remain_sell_qty:,} 주")

        with col_m2:
            with st.container(border=True):
                st.markdown("#### 🔵 매수 가이드")
                if stage_type == "A":
                    half_amt = daily_buy_amount_normal / 2
                    q_bp = math.floor(half_amt / buy_point_price_normal) if buy_point_price_normal > 0 else 0
                    q_avg = math.floor(half_amt / avg_price) if avg_price > 0 else 0
                    st.markdown("**① 절반 금액 · 매수점가 LOC 매수**")
                    st.metric("매수 단가", f"${buy_point_price_normal:,.2f}")
                    st.metric("매수 수량", f"{q_bp:,} 주")
                    st.divider()
                    st.markdown("**② 절반 금액 · 평단가 LOC 매수**")
                    st.metric("매수 단가", f"${avg_price:,.2f}")
                    st.metric("매수 수량", f"{q_avg:,} 주")
                else:
                    q_full = math.floor(daily_buy_amount_normal / buy_point_price_normal) if buy_point_price_normal > 0 else 0
                    st.markdown("**1회 매수금 전액 · 매수점가 LOC 매수**")
                    st.metric("매수 단가", f"${buy_point_price_normal:,.2f}")
                    st.metric("매수 수량", f"{q_full:,} 주")

                # 매수 가이드 박스 내부에 작고 연한 폰트의 사다리 주문 세로 정렬
                st.markdown("<div style='border-top: 1px dashed #E9ECEF; margin: 15px 0 10px 0;'></div>", unsafe_allow_html=True)
                st.markdown("<span style='color: #868E96; font-size: 0.8rem; font-weight: 700;'>🚨 폭락장 대비 50% 하락 사다리 (8단계)</span>", unsafe_allow_html=True)
                
                ladder = build_fixed_50_ladder(buy_point_price_normal, daily_buy_amount_normal)
                if ladder:
                    tot_qty = sum(i["qty"] for i in ladder)
                    tot_amt = sum(i["price"] * i["qty"] for i in ladder)
                    st.markdown(f"<span style='color: #ADB5BD; font-size: 0.75rem;'>총 추가수량: <b>{tot_qty:,}주</b> | 필요 예산: <b>${tot_amt:,.2f}</b></span>", unsafe_allow_html=True)
                    
                    ladder_rows = "".join([f"<div style='color: #ADB5BD; font-size: 0.78rem; line-height: 1.4;'>${item['price']:,.2f} x {item['qty']}주</div>" for item in ladder])
                    st.markdown(f"<div style='margin-top: 6px; background-color: #F8F9FA; padding: 6px 10px; border-radius: 6px;'>{ladder_rows}</div>", unsafe_allow_html=True)

    else:
        st.info(f"현재 **{detected_mode}** 상태입니다.")

with tab2:
    st.subheader("⚡ 거래 내역 빠른 입력 (이미지 양식 맞춤형)")
    with st.container(border=True):
        st.write("스크린샷의 양식(`매수 +1`, `매수 +0` 등 세부구분, 날짜, 체결가, 수량)에 맞춰 거래를 추가하고 계좌 상태를 실시간으로 크로스 체크하세요.")

        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            trade_action = st.selectbox("거래 구분", ["매수 +1", "매수 +0", "매도 (익절/기타)", "매도 (-1회치 이상)"])
        with col_f2:
            trade_date = st.date_input("체결 날짜", value=datetime.today())
        with col_f3:
            t_impact = st.number_input("T값 증감 수치 (예: +1, +0, -0.25 등)", value=1.0, step=0.25, format="%.2f")

        col_f4, col_f5 = st.columns(2)
        exec_price = col_f4.number_input("체결가 ($)", min_value=0.0, step=0.01, value=100.0, format="%.2f")
        exec_shares = col_f5.number_input("수량 (주)", min_value=1, step=1, value=1)
        
        total_exec_amount = exec_price * exec_shares
        st.markdown(f"<span style='color: #495057; font-size: 0.85rem;'>💡 총 거래액 자동 계산: <b>${total_exec_amount:,.2f}</b> (${exec_price:,.2f} × {exec_shares}주)</span>", unsafe_allow_html=True)

        if st.button("➕ 거래 내역 추가 및 계좌 반영", type="primary"):
            # 1. 히스토리 리스트에 추가
            history_list = st.session_state.get("trade_history", [])
            new_record = {
                "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
                "action": trade_action,
                "date": trade_date.strftime("%Y.%m.%d"),
                "price": round(exec_price, 2),
                "shares": int(exec_shares),
                "amount": round(total_exec_amount, 2),
                "t_impact": float(t_impact)
            }
            history_list.insert(0, new_record)
            update_setting("trade_history", history_list)

            # 2. 계좌 상태 자동 동기화 (재계산)
            # 전체 히스토리를 기반으로 현재 보유수량 및 평단가 재산출 (매수의 경우 가중평균)
            # 단, T값은 누적 합산 적용
            recalc_shares = 0
            recalc_total_cost = 0.0
            recalc_t = 0.0

            for h in history_list:
                recalc_t += h["t_impact"]
                if "매수" in h["action"]:
                    recalc_shares += h["shares"]
                    recalc_total_cost += h["amount"]
                elif "매도" in h["action"]:
                    recalc_shares = max(recalc_shares - h["shares"], 0)
                    # 매도시 잔여 주식 비율만큼 원가 차감 또는 유지 (기본 무한매수 로직 반영)

            recalc_avg_price = (recalc_total_cost / recalc_shares) if recalc_shares > 0 else 0.0

            update_setting("current_shares", recalc_shares)
            update_setting("avg_price", round(recalc_avg_price, 2))
            update_setting("t_value", round(recalc_t, 2))

            st.success("거래 내역이 추가되고 보유 수량 및 평단가, T값이 성공적으로 동기화되었습니다!")
            st.rerun()

    # 이미지 스타일의 거래 내역 테이블 출력 뷰
    st.markdown("### 📋 등록된 거래 내역 목록")
    history_list = st.session_state.get("trade_history", [])
    
    if history_list:
        if st.button("🗑️ 전체 거래 내역 초기화"):
            update_setting("trade_history", [])
            update_setting("current_shares", 0)
            update_setting("avg_price", 0.0)
            update_setting("t_value", 0.0)
            st.rerun()

        for idx, item in enumerate(history_list):
            col_h1, col_h2, col_h3, col_h4, col_h5 = st.columns([1.2, 1.5, 1.8, 1.2, 0.8])
            col_h1.markdown(f"<span style='color: #C2410C; font-weight: 800;'>{item['action']}</span>", unsafe_allow_html=True)
            col_h2.markdown(f"<span style='color: #495057;'>{item['date']}</span>", unsafe_allow_html=True)
            col_h3.markdown(f"<b>${item['price']:,.2f}</b> <span style='color: #868E96; font-size: 0.8rem;'>(${item['amount']:,.2f})</span>", unsafe_allow_html=True)
            col_h4.markdown(f"<b>{item['shares']}주</b>", unsafe_allow_html=True)
            
            # X 버튼 (개별 삭제 및 계좌 재동기화)
            if col_h5.button("✕", key=f"del_{item['id']}ــ{idx}"):
                history_list.pop(idx)
                update_setting("trade_history", history_list)
                
                # 삭제 후 계좌 상태 재계산
                recalc_shares = 0
                recalc_total_cost = 0.0
                recalc_t = 0.0
                for h in history_list:
                    recalc_t += h["t_impact"]
                    if "매수" in h["action"]:
                        recalc_shares += h["shares"]
                        recalc_total_cost += h["amount"]
                    elif "매도" in h["action"]:
                        recalc_shares = max(recalc_shares - h["shares"], 0)
                recalc_avg_price = (recalc_total_cost / recalc_shares) if recalc_shares > 0 else 0.0

                update_setting("current_shares", recalc_shares)
                update_setting("avg_price", round(recalc_avg_price, 2))
                update_setting("t_value", round(recalc_t, 2))
                st.rerun()
            st.markdown("<div style='border-bottom: 1px solid #E9ECEF; margin: 4px 0;'></div>", unsafe_allow_html=True)
    else:
        st.info("기록된 거래 내역이 없습니다. 위에서 거래 내역을 추가해 보세요.")

# 하단 푸터
st.divider()
st.caption(f"🚀 Road to Billionaire Engine | 종목: {ticker} | 분할: {split_n}회 | T값: {t_value:g}")
