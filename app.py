"""
=====================================================================================
무한매수법 V4.0 - 레버리지 ETF 퀀트 대시보드 (디자인 복구 + 코드 노출 완전 차단 버전)
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
st.set_page_config(page_title="무한매수법 V4.0 대시보드", page_icon="🔥", layout="wide")

CUSTOM_UI_CSS = """
<style>
    .stApp { background-color: #F8F9FA; color: #212529; }
    
    /* 사이드바 스타일 및 기본 숨김 처리 */
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

    st.markdown("<div style='font-size: 0.85rem; font-weight: 700; color: #4B5563; margin: 15px 0 8px 0;'>💰 수동 자산 상태</div>", unsafe_allow_html=True)
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
# 5. 메인 UI 구성 (안전한 함수 분리형 디자인 렌더링)
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
        
        ladder_html_items = ""
        if ladder:
            items_str = "".join([f"<div style='font-size: 0.82rem; color: #6B7280; margin-bottom: 4px;'>- LOC ${item['price']:,.2f} × {item['qty']}주</div>" for item in ladder])
            ladder_html_items = f"""
            <div style="background: #FAFAFA; border: 1px solid #F3F4F6; border-radius: 12px; padding: 16px 18px; margin-top: 14px;">
                <div style="font-size: 0.78rem; color: #DC2626; font-weight: 700; margin-bottom: 10px;">+@ 폭락장 대비 추가 매수</div>
                {items_str}
            </div>
            """

        quarter_sell_qty = math.floor(current_shares / 4)
        remain_sell_qty = current_shares - quarter_sell_qty
        target_sell_price = avg_price * (1 + target_pct)
        star_display_str = f"{star_pct*100:.2f}%" if stage_type in ("A", "B") else "—"
        star_pct_val_str = f"{star_pct*100:.2f}%"
        target_pct_val_str = f"{target_pct*100:.0f}%"

        # 1. 상단 진행 상황 카드
        progress_card_html = f"""
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
        """
        st.markdown(progress_card_html, unsafe_allow_html=True)

        # 2. 가이드 헤더 및 상태 배지
        header_html = f"""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
            <h3 style="margin: 0; font-size: 1.4rem; color: #111315;">무한 매수법 가이드</h3>
            <div style="display: flex; gap: 10px;">
                <div style="background: #FFFBEB; border: 1px solid #FDE68A; border-radius: 12px; padding: 8px 14px; text-align: center;">
                    <div style="font-size: 0.7rem; color: #D97706; font-weight: 700;">T 값</div>
                    <div style="font-size: 1.1rem; font-weight: 800; color: #111315;">{t_value:g} 회</div>
                </div>
                <div style="background: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 12px; padding: 8px 14px; text-align: center;">
                    <div style="font-size: 0.7rem; color: #2563EB; font-weight: 700;">Star 값</div>
                    <div style="font-size: 1.1rem; font-weight: 800; color: #111315;">{star_display_str}</div>
                </div>
            </div>
        </div>

        <div style="background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 14px; padding: 14px 20px; display: flex; align-items: center; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.01);">
            <span style="background: #EFF6FF; color: #2563EB; padding: 6px 10px; border-radius: 8px; margin-right: 12px; font-size: 1rem;">📄</span>
            <div>
                <div style="font-size: 0.7rem; color: #6B7280; font-weight: 700; letter-spacing: 0.5px;">CURRENT STATE</div>
                <div style="font-size: 1.1rem; font-weight: 800; color: #111315;">{detected_mode}</div>
            </div>
        </div>
        """
        st.markdown(header_html, unsafe_allow_html=True)

        # 3. 매수 / 매도 가이드 그리드 박스
        col_buy_card, col_sell_card = st.columns(2, gap="medium")

        with col_buy_card:
            buy_card_html = f"""
            <div style="background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 16px; padding: 24px; box-shadow: 0 4px 16px rgba(0,0,0,0.02); height: 100%;">
                <h4 style="color: #DC2626; font-size: 1.1rem; margin-top: 0; margin-bottom: 18px;">매수 가이드</h4>
                <div style="background: #FFFDFD; border: 1px solid #FEE2E2; border-radius: 12px; padding: 18px 20px;">
                    <div style="font-size: 0.8rem; color: #DC2626; font-weight: 700; margin-bottom: 6px;">LOC ★{star_pct_val_str}</div>
                    <div style="font-size: 1.5rem; font-weight: 800; color: #111315;">${buy_point_price_normal:,.2f} <span style="font-size: 1rem; color: #6B7280; font-weight: 600;">× {q_full:,}주</span></div>
                </div>
                {ladder_html_items}
            </div>
            """
            st.markdown(buy_card_html, unsafe_allow_html=True)

        with col_sell_card:
            sell_card_html = f"""
            <div style="background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 16px; padding: 24px; box-shadow: 0 4px 16px rgba(0,0,0,0.02); height: 100%;">
                <h4 style="color: #2563EB; font-size: 1.1rem; margin-top: 0; margin-bottom: 18px;">매도 가이드</h4>
                <div style="background: #F8FAFC; border: 1px solid #DBEAFE; border-radius: 12px; padding: 18px 20px; margin-bottom: 14px;">
                    <div style="font-size: 0.8rem; color: #2563EB; font-weight: 700; margin-bottom: 6px;">LOC ★{star_pct_val_str}</div>
                    <div style="font-size: 1.5rem; font-weight: 800; color: #111315;">${star_price_normal:,.2f} <span style="font-size: 1rem; color: #6B7280; font-weight: 600;">× {quarter_sell_qty:,}주</span></div>
                </div>
                <div style="background: #F8FAFC; border: 1px solid #DBEAFE; border-radius: 12px; padding: 18px 20px;">
                    <div style="font-size: 0.8rem; color: #2563EB; font-weight: 700; margin-bottom: 6px;">지정가 +{target_pct_val_str}</div>
                    <div style="font-size: 1.5rem; font-weight: 800; color: #111315;">${target_sell_price:,.2f} <span style="font-size: 1rem; color: #6B7280; font-weight: 600;">× {remain_sell_qty:,}주</span></div>
                </div>
            </div>
            """
            st.markdown(sell_card_html, unsafe_allow_html=True)

    # ---------------------------------------------------------------------------------
    # [Tab 2] 거래내역 입력
    # ---------------------------------------------------------------------------------
    with tab2:
        history_list = st.session_state.get("trade_history", [])
        
        with st.container(border=True):
            st.markdown("#### 📝 신규 거래 기록 추가")
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
                st.success("거래 내역이 기록되었습니다!")
                st.rerun()

        st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
        history_list = st.session_state.get("trade_history", [])
        
        if history_list:
            if st.button("🗑️ 전체 거래기록 초기화"):
                update_setting("trade_history", [])
                st.rerun()

            for idx, item in enumerate(history_list):
                with st.container(border=True):
                    col_h1, col_h2, col_h3, col_h4, col_h5, col_h6 = st.columns([1, 1.5, 1.8, 1.5, 1, 1.2])
                    col_h1.markdown(f"**#{len(history_list) - idx}**")
                    col_h2.markdown(f"{item['date']}")
                    col_h3.markdown(f"**{item['action']}**")
                    col_h4.markdown(f"${item['price']:,.2f}")
                    col_h5.markdown(f"{item['shares']}주")
                    
                    sub_col_amt, sub_col_del = col_h6.columns([3, 1])
                    sub_col_amt.markdown(f"**${item['amount']:,.2f}**")
                    if sub_col_del.button("✕", key=f"del_{item['id']}_{idx}"):
                        history_list.pop(idx)
                        update_setting("trade_history", history_list)
                        st.rerun()
        else:
            st.info("기록된 거래 내역이 없습니다.")

    # ---------------------------------------------------------------------------------
    # [Tab 3] 거래내역 크로스체크
    # ---------------------------------------------------------------------------------
    with tab3:
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

        diff_shares = st.session_state.current_shares - calc_shares
        diff_avg = st.session_state.avg_price - calc_avg
        diff_t = st.session_state.t_value - max(calc_t, 0.0)

        cross_header_html = f"""
        <div style="background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 16px; padding: 24px; box-shadow: 0 4px 16px rgba(0,0,0,0.02); margin-bottom: 24px;">
            <h3 style="margin-top: 0; font-size: 1.3rem; color: #111315;">🔍 거래내역 크로스체크 및 오차 검증 센터</h3>
            <p style="color: #6B7280; font-size: 0.9rem; margin-bottom: 0;">왼쪽 대시보드(수동 입력값)와 실제 입력된 거래내역들의 누적 계산값을 비교하여 오차를 진단합니다.</p>
        </div>
        """
        st.markdown(cross_header_html, unsafe_allow_html=True)

        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            st.markdown(f"""
            <div style="background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 16px; padding: 20px; box-shadow: 0 4px 16px rgba(0,0,0,0.02);">
                <div style="font-weight: 800; color: #111315; font-size: 1.05rem; margin-bottom: 12px;">보유 주식수 비교</div>
                <div style="font-size: 0.9rem; color: #4B5563; margin-bottom: 4px;">설정: <b>{st.session_state.current_shares}주</b></div>
                <div style="font-size: 0.9rem; color: #4B5563; margin-bottom: 8px;">거래기록: <b>{calc_shares}주</b></div>
                <div style="font-size: 0.9rem; color: {'#DC2626' if diff_shares != 0 else '#059669'}; font-weight: 700;">상태: {f"오차 발생 ({diff_shares:+d}주)" if diff_shares != 0 else "일치함"}</div>
            </div>
            """, unsafe_allow_html=True)

        with col_c2:
            st.markdown(f"""
            <div style="background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 16px; padding: 20px; box-shadow: 0 4px 16px rgba(0,0,0,0.02);">
                <div style="font-weight: 800; color: #111315; font-size: 1.05rem; margin-bottom: 12px;">평균단가 비교</div>
                <div style="font-size: 0.9rem; color: #4B5563; margin-bottom: 4px;">설정: <b>${st.session_state.avg_price:,.2f}</b></div>
                <div style="font-size: 0.9rem; color: #4B5563; margin-bottom: 8px;">거래기록: <b>${calc_avg:,.2f}</b></div>
                <div style="font-size: 0.9rem; color: {'#DC2626' if abs(diff_avg) > 0.01 else '#059669'}; font-weight: 700;">상태: {f"오차 발생 (${diff_avg:+.2f})" if abs(diff_avg) > 0.01 else "일치함"}</div>
            </div>
            """, unsafe_allow_html=True)

        with col_c3:
            st.markdown(f"""
            <div style="background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 16px; padding: 20px; box-shadow: 0 4px 16px rgba(0,0,0,0.02);">
                <div style="font-weight: 800; color: #111315; font-size: 1.05rem; margin-bottom: 12px;">진행 회차(T값) 비교</div>
                <div style="font-size: 0.9rem; color: #4B5563; margin-bottom: 4px;">설정: <b>{st.session_state.t_value:g}회</b></div>
                <div style="font-size: 0.9rem; color: #4B5563; margin-bottom: 8px;">거래기록: <b>{max(calc_t, 0.0):g}회</b></div>
                <div style="font-size: 0.9rem; color: {'#DC2626' if abs(diff_t) > 0.01 else '#059669'}; font-weight: 700;">상태: {f"오차 발생 ({diff_t:+.1f}회)" if abs(diff_t) > 0.01 else "일치함"}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)

        if len(history_list) == 0:
            st.info("비교할 거래 내역이 없습니다.")
        elif diff_shares == 0 and abs(diff_avg) <= 0.01 and abs(diff_t) <= 0.01:
            st.success("✨ 완벽합니다! 사이드바 입력값과 거래내역 누적 계산값이 완전히 일치합니다.")
        else:
            st.warning("⚠️ 사이드바 입력값과 거래기록 누적값 사이에 오차가 존재합니다.")
            if st.button("🔄 거래내역 기준으로 사이드바 값 동기화하기", type="primary"):
                update_setting("current_shares", calc_shares)
                update_setting("avg_price", round(calc_avg, 2))
                update_setting("t_value", round(max(calc_t, 0.0), 2))
                st.success("동기화가 완료되었습니다!")
                st.rerun()
