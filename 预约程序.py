def render_grid(reservations):
    n_dates = len(AVAILABLE_DATES)
    col_weights = [1.3] + [1] * n_dates

    # 用 key="grid" 创建 CSS 作用域
    with st.container(key="grid"):
        # ---------- 表头 ----------
        header_cols = st.columns(col_weights)
        with header_cols[0]:
            st.markdown('<div class="grid-head">时间段</div>', unsafe_allow_html=True)
        for i, d in enumerate(AVAILABLE_DATES):
            with header_cols[i + 1]:
                st.markdown(
                    f'<div class="grid-head">'
                    f'<span>{d.strftime("%m-%d")}</span>'
                    f'<span class="wd">{WEEKDAY_CN[d.weekday()]}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # ---------- 数据行 ----------
        for slot in TIME_SLOTS:
            row_cols = st.columns(col_weights)

            # 第一列：时间段（统一 46px 高度）
            with row_cols[0]:
                st.markdown(
                    f'<div class="grid-slot">{slot}</div>',
                    unsafe_allow_html=True,
                )

            # 其余列：预约按钮
            for i, d in enumerate(AVAILABLE_DATES):
                date_str = d.strftime("%Y-%m-%d")
                key = (date_str, slot)
                with row_cols[i + 1]:
                    if key in reservations:
                        is_mine = (
                            st.session_state.my_employee_id is not None
                            and reservations[key] == st.session_state.my_employee_id
                        )
                        label = "✅ 我的预约" if is_mine else "🔴 已预约"
                        st.button(
                            label,
                            key=f"btn_{date_str}_{slot}",
                            disabled=True,
                            use_container_width=True,
                        )
                    else:
                        if st.button(
                            "🟢 可预约",
                            key=f"btn_{date_str}_{slot}",
                            use_container_width=True,
                        ):
                            st.session_state.pop("dlg_eid", None)
                            st.session_state.pop("dlg_name", None)
                            st.session_state["dialog_slot"] = (date_str, slot)
                            st.rerun()
