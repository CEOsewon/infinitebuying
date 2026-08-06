"""
=====================================================================================
무한매수법 V4.0 - 레버리지 ETF(TQQQ / SOXL) 퀀트 매매 대시보드
=====================================================================================
- 계정별 로그인 & 설정 자동 저장 (users_db.json)
- 남은 잔금 자동 계산 (총원금 - 보유주식수×평단가)
- 폭락장 대비 추가매수(안전마진) 주문 계산
- '오늘 주문 계산기' / '체결 결과 입력 & T값 업데이트' 탭 구성

⚠️ 주의
1) 이 앱은 특정 개인 전략(무한매수법 V4.0)을 코드로 구현한 계산 도구이며, 투자 조언이 아닙니다.
2) 로그인 기능은 로컬 JSON 파일(users_db.json)에 아이디/비밀번호(해시)를 저장하는 간단한 방식입니다.
   본인 혼자 또는 소수 인원이 개인용으로 쓰는 용도로는 충분하지만, 다수의 일반 사용자에게
   서비스하려면 별도의 정식 인증 시스템(예: Firebase Auth, Supabase Auth 등)과 DB 사용을 권장합니다.
   또한 Streamlit Community Cloud 등 일부 무료 호스팅은 앱 재배포/재시작 시 로컬 파일이
   초기화될 수 있으니, 장기 보관이 중요하다면 외부 DB 연동을 고려하세요.
=====================================================================================
"""

import math
import json
import hashlib
from pathlib import Path

import streamlit as st

# -------------------------------------------------------------------------------
# 0. 기본 페이지 설정 & 커스텀 스타일
# -------------------------------------------------------------------------------
st.set_page_config(page_title="무한매수법 V4.0 대시보드", layout="wide", page_icon="🔥")

