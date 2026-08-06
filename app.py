"""
=====================================================================================
무한매수법 V4.0 - 레버리지 ETF(TQQQ / SOXL) 퀀트 매매 대시보드
=====================================================================================
- Google / Naver 소셜 로그인 전용 (자체 회원가입 없음)
- 계정별 설정 자동 저장 (user_settings.json, 원자적 저장 + 백업 + 선택적 암호화)
- 남은 잔금 자동 계산
- 폭락장 대비 추가매수 "사다리" 주문 계산 (최대 하락률까지 1주 단위로 커버)

⚠️ 실행 전 준비사항
1) 이 앱을 실행하려면 프로젝트 폴더에 `.streamlit/secrets.toml` 파일이 필요합니다.
   아래 [로그인 설정] 섹션의 주석을 참고해서 채워주세요. (구글/네이버 개발자 콘솔에서 발급)
2) 필요한 패키지: pip install streamlit requests cryptography
   (Google 로그인은 Streamlit 1.42+ 의 내장 인증 기능(st.login)을 사용하며, Authlib이 함께 설치됩니다)
3) 이 앱은 특정 개인 전략(무한매수법 V4.0)을 코드로 구현한 계산 도구이며, 투자 조언이 아닙니다.
=====================================================================================
"""

import math
import os
import json
import threading
import secrets as pysecrets
from pathlib import Path
from urllib.parse import urlencode

import requests
import streamlit as st

try:
    from cryptography.fernet import Fernet
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False


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
# 1. 계정별 설정 저장소 (JSON, 원자적 저장 + 자동 백업 + 선택적 암호화)
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


def _get_fernet():
    """
    st.secrets 에 data_encryption_key가 설정돼 있으면 저장 파일을 암호화합니다.
    (선택사항 - 없으면 평문 JSON으로 저장되며, 파일시스템 접근 권한으로만 보호됩니다)
    """
    if not _CRYPTO_AVAILABLE:
        return None
    try:
        key = st.secrets.get("data_encryption_key", None)
    except Exception:
        key = None
    if not key:
        return None
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        return None


def load_all_settings() -> dict:
    if not DATA_PATH.exists():
        return {}
    try:
        raw = DATA_PATH.read_bytes()
        fernet = _get_fernet()
        if fernet:
            raw = fernet.decrypt(raw)
        return json.loads(raw.decode("utf-8"))
    except Exception:
        # 파일이 손상되었거나 키가 맞지 않는 경우 - 서비스가 죽지 않도록 빈 값으로 안전하게 폴백
        return {}


def save_all_settings(data: dict) -> None:
    """
    원자적 저장: 임시파일에 먼저 쓰고 os.replace로 교체 -> 저장 도중 프로세스가 죽어도
    기존 파일이 손상되지 않습니다. 교체 직전에는 기존 파일을 .bak으로 백업합니다.
    """
    payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    fernet = _get_fernet()
    if fernet:
        payload = fernet.encrypt(payload)

    with _FILE_LOCK:
        tmp_path = DATA_PATH.with_suffix(".tmp")
        bak_path = DATA_PATH.with_suffix(".bak")
        try:
            if DATA_PATH.exists():
                bak_path.write_bytes(DATA_PATH.read_bytes())
        except Exception:
            pass
        tmp_path.write_bytes(payload)
        os.replace(tmp_path, DATA_PATH)


def save_user_settings(user_key: str, settings: dict) -> None:
    all_data = load_all_settings()
    all_data[user_key] = settings
    save_all_settings(all_data)


def delete_user_settings(user_key: str) -> None:
    all_data = load_all_settings()
    if user_key in all_data:
        del all_data[user_key]
        save_all_settings(all_data)


# =================================================================================
# 2. 로그인 (Google: Streamlit 내장 OIDC / Naver: 수동 OAuth2 인가코드 흐름)
# =================================================================================
NAVER_AUTH_URL = "https://nid.naver.com/oauth2.0/authorize"
NAVER_TOKEN_URL = "https://nid.naver.com/oauth2.0/token"
NAVER_PROFILE_URL = "https://openapi.naver.com/v1/nid/me"


