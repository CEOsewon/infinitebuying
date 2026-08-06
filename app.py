"""
=====================================================================================
무한매수법 V4.0 - 레버리지 ETF(TQQQ / SOXL) 퀀트 매매 대시보드
=====================================================================================
- 매일 장 시작 전: '오늘 주문 계산기' 탭에서 오늘 걸어야 할 주문(가격/수량)을 확인
- 장 마감 후: '체결 결과 입력 & T값 업데이트' 탭에서 체결 결과를 입력하고
  내일을 위한 새로운 T값(진행 회차)을 계산

⚠️ 주의: 이 앱은 특정 개인 전략(무한매수법 V4.0)을 코드로 구현한 계산 도구이며,
투자 조언이 아닙니다. 모든 매매 판단과 최종 책임은 사용자 본인에게 있습니다.
=====================================================================================
"""

import math
import streamlit as st

# -------------------------------------------------------------------------------
# 0. 기본 페이지 설정
# -------------------------------------------------------------------------------
st.set_page_config(page_title="무한매수법 V4.0 대시보드", layout="wide")
st.title("📈 무한매수법 V4.0 - 레버리지 ETF 매매 대시보드")
st.caption("TQQQ / SOXL 대상 · 분할매수 + 리버스(소진)모드 지원 · 본 계산기는 투자 조언이 아닙니다.")


# =================================================================================
# 1. 핵심 계산 함수들
# =================================================================================

def get_star_percent(ticker: str, split_n: int, t: float) -> float:
    """
    별지점(Star Point) % 계산
    - 종목(TQQQ/SOXL)과 분할수(20/40)에 따라 공식이 다름
    - T(진행 회차)가 커질수록 별% 는 점점 작아지는 구조 (초반엔 목표수익률 높게, 후반엔 낮게)
    """
    if ticker == "TQQQ":
        if split_n == 20:
            pct = (15 - 1.5 * t) / 100
        else:  # 40분할
            pct = (15 - 0.75 * t) / 100
    else:  # SOXL
        if split_n == 20:
            pct = (20 - 2 * t) / 100
        else:  # 40분할
            pct = (20 - t) / 100
    return pct


def get_target_profit_percent(ticker: str) -> float:
    """
    지정가 매도(잔여 3/4 수량)에 사용하는 목표 수익률
    - TQQQ: +15%, SOXL: +20%
    - 리버스모드 종료 조건(-15%/-20%)에도 동일한 값을 사용
    """
    return 0.15 if ticker == "TQQQ" else 0.20


def calc_star_price_normal(avg_price: float, star_pct: float) -> float:
    """일반모드 별지점 가격 = 평단가 * (1 + 별%)"""
    return avg_price * (1 + star_pct)


def calc_buy_point_price(star_price: float) -> float:
    """매수점 가격 = 별지점 가격 - 0.01달러 (매도 주문과 겹치지 않도록 살짝 낮춤)"""
    return star_price - 0.01


def calc_daily_buy_amount_normal(remaining_cash: float, split_n: int, t: float) -> float:
    """일반모드 1회 매수금 = 남은 잔금 / (분할수 - T)"""
    denom = split_n - t
    if denom <= 0:
        return 0.0
    return remaining_cash / denom


def calc_daily_buy_amount_reverse(remaining_cash: float) -> float:
    """리버스모드 1회 매수금(쿼터매수) = 남은 잔금 / 4"""
    return remaining_cash / 4


# =================================================================================
# 2. 사이드바 - 사용자 입력값
# =================================================================================
with st.sidebar:
    st.header("⚙️ 오늘의 입력값")

    st.subheader("1. 종목 & 분할 설정")
    ticker = st.selectbox("종목 선택", ["TQQQ", "SOXL"])
    split_n = st.selectbox("분할 수 (Split_N)", [20, 40])

    st.subheader("2. 현재 상태")
    total_principal = st.number_input("총 투자 원금 ($)", min_value=0.0, value=10000.0, step=100.0)
    remaining_cash = st.number_input("현재 남은 잔금 ($)", min_value=0.0, value=5000.0, step=100.0)
    current_shares = st.number_input("현재 보유 주식 수 (주)", min_value=0, value=100, step=1)
    avg_price = st.number_input("현재 평단가 ($)", min_value=0.0, value=50.0, step=0.01, format="%.2f")
    t_value = st.number_input("현재 진행 회차 (T값)", min_value=0.0, value=5.0, step=0.1, format="%.2f")

    st.subheader("3. 시장 데이터")
    prev_close = st.number_input("전일 종가 ($)", min_value=0.0, value=50.0, step=0.01, format="%.2f")
    ma5 = st.number_input("최근 5거래일 종가 평균 ($)", min_value=0.0, value=50.0, step=0.01, format="%.2f")

    st.subheader("4. 현재 모드 단계")
    # T값만으로는 '리버스모드 진입 첫날'인지 '둘째날 이후'인지 기계적으로 구분하기 어렵기 때문에
    # (며칠째 리버스모드인지는 일자별 이력이 있어야 정확히 판별 가능),
    # 사용자가 직접 현재 상태를 선택하도록 구성했습니다.
    mode_stage = st.radio(
        "현재 어떤 단계인가요?",
        ["일반모드 (전반전/후반전 자동판별)", "리버스모드 - 진입 첫날", "리버스모드 - 둘째날 이후"],
    )