# fire-gate 류의 개인 재무/파이어 계산기 앱들이 흔히 쓰는 스타일(부드러운 배경 + 화이트 카드 +
# 큼직한 숫자 강조 + 포인트 컬러)을 참고해 깔끔한 카드형 UI로 구성했습니다.
CUSTOM_CSS = """
<style>
    .stApp { background-color: #F6F7FB; }
    section[data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #EEF0F4; }

    h1, h2, h3 { color: #14161A; font-weight: 800; }
    p, span, label { color: #4B4F58; }

    /* 카드형 컨테이너 (st.container(border=True)) 스타일 */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF;
        border-radius: 18px !important;
        border: 1px solid #EEF0F4 !important;
        box-shadow: 0 2px 10px rgba(20, 22, 26, 0.04);
        padding: 6px 4px;
    }

    /* 큰 숫자 강조되는 Metric */
    div[data-testid="stMetric"] {
        background-color: #FAFAFC;
        border-radius: 12px;
        padding: 10px 14px;
    }
    [data-testid="stMetricValue"] { font-size: 1.65rem; font-weight: 800; color: #14161A; }
    [data-testid="stMetricLabel"] { font-size: 0.82rem; color: #8A8F9A; font-weight: 600; }

    /* 탭 */
    .stTabs [data-baseweb="tab"] { font-weight: 700; font-size: 1rem; }
    .stTabs [aria-selected="true"] { color: #FF5A36 !important; }
    .stTabs [data-baseweb="tab-highlight"] { background-color: #FF5A36 !important; }

    /* 기본(primary) 버튼 - 포인트 컬러(FIRE 느낌의 오렌지/레드) */
    button[kind="primary"] {
        background-color: #FF5A36 !important;
        border: none !important;
    }
    button[kind="primary"]:hover { background-color: #E64A28 !important; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# =================================================================================
# 1. 계정별 저장 (간단한 로컬 JSON 기반 로그인 & 설정 저장소)
# =================================================================================
DB_PATH = Path(__file__).parent / "users_db.json"

DEFAULT_SETTINGS = {
    "ticker": "TQQQ",
    "split_n": 20,
    "total_principal": 10000.0,
    "current_shares": 0,
    "avg_price": 0.0,
    "t_value": 0.0,
    "prev_close": 0.0,
    "ma5": 0.0,
    "crash_drop_pct": 5,
}


def load_db() -> dict:
    if DB_PATH.exists():
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_db(db: dict) -> None:
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def hash_password(pw: str) -> str:
    # 간단한 솔트를 붙인 SHA-256 해시. (프로덕션 수준의 보안은 아닙니다 - 위 주의사항 참고)
    salt = "infinite-buying-v4-salt"
    return hashlib.sha256((salt + pw).encode("utf-8")).hexdigest()


def login_and_signup_screen():
    """로그인 전 화면: 로그인 / 회원가입 탭"""
    st.title("🔥 무한매수법 V4.0 대시보드")
    st.caption("계정별로 종목/분할수/투자원금 등 설정이 저장됩니다. 먼저 로그인해주세요.")

    tab_login, tab_signup = st.tabs(["🔐 로그인", "📝 회원가입"])
    db = load_db()

    with tab_login:
        with st.container(border=True):
            uid = st.text_input("아이디", key="login_id")
            pw = st.text_input("비밀번호", type="password", key="login_pw")
            if st.button("로그인", type="primary", use_container_width=True):
                if uid in db and db[uid]["password_hash"] == hash_password(pw):
                    st.session_state.user = uid
                    st.session_state.settings_loaded = False
                    st.rerun()
                else:
                    st.error("아이디 또는 비밀번호가 올바르지 않습니다.")

    with tab_signup:
        with st.container(border=True):
            new_uid = st.text_input("새 아이디", key="signup_id")
            new_pw = st.text_input("새 비밀번호", type="password", key="signup_pw")
            if st.button("회원가입", use_container_width=True):
                if not new_uid or not new_pw:
                    st.error("아이디와 비밀번호를 모두 입력해주세요.")
                elif new_uid in db:
                    st.error("이미 존재하는 아이디입니다.")
                else:
                    db[new_uid] = {
                        "password_hash": hash_password(new_pw),
                        "settings": DEFAULT_SETTINGS.copy(),
                    }
                    save_db(db)
                    st.success("가입이 완료되었습니다! '로그인' 탭에서 로그인해주세요.")


# --- 로그인 여부 확인 ---
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    login_and_signup_screen()
    st.stop()

CURRENT_USER = st.session_state.user
db = load_db()
saved_settings = db.get(CURRENT_USER, {}).get("settings", DEFAULT_SETTINGS.copy())

# 로그인 직후 1회에 한해, 저장된 설정값을 위젯 session_state 기본값으로 주입
if not st.session_state.get("settings_loaded", False):
    for k, v in saved_settings.items():
        st.session_state[k] = v
    st.session_state.settings_loaded = True


# =================================================================================
# 2. 핵심 계산 함수들
# =================================================================================

def get_star_percent(ticker: str, split_n: int, t: float) -> float:
    """별지점(Star Point) % 계산 - 종목/분할수 별 공식이 다름"""
    if ticker == "TQQQ":
        pct = (15 - 1.5 * t) / 100 if split_n == 20 else (15 - 0.75 * t) / 100
    else:  # SOXL
        pct = (20 - 2 * t) / 100 if split_n == 20 else (20 - t) / 100
    return pct


def get_target_profit_percent(ticker: str) -> float:
    """지정가 매도(잔여 3/4) 및 리버스모드 종료 기준에 쓰이는 목표수익률"""
    return 0.15 if ticker == "TQQQ" else 0.20


def calc_buy_point_price(star_price: float) -> float:
    return star_price - 0.01


def calc_daily_buy_amount_normal(remaining_cash: float, split_n: int, t: float) -> float:
    denom = split_n - t
    return remaining_cash / denom if denom > 0 else 0.0


def calc_daily_buy_amount_reverse(remaining_cash: float) -> float:
    return remaining_cash / 4


def render_crash_buy_section(reference_buy_point_price: float, base_buy_amount: float):
    """
    폭락장 대비 추가매수(안전마진) 섹션
    - 평소 매수점가보다 사용자가 지정한 % 만큼 더 낮은 가격에, '1회 매수금'에 가까운 금액을
      통째로 LOC 매수 주문으로 걸어두어, 장중 급락 시에만 체결되도록 하는 예비 주문입니다.
    - 정규 매수 주문과는 별도로 추가 등록하는 주문입니다 (정규 주문을 대체하지 않음).
    """
    with st.container(border=True):
        st.markdown("#### 🚨 폭락장 대비 추가매수 (안전마진)")
        st.caption(
            "평소 매수점가보다 훨씬 낮은 가격에 1회 매수금과 비슷한 금액을 미리 걸어두는 예비 주문입니다. "
            "정규 매수 주문은 그대로 유지하고, 이 주문을 **별도로 추가** 등록하세요."
        )
        crash_pct = st.slider(
            "매수점가 대비 추가 하락 트리거 (%)",
            min_value=1, max_value=30,
            value=int(st.session_state.get("crash_drop_pct", 5)),
            key="crash_drop_pct",
        )
        crash_price = reference_buy_point_price * (1 - crash_pct / 100)
        crash_qty = math.floor(base_buy_amount / crash_price) if crash_price > 0 else 0

        c1, c2 = st.columns(2)
        with c1:
            st.metric("추가매수 단가 (LOC)", f"${crash_price:,.2f}")
        with c2:
            st.metric("추가매수 수량", f"{crash_qty:,} 주")
        st.caption(f"배정 금액 ≈ 1회 매수금 전액(${base_buy_amount:,.2f}) 기준")


# =================================================================================
# 3. 사이드바 - 사용자 입력값 (계정별 저장/불러오기 포함)
# =================================================================================
with st.sidebar:
    st.markdown(f"#### 👤 {CURRENT_USER} 님")
    colL, colR = st.columns(2)
    with colL:
        if st.button("🔄 불러오기", use_container_width=True):
            for k, v in saved_settings.items():
                st.session_state[k] = v
            st.rerun()
    with colR:
        if st.button("🚪 로그아웃", use_container_width=True):
            st.session_state.user = None
            st.session_state.settings_loaded = False
            st.rerun()

    st.divider()
    st.header("⚙️ 오늘의 입력값")

    st.subheader("1. 종목 & 분할 설정")
    ticker = st.selectbox("종목 선택", ["TQQQ", "SOXL"], key="ticker")
    split_n = st.selectbox("분할 수 (Split_N)", [20, 40], key="split_n")

    st.subheader("2. 현재 상태")
    total_principal = st.number_input("총 투자 원금 ($)", min_value=0.0, step=100.0, key="total_principal")
    current_shares = st.number_input("현재 보유 주식 수 (주)", min_value=0, step=1, key="current_shares")
    avg_price = st.number_input("현재 평단가 ($)", min_value=0.0, step=0.01, format="%.2f", key="avg_price")
    t_value = st.number_input("현재 진행 회차 (T값)", min_value=0.0, step=0.1, format="%.2f", key="t_value")

    # --- 요청사항: 남은 잔금은 이제 입력이 아니라 자동 계산 ---
    # 남은 잔금 = 총 투자원금 - (보유주식수 × 평단가)
    # (평단가 × 보유주식수 = 지금까지 실제로 투입되어 주식으로 물려있는 금액이라는 전제)
    remaining_cash = max(total_principal - (current_shares * avg_price), 0.0)
    st.metric("💰 현재 남은 잔금 (자동계산)", f"${remaining_cash:,.2f}")
    st.caption("= 총 투자원금 − (보유주식수 × 평단가)")

    st.subheader("3. 시장 데이터")
    prev_close = st.number_input("전일 종가 ($)", min_value=0.0, step=0.01, format="%.2f", key="prev_close")
    ma5 = st.number_input("최근 5거래일 종가 평균 ($)", min_value=0.0, step=0.01, format="%.2f", key="ma5")

    st.subheader("4. 현재 모드 단계")
    mode_stage = st.radio(
        "현재 어떤 단계인가요?",
        ["일반모드 (전반전/후반전 자동판별)", "리버스모드 - 진입 첫날", "리버스모드 - 둘째날 이후"],
    )

    st.divider()
    if st.button("💾 현재 설정 저장", type="primary", use_container_width=True):
        db2 = load_db()
        db2.setdefault(CURRENT_USER, {"password_hash": db.get(CURRENT_USER, {}).get("password_hash"), "settings": {}})
        db2[CURRENT_USER]["settings"] = {
            "ticker": ticker, "split_n": split_n, "total_principal": total_principal,
            "current_shares": current_shares, "avg_price": avg_price, "t_value": t_value,
            "prev_close": prev_close, "ma5": ma5,
            "crash_drop_pct": st.session_state.get("crash_drop_pct", 5),
        }
        save_db(db2)
        st.success("저장되었습니다!")

st.sidebar.info(f"분할수 절반 지점(Split_N/2) = **{split_n/2:g}**  ·  리버스 진입 기준(Split_N-1) = **{split_n-1:g}**")


# =================================================================================
# 4. 공통 계산값 미리 산출
# =================================================================================
star_pct = get_star_percent(ticker, split_n, t_value)
target_pct = get_target_profit_percent(ticker)

star_price_normal = avg_price * (1 + star_pct)      # 일반모드 별지점 가격
star_price_reverse = ma5                             # 리버스모드 별지점 가격 = 5일 평균종가
buy_point_price_normal = calc_buy_point_price(star_price_normal)
buy_point_price_reverse = calc_buy_point_price(star_price_reverse)

daily_buy_amount_normal = calc_daily_buy_amount_normal(remaining_cash, split_n, t_value)
daily_buy_amount_reverse = calc_daily_buy_amount_reverse(remaining_cash)

target_sell_price = avg_price * (1 + target_pct)
reverse_exit_price = avg_price * (1 - target_pct)


# =================================================================================
# 5. 탭 구성
# =================================================================================
title_col, badge_col = st.columns([5, 1])
with title_col:
    st.title("🔥 무한매수법 V4.0 대시보드")
with badge_col:
    st.markdown(f"<div style='text-align:right; padding-top:20px;'>👤 {CURRENT_USER}</div>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["🧮 오늘 주문 계산기", "✅ 체결 결과 입력 & T값 업데이트"])


# ---------------------------------------------------------------------------------
# TAB 1. 오늘 주문 계산기
# ---------------------------------------------------------------------------------
with tab1:
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
        # --- 요청사항: 폭락장 대비 추가매수 섹션 ---
        render_crash_buy_section(buy_point_price_normal, daily_buy_amount_normal)

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
                render_crash_buy_section(buy_point_price_reverse, daily_buy_amount_reverse)

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
            st.metric("적용 공식", explanation)

    st.caption(
        "💡 내일 장 시작 전, 사이드바의 '현재 진행 회차 (T값)'과 '보유 주식 수 / 평단가'를 갱신한 뒤 "
        "'💾 현재 설정 저장'을 눌러두면 다음 로그인 때도 이어서 사용할 수 있습니다."
    )

    with st.expander("📎 참고: 오늘 입력한 체결 수량"):
        st.write(f"- 체결된 매수 수량: {filled_buy_qty:,} 주")
        st.write(f"- 체결된 매도 수량: {filled_sell_qty:,} 주")


# =================================================================================
# 6. 하단 요약 정보
# =================================================================================
st.divider()
st.caption(
    f"현재 설정: {ticker} · {split_n}분할 · T={t_value:g} · 총원금 ${total_principal:,.0f} · "
    f"잔금(자동계산) ${remaining_cash:,.0f} · 보유 {current_shares:,}주 · 평단 ${avg_price:,.2f}"
)
