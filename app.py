"""
=====================================================================================
무한매수법 V4.0 - 레버리지 ETF 퀀트 대시보드 (최종 UI 개선 버전)
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
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF; border-radius: 16px !important;
        border: 1px solid #E5E7EB !important; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.02);
    }
    input, div[data-testid="stNumberInput"] input, div[data-baseweb="select"] > div {
        border: 1px solid #CED4DA !important; border-radius: 8px !important;
    }
    div[data-testid="stMetric"] {
        background-color: #F8F9FA; border-radius: 10px; padding: 10px 14px; border: 1px solid #E9ECEF;
    }
    [data-testid="stMetricValue"] { font-size: 1.3rem; font-weight: 800; color: #111315; }
    [data-testid="stMetricLabel"] { font-size: 0.8rem; color: #6C757D; font-weight: 600; }
    .stTabs [data-baseweb="tab"] { font-weight: 700; font-size: 1rem; color: #4B5563; }
    .stTabs [aria-selected="true"] { color: #2563EB !important; }
    .stTabs [data-baseweb="tab-highlight"] { background-color: #2563EB !important; }
    .badge-v4 { display: inline-block; background: #DCFCE7; color: #166534; font-weight: 800; border-radius: 6px; padding: 3px 8px; font-size: 0.8rem; border: 1px solid #BBF7D0; vertical-align: middle; margin-left: 8px; }
    
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
    "ticker": "TQQQ",
    "split_n": 20,
    "total_principal": 10000.0,
    "current_shares": 0,
    "avg_price": 0.0,
    "t_value": 0.0,
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
    st.metric("남은 잔금", f"${remaining_cash:,.2f}")

    st.divider()
    st.markdown("#### 🌐 시장 데이터")
    auto_close, auto_ma5 = fetch_market_data(st.session_state.ticker)

    if auto_close is not None:
        prev_close = auto_close
        ma5 = auto_ma5
        st.metric("전일 종가", f"${prev_close:,.2f}")
        st.metric("5일 평균가", f"${ma5:,.2f}")
        st.success("야후 파이낸스 연동 완료")
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
        if n - base_qty > 7:
            break
    return ladder


# =================================================================================
# 5. 메인 UI 구성
# =================================================================================
st.markdown(f"<h1>{ticker} <span class='badge-v4'>V4.0</span></h1>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["🎯 오늘의 매수/매도 가이드", "⚡ 거래내역 입력"])

with tab1:
    # 1. 최상단 진행률 바 (가장 가시성 있게 배치)
    with st.container(border=True):
        progress_ratio = min(t_value / split_n, 1.0) if split_n > 0 else 0.0
        st.progress(progress_ratio, text=f"🔥 전체 분할 진행률: {progress_ratio*100:.1f}% (T = {t_value:g} / {split_n}분할)")

    st.markdown("<div style='margin: 10px 0;'></div>", unsafe_allow_html=True)

    # 2. 상태 정보 카드 (동일한 높이와 패딩으로 정렬)
    top_col1, top_col2, top_col3 = st.columns(3)
    
    with top_col1:
        st.markdown(f"""
        <div style="background: #FFFFFF; padding: 16px 20px; border-radius: 14px; border: 1px solid #E5E7EB; text-align: center; height: 85px; display: flex; flex-direction: column; justify-content: center;">
            <div style="font-size: 0.75rem; color: #6B7280; font-weight: 700; letter-spacing: 0.5px;">CURRENT STATE</div>
            <div style="font-size: 1.15rem; font-weight: 800; color: #111315; margin-top: 4px;">{detected_mode}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with top_col2:
        st.markdown(f"""
        <div style="background: #FFFFFF; padding: 16px 20px; border-radius: 14px; border: 1px solid #E5E7EB; text-align: center; height: 85px; display: flex; flex-direction: column; justify-content: center;">
            <div style="font-size: 0.75rem; color: #D97706; font-weight: 700;">T 값</div>
            <div style="font-size: 1.15rem; font-weight: 800; color: #111315; margin-top: 4px;">{t_value:g} <span style="font-size: 0.8rem; font-weight: 600;">회</span></div>
        </div>
        """, unsafe_allow_html=True)
        
    with top_col3:
        star_display = f"{star_pct*100:.2f}%" if stage_type in ("A", "B") else "—"
        st.markdown(f"""
        <div style="background: #FFFFFF; padding: 16px 20px; border-radius: 14px; border: 1px solid #E5E7EB; text-align: center; height: 85px; display: flex; flex-direction: column; justify-content: center;">
            <div style="font-size: 0.75rem; color: #2563EB; font-weight: 700;">STAR 값</div>
            <div style="font-size: 1.15rem; font-weight: 800; color: #111315; margin-top: 4px;">{star_display}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin: 14px 0;'></div>", unsafe_allow_html=True)

    # 3. 매수/매도 가이드 영역 (완전 독립된 CSS 박스로 선 겹침 원천 차단)
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
            <span style="color: #1D4ED8; font-weight: 700; font-size: 0.9rem;">📝 거래 유형 선택 및 입력</span>
        </div>
        """, unsafe_allow_html=True)

        col_i1, col_i2 = st.columns(2)
        trade_date = col_i1.date_input("체결 날짜", value=datetime.today())
        
        # 큰 갈래 (매수 / 매도) 선택 후 상세 옵션 연동
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

        if st.button("➕ 거래 내역 추가 및 반영", type="primary", use_container_width=True):
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

            recalc_shares, recalc_total_cost, recalc_t = 0, 0.0, 0.0
            for h in history_list:
                recalc_t += h["t_impact"]
                if "매수" in h["action"]:
                    recalc_shares += h["shares"]
                    recalc_total_cost += h["amount"]
                elif "매도" in h["action"] or "전량" in h["action"]:
                    recalc_shares = max(recalc_shares - h["shares"], 0)
            recalc_avg_price = (recalc_total_cost / recalc_shares) if recalc_shares > 0 else 0.0

            update_setting("current_shares", recalc_shares)
            update_setting("avg_price", round(recalc_avg_price, 2))
            update_setting("t_value", round(max(recalc_t, 0.0), 2))
            st.success("반영 완료!")
            st.rerun()

    # 거래 내역 표
    st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
    history_list = st.session_state.get("trade_history", [])
    
    if history_list:
        if st.button("🗑️ 전체 초기화"):
            update_setting("trade_history", [])
            update_setting("current_shares", 0)
            update_setting("avg_price", 0.0)
            update_setting("t_value", 0.0)
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
                
                recalc_shares, recalc_total_cost, recalc_t = 0, 0.0, 0.0
                for h in history_list:
                    recalc_t += h["t_impact"]
                    if "매수" in h["action"]:
                        recalc_shares += h["shares"]
                        recalc_total_cost += h["amount"]
                    elif "매도" in h["action"] or "전량" in h["action"]:
                        recalc_shares = max(recalc_shares - h["shares"], 0)
                recalc_avg_price = (recalc_total_cost / recalc_shares) if recalc_shares > 0 else 0.0

                update_setting("current_shares", recalc_shares)
                update_setting("avg_price", round(recalc_avg_price, 2))
                update_setting("t_value", round(max(recalc_t, 0.0), 2))
                st.rerun()
                
            st.markdown("<div style='border-bottom: 1px solid #F3F4F6; margin: 6px 0;'></div>", unsafe_allow_html=True)
    else:
        st.info("기록된 거래 내역이 없습니다.")