st.sidebar.info(f"분할수 절반 지점(Split_N/2) = **{split_n/2:g}**  ·  리버스 진입 기준(Split_N-1) = **{split_n-1:g}**")


# =================================================================================
# 3. 공통 계산값 미리 산출
# =================================================================================
star_pct = get_star_percent(ticker, split_n, t_value)
target_pct = get_target_profit_percent(ticker)

star_price_normal = calc_star_price_normal(avg_price, star_pct)          # 일반모드 별지점 가격
star_price_reverse = ma5                                                  # 리버스모드 별지점 가격 = 5일 평균종가
buy_point_price_normal = calc_buy_point_price(star_price_normal)
buy_point_price_reverse = calc_buy_point_price(star_price_reverse)

daily_buy_amount_normal = calc_daily_buy_amount_normal(remaining_cash, split_n, t_value)
daily_buy_amount_reverse = calc_daily_buy_amount_reverse(remaining_cash)

target_sell_price = avg_price * (1 + target_pct)      # 잔여 3/4 수량 지정가 매도가
reverse_exit_price = avg_price * (1 - target_pct)      # 리버스모드 종료 기준가(평단 대비 -15%/-20%)


# =================================================================================
# 4. 탭 구성
# =================================================================================
tab1, tab2 = st.tabs(["🧮 오늘 주문 계산기", "✅ 체결 결과 입력 & T값 업데이트"])


