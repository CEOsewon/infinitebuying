"""
=====================================================================================
무한매수법 V4.0 - 레버리지 ETF(TQQQ / SOXL) 퀀트 매매 대시보드 (개인 전용 싱글탑)
=====================================================================================
- 로그인 절차 없이 접속 즉시 사용 (개인 전용 단일 저장소 구조)
- 입력 데이터 자동 저장 (user_settings.json, 원자적 저장 + 백업으로 유실/손상 방지)
- 남은 잔금 자동 계산
- 폭락장 대비 추가매수 "사다리" 주문 계산 (최대 하락률까지 1주 단위 커버)
=====================================================================================
"""

import math
import os
import json
import threading
from pathlib import Path
import streamlit as st

# =================================================================================
# 0. 기본 페이지 설정 & 스타일 (FIRE GATE 스타일 참고: 다크 사이드바 + 화이트 카드)
# =================================================================================
st.set_page_config(page_title="Road to Billionaire", layout="wide", page_icon="🔥")

CUSTOM_CSS = """
<style>
    .stApp { background-color: #F5F6FA; }

    section[data-testid="stSidebar"] {
        background-color: #14161A;
    }
    section[data-testid="stSidebar"] * { color: #F5F6FA !important; }
    section[data-testid="stSidebar"] input, section[data-testid="stSidebar"] textarea {
        color: #14161A !important;
    }

    h1, h2, h3 { color: #14161A; font-weight: 800; }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF;
        border-radius: 18px !important;
        border: 1px solid #ECEEF2 !important;
        box-shadow: 0 2px 10px rgba(20, 22, 26, 0.05);
    }

    div[data-testid="stMetric"] {
        background-color: #FAFAFC;
        border-radius: 12px;
        padding: 10px 14px;
    }
    [data-testid="stMetricValue"] { font-size: 1.55rem; font-weight: 800; color: #14161A; }
    [data-testid="stMetricLabel"] { font-size: 0.8rem; color: #8A8F9A; font-weight: 600; }

    .stTabs [data-baseweb="tab"] { font-weight: 700; font-size: 1rem; }
    .stTabs [aria-selected="true"] { color: #3B5BFF !important; }
    .stTabs [data-baseweb="tab-highlight"] { background-color: #3B5BFF !important; }

    button[kind="primary"] { background-color: #14161A !important; border: none !important; }
    button[kind="primary"]:hover { background-color: #2A2D33 !important; }

    .badge-orange {
        display:inline-block; background:#FFF1E8; color:#FF7A28; font-weight:800;
        border-radius:10px; padding:8px 14px; font-size:0.95rem;
    }
    .badge-purple {
        display:inline-block; background:#F0EEFF; color:#6C5CE7; font-weight:800;
        border-radius:10px; padding:8px 14px; font-size:0.95rem;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# =================================================================================
# 1. 개인 데이터 저장소 (JSON, 원자적 저장 + 자동 백업으로 유실 방지)
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
    "prev_close": 0.0,
    "ma5": 0.0,
    "crash_max_drop_pct": 50,
}


def load_settings() -> dict:
    if not DATA_PATH.exists():
        return DEFAULT_SETTINGS.copy()
    try:
        raw = DATA_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        # 누락된 키가 있다면 기본값으로 채워줌
        merged = DEFAULT_SETTINGS.copy()
        merged.update(data)
        return merged
    except Exception:
        return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict) -> None:
    """
    원자적 저장: 임시파일에 먼저 쓰고 os.replace로 교체하여 저장 도중 앱이 꺼져도 
    기존 파일이 절대 손상되거나 유실되지 않도록 보호합니다.
    """
    payload = json.dumps(settings, ensure_ascii=False, indent=2)
    with _FILE_LOCK:
        tmp_path = DATA_PATH.with_suffix(".tmp")
        bak_path = DATA_PATH.with_suffix(".bak")
        try:
            if DATA_PATH.exists():
                bak_path.write_text(DATA_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception:
            pass
        tmp_path.write_text(payload, encoding="utf-8")
        os.replace(tmp_path, DATA_PATH)


# 세션 상태 초기화 (최초 접속 시 파일에서 불러오기)
if "settings_loaded" not in st.session_state:
    saved = load_settings()
    for k, v in saved.items():
        st.session_state[k] = v
    st.session_state.settings_loaded = True


# =================================================================================
# 2. 핵심 계산 함수들
# =================================================================================

def get_star_percent(ticker: str, split_n: int, t: float) -> float:
    if ticker == "TQQQ":
        pct = (15 - 1.5 * t) / 100 if split_n == 20 else (15 - 0.75 * t) / 100
    else:  # SOXL
        pct = (20 - 2 * t) / 100 if split_n == 20 else (20 - t) / 100
    return pct


def get_target_profit_percent(ticker: str) -> float:
    return 0.15 if ticker == "TQQQ" else 0.20


def calc_buy_point_price(star_price: float) -> float:
    return star_price - 0.01


def calc_daily_buy_amount_normal(remaining_cash: float, split_n: int, t: float) -> float:
    denom = split_n - t
    return remaining_cash / denom if denom > 0 else 0.0


def calc_daily_buy_amount_reverse(remaining_cash: float) -> float:
    return remaining_cash / 4


def build_crash_buy_ladder(base_price: float, base_amount: float, max_drop_pct: float):
    """
    폭락장 대비 추가매수 "사다리" 계산 (Fire Gate 방식 동일 로직)
    """
    if base_price <= 0 or base_amount <= 0:
        return []
    base_qty = math.floor(base_amount / base_price)
    floor_price = base_price * (1 - max_drop_pct / 100)

    ladder = []
    n = base_qty + 1
    while True:
        price = base_amount / n
        if price < floor_price:
            break
        ladder.append({"price": round(price, 2), "qty": 1})
        n += 1
        if n - base_qty > 500:  # 무한루프 방지
            break
    return ladder


def render_crash_buy_section(reference_buy_point_price: float, base_buy_amount: float, key_prefix: str):
    with st.container(border=True):
        st.markdown("#### 🚨 폭락장 대비 추가매수 (안전마진 사다리)")
        st.caption(
            "오늘 매수점가보다 가격이 더 떨어질 때마다 1주씩 더 살 수 있게 되는 정확한 가격을 계산해서, "
            "그 가격마다 1주짜리 LOC 매수 주문을 미리 걸어두는 방식입니다. 정규 매수 주문은 그대로 두고 "
            "이 주문들을 **별도로 추가** 등록하세요."
        )
        max_drop_pct = st.slider(
            "매수점가 대비 최대 커버 하락률 (%)",
            min_value=10, max_value=80,
            value=int(st.session_state.get("crash_max_drop_pct", 50)),
            key=f"crash_max_drop_pct_{key_prefix}",
        )
        st.session_state["crash_max_drop_pct"] = max_drop_pct

        ladder = build_crash_buy_ladder(reference_buy_point_price, base_buy_amount, max_drop_pct)

        if not ladder:
            st.caption("추가매수 사다리를 계산할 수 없습니다 (가격/금액을 확인해주세요).")
        else:
            total_qty = sum(item["qty"] for item in ladder)
            total_amount = sum(item["price"] * item["qty"] for item in ladder)

            c1, c2, c3 = st.columns(3)
            c1.metric("주문 단계 수", f"{len(ladder)} 단계")
            c2.metric("총 추가매수 수량", f"{total_qty:,} 주")
            c3.metric("총 배정 금액", f"${total_amount:,.2f}")

            lines = "  \n".join([f"- LOC ${item['price']:,.2f} × {item['qty']}주" for item in ladder])
            st.markdown(lines)


# =================================================================================
# 3. 사이드바 - 사용자 입력값 (실시간 연동 & 자동저장 버튼)
# =================================================================================
with st.sidebar:
    st.markdown("### 🔥 무한매수법 V4.0")
    st.caption("개인 맞춤형 전용 대시보드")

    if st.button("🔄 파일에서 다시 불러오기", use_container_width=True):
        saved = load_settings()
        for k, v in saved.items():
            st.session_state[k] = v
        st.success("불러왔습니다!")
        st.rerun()

    st.divider()
    st.markdown("#### ⚙️ 오늘의 입력값")

    st.markdown("**1. 종목 & 분할 설정**")
    ticker = st.selectbox("종목 선택", ["TQQQ", "SOXL"], key="ticker")
    split_n = st.selectbox("분할 수 (Split_N)", [20, 40], key="split_n")

    st.markdown("**2. 현재 상태**")
    total_principal = st.number_input("총 투자 원금 ($)", min_value=0.0, step=100.0, key="total_principal")
    current_shares = st.number_input("현재 보유 주식 수 (주)", min_value=0, step=1, key="current_shares")
    avg_price = st.number_input("현재 평단가 ($)", min_value=0.0, step=0.01, format="%.2f", key="avg_price")
    t_value = st.number_input("현재 진행 회차 (T값)", min_value=0.0, step=0.1, format="%.2f", key="t_value")

    # 남은 잔금 = 총 투자원금 - (보유주식수 × 평단가), 자동 계산
    remaining_cash = max(total_principal - (current_shares * avg_price), 0.0)
    st.metric("💰 남은 잔금 (자동계산)", f"${remaining_cash:,.2f}")
    st.caption("= 총 투자원금 − (보유주식수 × 평단가)")

    st.markdown("**3. 시장 데이터**")
    prev_close = st.number_input("전일 종가 ($)", min_value=0.0, step=0.01, format="%.2f", key="prev_close")
    ma5 = st.number_input("최근 5거래일 종가 평균 ($)", min_value=0.0, step=0.01, format="%.2f", key="ma5")

    st.markdown("**4. 현재 모드 단계**")
    mode_stage = st.radio(
        "현재 어떤 단계인가요?",
        ["일반모드 (전반전/후반전 자동판별)", "리버스모드 - 진입 첫날", "리버스모드 - 둘째날 이후"],
    )

    st.divider()
    if st.button("💾 설정 영구 저장", type="primary", use_container_width=True):
        current_data = {
            "ticker": st.session_state.ticker,
            "split_n": st.session_state.split_n,
            "total_principal": st.session_state.total_principal,
            "current_shares": st.session_state.current_shares,
            "avg_price": st.session_state.avg_price,
            "t_value": st.session_state.t_value,
            "prev_close": st.session_state.prev_close,
            "ma5": st.session_state.ma5,
            "crash_max_drop_pct": st.session_state.get("crash_max_drop_pct", 50),
        }
        save_settings(current_data)
        st.success("안전하게 저장되었습니다!")


# =================================================================================
# 4. 공통 계산값
# =================================================================================
half_split = split_n / 2

if mode_stage.startswith("일반모드"):
    if t_value >= split_n - 1:
        stage = "WARN"
    elif t_value < half_split:
        stage = "A"
    else:
        stage = "B"
elif mode_stage == "리버스모드 - 진입 첫날":
    stage = "C"
else:
    stage = "D"

star_pct = get_star_percent(ticker, split_n, t_value)
target_pct = get_target_profit_percent(ticker)

star_price_normal = avg_price * (1 + star_pct)
star_price_reverse = ma5
buy_point_price_normal = calc_buy_point_price(star_price_normal)
buy_point_price_reverse = calc_buy_point_price(star_price_reverse)

daily_buy_amount_normal = calc_daily_buy_amount_normal(remaining_cash, split_n, t_value)
daily_buy_amount_reverse = calc_daily_buy_amount_reverse(remaining_cash)

target_sell_price = avg_price * (1 + target_pct)
reverse_exit_price = avg_price * (1 - target_pct)


# =================================================================================
# 5. 헤더 & 진행 상황 요약 카드 (FIRE GATE 스타일)
# =================================================================================
st.title(f"🔥 {ticker} 무한매수법 V4.0")

with st.container(border=True):
    st.markdown("##### 진행 상황")
    progress_ratio = min(t_value / split_n, 1.0) if split_n > 0 else 0.0
    st.progress(progress_ratio, text=f"{progress_ratio*100:.1f}%")

    invested_amount = current_shares * avg_price
    display_daily_amount = daily_buy_amount_normal if stage in ("A", "B") else daily_buy_amount_reverse

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("총 시드", f"${total_principal:,.0f}")
    c2.metric("사용한 시드", f"${invested_amount:,.0f}")
    c3.metric("1회 매수금", f"${display_daily_amount:,.2f}")
    c4.metric("평단가", f"${avg_price:,.2f}")
    c5.metric("보유 수량", f"{current_shares:,} 주")

    badge_col1, badge_col2, badge_col3 = st.columns([1, 1, 3])
    with badge_col1:
        st.markdown(f"<span class='badge-orange'>T값 {t_value:g}</span>", unsafe_allow_html=True)
    with badge_col2:
        star_display = f"{star_pct*100:.2f}%" if stage in ("A", "B") else "—"
        st.markdown(f"<span class='badge-purple'>Star값 {star_display}</span>", unsafe_allow_html=True)


tab1, tab2 = st.tabs(["🧮 오늘 주문 계산기", "✅ 체결 결과 입력 & T값 업데이트"])


# ---------------------------------------------------------------------------------
# TAB 1. 오늘 주문 계산기
# ---------------------------------------------------------------------------------
with tab1:
    if stage == "WARN":
        st.warning(
            f"⚠️ 현재 T값({t_value:g})이 리버스모드 진입 기준(Split_N - 1 = {split_n-1:g}) 이상입니다.\n\n"
            "사이드바에서 '리버스모드 - 진입 첫날'을 선택해주세요."
        )

    elif stage in ("A", "B"):
        stage_name = "A. 일반모드 - 전반전" if stage == "A" else "B. 일반모드 - 후반전"
        st.subheader(f"현재 단계: {stage_name}")

        st.markdown("### 🔴 매도 주문")
        col1, col2 = st.columns(2)
        quarter_sell_qty = math.floor(current_shares / 4)
        with col1:
            with st.container(border=True):
                st.markdown("**① 1/4 수량 · 별지점 LOC 매도**")
                st.metric("매도 단가 (별지점가)", f"${star_price_normal:,.2f}")
                st.metric("매도 수량", f"{quarter_sell_qty:,} 주")

        remain_sell_qty = current_shares - quarter_sell_qty
        with col2:
            with st.container(border=True):
                st.markdown(f"**② 나머지 3/4 수량 · 지정가(+{target_pct*100:.0f}%) 매도**")
                st.metric("매도 단가 (목표가)", f"${target_sell_price:,.2f}")
                st.metric("매도 수량", f"{remain_sell_qty:,} 주")

        st.markdown("### 🔵 매수 주문")

        if stage == "A":
            half_amount = daily_buy_amount_normal / 2
            buy_qty_at_buy_point = math.floor(half_amount / buy_point_price_normal) if buy_point_price_normal > 0 else 0
            buy_qty_at_avg = math.floor(half_amount / avg_price) if avg_price > 0 else 0

            colA, colB = st.columns(2)
            with colA:
                with st.container(border=True):
                    st.markdown("**① 절반 금액 · 매수점가 LOC 매수**")
                    st.metric("매수 단가 (매수점가)", f"${buy_point_price_normal:,.2f}")
                    st.metric("매수 수량", f"{buy_qty_at_buy_point:,} 주")
                    st.caption(f"배정 금액: ${half_amount:,.2f}")
            with colB:
                with st.container(border=True):
                    st.markdown("**② 절반 금액 · 평단가 LOC 매수**")
                    st.metric("매수 단가 (평단가)", f"${avg_price:,.2f}")
                    st.metric("매수 수량", f"{buy_qty_at_avg:,} 주")
                    st.caption(f"배정 금액: ${half_amount:,.2f}")
        else:
            buy_qty_full = math.floor(daily_buy_amount_normal / buy_point_price_normal) if buy_point_price_normal > 0 else 0
            with st.container(border=True):
                st.markdown("**1회 매수금 전액 · 매수점가 LOC 매수**")
                colX, colY = st.columns(2)
                with colX:
                    st.metric("매수 단가 (매수점가)", f"${buy_point_price_normal:,.2f}")
                with colY:
                    st.metric("매수 수량", f"{buy_qty_full:,} 주")
                st.caption(f"배정 금액: ${daily_buy_amount_normal:,.2f}")

        st.markdown("###")
        render_crash_buy_section(buy_point_price_normal, daily_buy_amount_normal, key_prefix="normal")

        with st.expander("📎 계산 상세 (별%, 1회 매수금 등)"):
            st.write(f"- 별% (Star %) = **{star_pct*100:.3f}%**")
            st.write(f"- 별지점 가격 = 평단가 × (1 + 별%) = **${star_price_normal:,.2f}**")
            st.write(f"- 매수점 가격 = 별지점 가격 - 0.01 = **${buy_point_price_normal:,.2f}**")
            st.write(f"- 1회 매수금 = 남은 잔금 ÷ (분할수 - T) = ${remaining_cash:,.2f} ÷ ({split_n} - {t_value:g}) = **${daily_buy_amount_normal:,.2f}**")

    elif stage == "C":
        st.subheader("C. 리버스(소진)모드 진입 첫날")
        st.info("이 단계에서는 매수 없이, 정해진 수량을 종가(MOC)로 무조건 매도합니다.")

        moc_sell_qty = math.floor(current_shares / half_split) if half_split > 0 else 0
        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True):
                st.markdown("**🔴 매도 (MOC, 종가매도)**")
                st.metric("매도 방식", "MOC (동시호가 종가매도)")
                st.metric("매도 수량", f"{moc_sell_qty:,} 주")
                st.caption(f"= 보유수량 {current_shares:,}주 ÷ (분할수/2 = {half_split:g}) 내림")
        with col2:
            with st.container(border=True):
                st.markdown("**🔵 매수**")
                st.write("없음 (진입 첫날은 매수하지 않음)")

    else:  # stage == "D"
        st.subheader("D. 리버스(소진)모드 - 둘째날 이후")

        if prev_close > reverse_exit_price:
            st.success(
                f"✅ 전일 종가(${prev_close:,.2f})가 리버스모드 종료 기준가(평단 대비 -{target_pct*100:.0f}% = "
                f"${reverse_exit_price:,.2f})보다 높습니다.\n\n"
                "**→ 리버스모드를 종료하고 일반모드로 즉시 복귀하세요.**"
            )
        else:
            st.warning(
                f"전일 종가(${prev_close:,.2f})가 종료 기준가(${reverse_exit_price:,.2f}) 이하이므로 리버스모드를 계속 유지합니다."
            )

            st.markdown("### 🔴 매도 주문 (LOC)")
            reverse_sell_qty = math.floor(current_shares / half_split) if half_split > 0 else 0
            with st.container(border=True):
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("매도 단가 (별지점가=5일선)", f"${star_price_reverse:,.2f} 이상")
                with col2:
                    st.metric("매도 수량", f"{reverse_sell_qty:,} 주")
                st.caption(f"= 전일 보유수량 {current_shares:,}주 ÷ (분할수/2 = {half_split:g}) 내림, 별지점가 이상에서 LOC 매도")

            st.markdown("### 🔵 매수 주문 (쿼터매수)")
            reverse_buy_qty = math.floor(daily_buy_amount_reverse / buy_point_price_reverse) if buy_point_price_reverse > 0 else 0

            if reverse_buy_qty < 1:
                st.error("❌ 쿼터매수 금액으로 1주도 매수할 수 없습니다. 매수 대신 MOC 매도(C 규칙)를 시행하세요.")
                fallback_moc_qty = math.floor(current_shares / half_split) if half_split > 0 else 0
                st.metric("MOC 매도 수량 (대체 실행)", f"{fallback_moc_qty:,} 주")
            else:
                with st.container(border=True):
                    col3, col4 = st.columns(2)
                    with col3:
                        st.metric("매수 단가 (매수점가, 별지점가 아래)", f"${buy_point_price_reverse:,.2f}")
                    with col4:
                        st.metric("매수 수량", f"{reverse_buy_qty:,} 주")
                    st.caption(f"배정 금액(잔금÷4): ${daily_buy_amount_reverse:,.2f}")

                st.markdown("###")
                render_crash_buy_section(buy_point_price_reverse, daily_buy_amount_reverse, key_prefix="reverse")

        with st.expander("📎 계산 상세"):
            st.write(f"- 리버스모드 종료 기준가 = 평단가 × (1 - {target_pct*100:.0f}%) = **${reverse_exit_price:,.2f}**")
            st.write(f"- 별지점 가격(리버스모드) = 최근 5거래일 종가 평균 = **${star_price_reverse:,.2f}**")
            st.write(f"- 매수점 가격 = 별지점 가격 - 0.01 = **${buy_point_price_reverse:,.2f}**")
            st.write(f"- 1회 매수금(쿼터매수) = 남은 잔금 ÷ 4 = **${daily_buy_amount_reverse:,.2f}**")


# ---------------------------------------------------------------------------------
# TAB 2. 체결 결과 입력 & T값 업데이트
# ---------------------------------------------------------------------------------
with tab2:
    st.subheader("장 마감 후 체결 결과를 입력하면 내일의 T값을 계산합니다")
    st.caption("아래에서 오늘 실제로 어떤 주문이 체결되었는지 시나리오를 선택하세요.")

    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            filled_buy_qty = st.number_input("체결된 매수 수량 (주)", min_value=0, value=0, step=1)
        with col2:
            filled_sell_qty = st.number_input("체결된 매도 수량 (주)", min_value=0, value=0, step=1)

        update_mode = st.radio("업데이트 대상 모드", ["일반모드", "리버스모드"], horizontal=True)

        new_t = t_value
        explanation = ""

        if update_mode == "일반모드":
            scenario = st.radio(
                "오늘 발생한 체결 시나리오를 선택하세요",
                [
                    "1회 매수금 전액 매수 체결 (T + 1)",
                    "1회 매수금 절반만 매수 체결 (전반전, T + 0.5)",
                    "쿼터매도(1/4 수량 매도)만 발생 (T × 0.75)",
                    "지정가 매도 체결 후 LOC 매수까지 절반 체결 (T × 0.25 + 0.5)",
                    "지정가 매도 체결 후 LOC 매수까지 전액 체결 (T × 0.25 + 1)",
                    "변화 없음 (미체결)",
                ],
            )
            if scenario.startswith("1회 매수금 전액"):
                new_t, explanation = t_value + 1, "T + 1"
            elif scenario.startswith("1회 매수금 절반"):
                new_t, explanation = t_value + 0.5, "T + 0.5"
            elif scenario.startswith("쿼터매도"):
                new_t, explanation = t_value * 0.75, "T × 0.75"
            elif scenario.startswith("지정가 매도 체결 후 LOC 매수까지 절반"):
                new_t, explanation = t_value * 0.25 + 0.5, "T × 0.25 + 0.5"
            elif scenario.startswith("지정가 매도 체결 후 LOC 매수까지 전액"):
                new_t, explanation = t_value * 0.25 + 1, "T × 0.25 + 1"
            else:
                new_t, explanation = t_value, "변화 없음"
        else:
            scenario = st.radio(
                "오늘 발생한 체결 시나리오를 선택하세요",
                ["매도 체결 발생", "매수(쿼터매수) 체결 발생", "변화 없음 (미체결)"],
            )
            sell_factor = 0.9 if split_n == 20 else 0.95
            if scenario == "매도 체결 발생":
                new_t, explanation = t_value * sell_factor, f"T × {sell_factor} ({split_n}분할)"
            elif scenario == "매수(쿼터매수) 체결 발생":
                new_t = t_value + (split_n - t_value) * 0.25
                explanation = f"T + ({split_n} - T) × 0.25 ({split_n}분할)"
            else:
                new_t, explanation = t_value, "변화 없음"

    st.markdown("### 📌 계산 결과")
    with st.container(border=True):
        colr1, colr2, colr3 = st.columns(3)
        with colr1:
            st.metric("기존 T값", f"{t_value:.3f}")
        with colr2:
            st.metric("👉 내일의 새로운 T값", f"{new_t:.3f}")
        with colr3:
            st.metric("적용 오차 공식", explanation)

    st.caption(
        "💡 내일 장 시작 전, 사이드바에서 T값을 이 새로운 값으로 변경하고 "
        "'💾 설정 영구 저장' 버튼을 눌러두시면 안전하게 유지됩니다."
    )


# =================================================================================
# 6. 하단 요약 정보
# =================================================================================
st.divider()
st.caption(
    f"현재 설정: {ticker} · {split_n}분할 · T={t_value:g} · 총원금 ${total_principal:,.0f} · "
    f"잔금(자동계산) ${remaining_cash:,.0f} · 보유 {current_shares:,}주 · 평단 ${avg_price:,.2f}"
)
