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

        # 1. 상단 진행 상황 카드 (Streamlit 네이티브 컨테이너 + 스타일 조합으로 코드 노출 원천 차단)
        with st.container(border=True):
            col_pr_t1, col_pr_t2 = st.columns([8, 2])
            col_pr_t1.markdown("<span style='font-size: 1.1rem; font-weight: 800; color: #111315;'>진행 상황</span>", unsafe_allow_html=True)
            col_pr_t2.markdown(f"<div style='text-align: right; font-size: 0.95rem; font-weight: 700; color: #2563EB;'>{progress_ratio*100:.1f}%</div>", unsafe_allow_html=True)
            
            st.progress(float(progress_ratio))
            
            st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
            col_m_1, col_m_2 = st.columns(2)
            col_m_1.metric("시드", f"{total_principal:,.0f} USD")
            col_m_2.metric("사용한 시드", f"{used_amount_calc:,.2f} USD")
            
            st.divider()
            
            col_sub_1, col_sub_2, col_sub_3 = st.columns(3)
            col_sub_1.metric("매입 금액", f"{used_amount_calc:,.2f} USD")
            col_sub_2.metric("평단가", f"{avg_price:,.3f} USD")
            col_sub_3.metric("보유 수량", f"{current_shares:,} 주")

        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

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