# ---------------------------------------------------------------------------------
# TAB 1. 오늘 주문 계산기
# ---------------------------------------------------------------------------------
with tab1:
    half_split = split_n / 2

    # -----------------------------------------------------------------------
    # A/B/C/D 단계 판별
    # -----------------------------------------------------------------------
    if mode_stage.startswith("일반모드"):
        if t_value >= split_n - 1:
            stage = "WARN"  # 일반모드로 선택했지만 T값이 이미 리버스 진입 기준을 넘음
        elif t_value < half_split:
            stage = "A"
        else:
            stage = "B"
    elif mode_stage == "리버스모드 - 진입 첫날":
        stage = "C"
    else:
        stage = "D"

    # =====================================================================
    # WARN: 리버스모드 진입 시점 알림
    # =====================================================================
    if stage == "WARN":
        st.warning(
            f"⚠️ 현재 T값({t_value:g})이 리버스모드 진입 기준(Split_N - 1 = {split_n-1:g}) 이상입니다.\n\n"
            "사이드바에서 '리버스모드 - 진입 첫날'을 선택해주세요."
        )

    # =====================================================================
    # A, B: 일반모드 (전반전 / 후반전)
    # =====================================================================
    elif stage in ("A", "B"):
        stage_name = "A. 일반모드 - 전반전" if stage == "A" else "B. 일반모드 - 후반전"
        st.subheader(f"현재 단계: {stage_name}")

        st.markdown("### 🔴 매도 주문")
        col1, col2 = st.columns(2)

        # --- 매도 ①: 보유수량의 1/4을 별지점 가격에 LOC 매도 ---
        quarter_sell_qty = math.floor(current_shares / 4)
        with col1:
            st.markdown("**① 1/4 수량 · 별지점 LOC 매도**")
            st.metric("매도 단가 (별지점가)", f"${star_price_normal:,.2f}")
            st.metric("매도 수량", f"{quarter_sell_qty:,} 주")

        # --- 매도 ②: 나머지 3/4 수량을 평단가 대비 +15%/+20% 지정가 매도 ---
        remain_sell_qty = current_shares - quarter_sell_qty
        with col2:
            st.markdown(f"**② 나머지 3/4 수량 · 지정가(+{target_pct*100:.0f}%) 매도**")
            st.metric("매도 단가 (목표가)", f"${target_sell_price:,.2f}")
            st.metric("매도 수량", f"{remain_sell_qty:,} 주")

        st.markdown("### 🔵 매수 주문")

        if stage == "A":
            # 전반전: 1회 매수금의 절반은 매수점가에 LOC, 나머지 절반은 평단가에 LOC
            half_amount = daily_buy_amount_normal / 2
            buy_qty_at_buy_point = math.floor(half_amount / buy_point_price_normal) if buy_point_price_normal > 0 else 0
            buy_qty_at_avg = math.floor(half_amount / avg_price) if avg_price > 0 else 0

            colA, colB = st.columns(2)
            with colA:
                st.markdown("**① 절반 금액 · 매수점가 LOC 매수**")
                st.metric("매수 단가 (매수점가)", f"${buy_point_price_normal:,.2f}")
                st.metric("매수 수량", f"{buy_qty_at_buy_point:,} 주")
                st.caption(f"배정 금액: ${half_amount:,.2f}")
            with colB:
                st.markdown("**② 절반 금액 · 평단가 LOC 매수**")
                st.metric("매수 단가 (평단가)", f"${avg_price:,.2f}")
                st.metric("매수 수량", f"{buy_qty_at_avg:,} 주")
                st.caption(f"배정 금액: ${half_amount:,.2f}")

        else:
            # 후반전: 1회 매수금 전체를 매수점가에 LOC
            buy_qty_full = math.floor(daily_buy_amount_normal / buy_point_price_normal) if buy_point_price_normal > 0 else 0
            st.markdown("**1회 매수금 전액 · 매수점가 LOC 매수**")
            colX, colY = st.columns(2)
            with colX:
                st.metric("매수 단가 (매수점가)", f"${buy_point_price_normal:,.2f}")
            with colY:
                st.metric("매수 수량", f"{buy_qty_full:,} 주")
            st.caption(f"배정 금액: ${daily_buy_amount_normal:,.2f}")

        with st.expander("📎 계산 상세 (별%, 1회 매수금 등)"):
            st.write(f"- 별% (Star %) = **{star_pct*100:.3f}%**")
            st.write(f"- 별지점 가격 = 평단가 × (1 + 별%) = **${star_price_normal:,.2f}**")
            st.write(f"- 매수점 가격 = 별지점 가격 - 0.01 = **${buy_point_price_normal:,.2f}**")
            st.write(f"- 1회 매수금 = 남은 잔금 ÷ (분할수 - T) = ${remaining_cash:,.2f} ÷ ({split_n} - {t_value:g}) = **${daily_buy_amount_normal:,.2f}**")

    # =====================================================================
    # C: 리버스(소진)모드 진입 첫날
    # =====================================================================
    elif stage == "C":
        st.subheader("C. 리버스(소진)모드 진입 첫날")
        st.info("이 단계에서는 매수 없이, 정해진 수량을 종가(MOC)로 무조건 매도합니다.")

        moc_sell_qty = math.floor(current_shares / half_split) if half_split > 0 else 0

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**🔴 매도 (MOC, 종가매도)**")
            st.metric("매도 방식", "MOC (동시호가 종가매도)")
            st.metric("매도 수량", f"{moc_sell_qty:,} 주")
            st.caption(f"= 보유수량 {current_shares:,}주 ÷ (분할수/2 = {half_split:g}) 내림")
        with col2:
            st.markdown("**🔵 매수**")
            st.write("없음 (진입 첫날은 매수하지 않음)")

    # =====================================================================
    # D: 리버스(소진)모드 둘째 날 이후
    # =====================================================================
    else:
        st.subheader("D. 리버스(소진)모드 - 둘째날 이후")

        # --- 리버스모드 종료 조건 체크 ---
        if prev_close > reverse_exit_price:
            st.success(
                f"✅ 전일 종가(${prev_close:,.2f})가 리버스모드 종료 기준가(평단 대비 -{target_pct*100:.0f}% = "
                f"${reverse_exit_price:,.2f})보다 높습니다.\n\n"
                "**→ 리버스모드를 종료하고 일반모드로 즉시 복귀하세요.** "
                "(사이드바에서 '일반모드'로 전환 후 다시 계산해주세요.)"
            )
        else:
            st.warning(
                f"전일 종가(${prev_close:,.2f})가 종료 기준가(${reverse_exit_price:,.2f}) 이하이므로 "
                "리버스모드를 계속 유지합니다."
            )

            st.markdown("### 🔴 매도 주문 (LOC)")
            reverse_sell_qty = math.floor(current_shares / half_split) if half_split > 0 else 0
            col1, col2 = st.columns(2)
            with col1:
                st.metric("매도 단가 (별지점가=5일선)", f"${star_price_reverse:,.2f} 이상")
            with col2:
                st.metric("매도 수량", f"{reverse_sell_qty:,} 주")
            st.caption(f"= 전일 보유수량 {current_shares:,}주 ÷ (분할수/2 = {half_split:g}) 내림, 별지점가 이상에서 LOC 매도")

            st.markdown("### 🔵 매수 주문 (쿼터매수)")
            reverse_buy_qty = math.floor(daily_buy_amount_reverse / buy_point_price_reverse) if buy_point_price_reverse > 0 else 0

            if reverse_buy_qty < 1:
                # 쿼터매수 금액으로 1주도 살 수 없는 경우 → 매수 없이 MOC 매도(C룰) 시행
                st.error("❌ 쿼터매수 금액으로 1주도 매수할 수 없습니다. 매수 대신 MOC 매도(C 규칙)를 시행하세요.")
                fallback_moc_qty = math.floor(current_shares / half_split) if half_split > 0 else 0
                st.metric("MOC 매도 수량 (대체 실행)", f"{fallback_moc_qty:,} 주")
            else:
                col3, col4 = st.columns(2)
                with col3:
                    st.metric("매수 단가 (매수점가, 별지점가 아래)", f"${buy_point_price_reverse:,.2f}")
                with col4:
                    st.metric("매수 수량", f"{reverse_buy_qty:,} 주")
                st.caption(f"배정 금액(잔금÷4): ${daily_buy_amount_reverse:,.2f}")

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

    st.markdown(
        "아래에서 오늘 실제로 어떤 주문이 체결되었는지 시나리오를 선택하세요. "
        "체결 수량은 참고용 기록으로 함께 입력받습니다."
    )

    col1, col2 = st.columns(2)
    with col1:
        filled_buy_qty = st.number_input("체결된 매수 수량 (주)", min_value=0, value=0, step=1)
    with col2:
        filled_sell_qty = st.number_input("체결된 매도 수량 (주)", min_value=0, value=0, step=1)

    update_mode = st.radio("업데이트 대상 모드", ["일반모드", "리버스모드"], horizontal=True)

    new_t = t_value  # 기본값: 변화 없음
    explanation = ""

    if update_mode == "일반모드":
        # -----------------------------------------------------------------
        # 일반모드 T값 변화 규칙
        # -----------------------------------------------------------------
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
            new_t = t_value + 1
            explanation = "T + 1"
        elif scenario.startswith("1회 매수금 절반"):
            new_t = t_value + 0.5
            explanation = "T + 0.5"
        elif scenario.startswith("쿼터매도"):
            new_t = t_value * 0.75
            explanation = "T × 0.75"
        elif scenario.startswith("지정가 매도 체결 후 LOC 매수까지 절반"):
            new_t = t_value * 0.25 + 0.5
            explanation = "T × 0.25 + 0.5"
        elif scenario.startswith("지정가 매도 체결 후 LOC 매수까지 전액"):
            new_t = t_value * 0.25 + 1
            explanation = "T × 0.25 + 1"
        else:
            new_t = t_value
            explanation = "변화 없음"

    else:
        # -----------------------------------------------------------------
        # 리버스모드 T값 변화 규칙 (분할수에 따라 계수가 다름)
        # -----------------------------------------------------------------
        scenario = st.radio(
            "오늘 발생한 체결 시나리오를 선택하세요",
            ["매도 체결 발생", "매수(쿼터매수) 체결 발생", "변화 없음 (미체결)"],
        )

        sell_factor = 0.9 if split_n == 20 else 0.95  # 20분할: ×0.9 / 40분할: ×0.95

        if scenario == "매도 체결 발생":
            new_t = t_value * sell_factor
            explanation = f"T × {sell_factor} ({split_n}분할 리버스모드 매도 체결)"
        elif scenario == "매수(쿼터매수) 체결 발생":
            new_t = t_value + (split_n - t_value) * 0.25
            explanation = f"T + ({split_n} - T) × 0.25 ({split_n}분할 리버스모드 매수 체결)"
        else:
            new_t = t_value
            explanation = "변화 없음"

    st.markdown("### 📌 계산 결과")
    colr1, colr2, colr3 = st.columns(3)
    with colr1:
        st.metric("기존 T값", f"{t_value:.3f}")
    with colr2:
        st.metric("👉 내일의 새로운 T값", f"{new_t:.3f}")
    with colr3:
        st.metric("적용 공식", explanation)

    st.caption(
        "💡 내일 장 시작 전, 사이드바의 '현재 진행 회차 (T값)'에 위에서 계산된 새로운 T값을 입력한 뒤 "
        "'오늘 주문 계산기' 탭을 다시 확인하세요."
    )

    with st.expander("📎 참고: 오늘 입력한 체결 수량"):
        st.write(f"- 체결된 매수 수량: {filled_buy_qty:,} 주")
        st.write(f"- 체결된 매도 수량: {filled_sell_qty:,} 주")


# =================================================================================
# 5. 하단 요약 정보
# =================================================================================
st.divider()
st.caption(
    f"현재 설정: {ticker} · {split_n}분할 · T={t_value:g} · 총원금 ${total_principal:,.0f} · "
    f"잔금 ${remaining_cash:,.0f} · 보유 {current_shares:,}주 · 평단 ${avg_price:,.2f}"
)