def _secrets_section(name: str) -> dict:
    try:
        return dict(st.secrets.get(name, {}))
    except Exception:
        return {}


def google_configured() -> bool:
    auth = _secrets_section("auth")
    return bool(auth) and ("google" in st.secrets.get("auth", {}) or "client_id" in auth)


def naver_configured() -> bool:
    naver = _secrets_section("naver")
    return all(k in naver for k in ("client_id", "client_secret", "redirect_uri"))


def try_restore_google_session():
    """Streamlit 내장 st.user (구글 OIDC 로그인 결과)를 세션에 반영"""
    if st.session_state.get("auth_user") is not None:
        return
    try:
        if getattr(st.user, "is_logged_in", False):
            st.session_state.auth_user = {
                "provider": "google",
                "key": f"google:{st.user.email}",
                "name": getattr(st.user, "name", None) or st.user.email,
                "email": getattr(st.user, "email", None),
            }
    except Exception:
        pass


def handle_naver_callback():
    """네이버 로그인 콜백(인가코드) 처리 - 쿼리 파라미터에 code가 있으면 토큰/프로필 교환"""
    if st.session_state.get("auth_user") is not None:
        return
    qp = dict(st.query_params)
    code = qp.get("code")
    state = qp.get("state")
    expected_state = st.session_state.get("naver_oauth_state")
    if not code or not state or not expected_state or state != expected_state:
        return

    naver = _secrets_section("naver")
    try:
        token_resp = requests.get(
            NAVER_TOKEN_URL,
            params={
                "grant_type": "authorization_code",
                "client_id": naver["client_id"],
                "client_secret": naver["client_secret"],
                "redirect_uri": naver["redirect_uri"],
                "code": code,
                "state": state,
            },
            timeout=10,
        )
        token_resp.raise_for_status()
        access_token = token_resp.json().get("access_token")

        profile_resp = requests.get(
            NAVER_PROFILE_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        profile_resp.raise_for_status()
        profile = profile_resp.json().get("response", {})

        st.session_state.auth_user = {
            "provider": "naver",
            "key": f"naver:{profile.get('id')}",
            "name": profile.get("nickname") or profile.get("name") or "네이버 사용자",
            "email": profile.get("email"),
        }
        st.session_state.naver_oauth_state = None
        st.query_params.clear()
        st.rerun()
    except Exception:
        # 실패해도 민감정보(토큰 등)를 화면에 노출하지 않고 조용히 로그인 실패 처리
        st.session_state.auth_user = None
        st.query_params.clear()
        st.error("네이버 로그인 처리 중 문제가 발생했습니다. 다시 시도해주세요.")


def login_screen():
    st.title("🔥 무한매수법 V4.0 대시보드")
    st.caption("Google 또는 Naver 계정으로 로그인하면 설정이 자동으로 저장/불러오기 됩니다.")

    with st.container(border=True):
        st.markdown("### 로그인")

        if google_configured():
            if st.button("🟦 Google로 로그인", use_container_width=True):
                st.login("google")
        else:
            st.caption("⚠️ Google 로그인이 아직 설정되지 않았습니다 (secrets.toml [auth.google] 필요)")

        st.markdown("")

        if naver_configured():
            naver = _secrets_section("naver")
            if st.button("🟩 Naver로 로그인", use_container_width=True):
                state = pysecrets.token_urlsafe(16)
                st.session_state.naver_oauth_state = state
                url = f"{NAVER_AUTH_URL}?{urlencode({'response_type': 'code', 'client_id': naver['client_id'], 'redirect_uri': naver['redirect_uri'], 'state': state})}"
                st.link_button("네이버 로그인 계속하기 →", url, use_container_width=True)
        else:
            st.caption("⚠️ Naver 로그인이 아직 설정되지 않았습니다 (secrets.toml [naver] 필요)")

        if not google_configured() and not naver_configured():
            st.info(
                "로그인 제공자가 설정되지 않았습니다. 프로젝트 폴더에 `.streamlit/secrets.toml`을 만들고 "
                "코드 상단 주석의 안내에 따라 Google/Naver 앱 정보를 입력해주세요."
            )


# --- 세션 초기화 ---
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None

try_restore_google_session()
handle_naver_callback()

if st.session_state.auth_user is None:
    login_screen()
    st.stop()

CURRENT_USER = st.session_state.auth_user
USER_KEY = CURRENT_USER["key"]

all_settings = load_all_settings()
saved_settings = all_settings.get(USER_KEY, DEFAULT_SETTINGS.copy())

if not st.session_state.get("settings_loaded_for", None) == USER_KEY:
    for k, v in saved_settings.items():
        st.session_state[k] = v
    st.session_state.settings_loaded_for = USER_KEY


# =================================================================================
# 3. 핵심 계산 함수들
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
    폭락장 대비 추가매수 "사다리" 계산 (Fire Gate 방식과 동일한 로직)
    - 기준가(base_price)에서 1회 매수금(base_amount)으로 살 수 있는 수량 = base_qty (내림)
    - price(n) = base_amount / n  →  n주를 살 수 있게 되는 정확한 가격
    - n = base_qty+1, base_qty+2, ... 로 늘려가며, 가격이 base_price 대비 max_drop_pct%
      하락하는 지점까지 1주 단위로 LOC 매수 주문을 나열
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
        if n - base_qty > 500:  # 무한루프 방지 안전장치
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
# 4. 사이드바 - 사용자 입력값 (계정별 저장 포함)
# =================================================================================
with st.sidebar:
    st.markdown("### 🔥 무한매수법 V4.0")
    st.caption(f"👤 {CURRENT_USER['name']} ({CURRENT_USER['provider']})")

    colL, colR = st.columns(2)
    with colL:
        if st.button("🔄 불러오기", use_container_width=True):
            for k, v in saved_settings.items():
                st.session_state[k] = v
            st.rerun()
    with colR:
        if st.button("🚪 로그아웃", use_container_width=True):
            if CURRENT_USER["provider"] == "google":
                try:
                    st.logout()
                except Exception:
                    pass
            st.session_state.auth_user = None
            st.session_state.settings_loaded_for = None
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
    if st.button("💾 현재 설정 저장", type="primary", use_container_width=True):
        save_user_settings(USER_KEY, {
            "ticker": ticker, "split_n": split_n, "total_principal": total_principal,
            "current_shares": current_shares, "avg_price": avg_price, "t_value": t_value,
            "prev_close": prev_close, "ma5": ma5,
            "crash_max_drop_pct": st.session_state.get("crash_max_drop_pct", 50),
        })
        st.success("저장되었습니다!")

    with st.expander("🔒 내 데이터 관리"):
        st.caption("저장된 내 설정을 완전히 삭제합니다. 되돌릴 수 없습니다.")
        if st.button("내 데이터 삭제", use_container_width=True):
            delete_user_settings(USER_KEY)
            st.success("삭제되었습니다. 새로고침 시 기본값으로 초기화됩니다.")


# =================================================================================
# 5. 공통 계산값
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
# 6. 헤더 & 진행 상황 요약 카드 (FIRE GATE 스타일)
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
            st.metric("적용 공식", explanation)

    st.caption(
        "💡 내일 장 시작 전, 사이드바의 값들을 갱신한 뒤 '💾 현재 설정 저장'을 눌러두면 "
        "다음 로그인 때도 이어서 사용할 수 있습니다."
    )

    with st.expander("📎 참고: 오늘 입력한 체결 수량"):
        st.write(f"- 체결된 매수 수량: {filled_buy_qty:,} 주")
        st.write(f"- 체결된 매도 수량: {filled_sell_qty:,} 주")


# =================================================================================
# 7. 하단 요약 정보
# =================================================================================
st.divider()
st.caption(
    f"현재 설정: {ticker} · {split_n}분할 · T={t_value:g} · 총원금 ${total_principal:,.0f} · "
    f"잔금(자동계산) ${remaining_cash:,.0f} · 보유 {current_shares:,}주 · 평단 ${avg_price:,.2f}"
)
