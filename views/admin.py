import streamlit as st
import datetime
import os
import pandas as pd
import streamlit.components.v1 as components
from db import (
    get_all_users, update_user_role, delete_user,
    get_geodream_theme, update_geodream_theme,
    get_zones, update_zone, delete_zone,
    get_fms_status, _detect_fms_columns, _aggregate_fms_data, upload_fms_excel,
    get_portal_config, update_portal_config,
    get_sitemap_config, update_sitemap_config,
    get_custom_fonts, get_category_styles, update_category_styles,
    get_public_guides,
    get_audit_logs, get_inventory_summary,
    get_current_layout, save_layout, get_layout_history,
    _load_shared_state, _save_shared_state,
    get_admin_cards, update_admin_cards,
    get_user_card_order, update_user_card_order
)
from components_loader import map_editor_component

# 현재 뷰 상태 초기화
if "admin_current_view" not in st.session_state:
    st.session_state["admin_current_view"] = "home"

st.title("📊 관리자 대시보드")

admin_cards = get_admin_cards()
cards_dict = {c['id']: c for c in admin_cards}

current_user = st.session_state.get("user_id", "")
if current_user:
    custom_order = get_user_card_order(current_user)
    if custom_order:
        ordered_cards = []
        for cid in custom_order:
            if cid in cards_dict:
                ordered_cards.append(cards_dict[cid])
        for c in admin_cards:
            if c['id'] not in custom_order:
                ordered_cards.append(c)
        admin_cards = ordered_cards



if st.session_state["admin_current_view"] != "home":
    if st.button("🔙 전체 메뉴로 돌아가기 (그리드 홈)", type="primary"):
        st.session_state["admin_current_view"] = "home"
        st.rerun()
    st.divider()

if st.session_state["admin_current_view"] == "home":
    st.markdown("""
    <style>
    .admin-card {
        background: #ffffff;
        border: 2px solid #e0e0e0;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 10px;
        transition: all 0.3s ease;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        height: 120px;
        display: flex;
        flex-direction: column;
    }
    .admin-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 20px rgba(0,0,0,0.1);
        border-color: #ff6b6b;
    }
    .admin-card h3 {
        margin-top: 0;
        margin-bottom: 8px;
        color: #1f2937;
        font-size: 1.1rem;
        font-weight: 800;
        letter-spacing: -0.5px;
    }
    .admin-card p {
        color: #6b7280;
        font-size: 0.85rem;
        flex-grow: 1;
        margin: 0;
        line-height: 1.3;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.subheader("모듈 선택")

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        edit_mode = st.toggle("📝 대시보드 메뉴 텍스트 수정 모드")
    with col_t2:
        reorder_mode = st.toggle("↕️ 내 대시보드 메뉴 순서 변경")
        
    if edit_mode:
        st.info("각 메뉴 카드의 아이콘, 제목, 설명을 수정한 뒤 하단의 '변경사항 저장' 버튼을 누르세요.")
        with st.form("edit_admin_cards_form"):
            new_cards = []
            for c in admin_cards:
                col1, col2, col3 = st.columns([1, 3, 6])
                icon = col1.text_input("아이콘", value=c['icon'], key=f"i_{c['id']}")
                title = col2.text_input(f"제목 ({c['id']})", value=c['title'], key=f"t_{c['id']}")
                desc = col3.text_input("설명", value=c['desc'], key=f"d_{c['id']}")
                new_cards.append({"id": c['id'], "icon": icon, "title": title, "desc": desc})
            if st.form_submit_button("💾 전체 메뉴 텍스트 변경사항 저장", type="primary"):
                update_admin_cards(new_cards)
                st.success("메뉴 설정이 저장되었습니다.")
                st.rerun()
    elif reorder_mode:
        st.info("카드의 순서를 위/아래 버튼으로 변경하고 저장하세요. (내 계정에만 적용됩니다)")
        
        # Initialize order state if not exists or if mismatched
        current_ids = [c["id"] for c in admin_cards]
        if "temp_order" not in st.session_state or set(st.session_state["temp_order"]) != set(current_ids):
            st.session_state["temp_order"] = current_ids
            
        temp_order = st.session_state["temp_order"]
        
        for i, cid in enumerate(temp_order):
            c = cards_dict[cid]
            col1, col2, col3, col4 = st.columns([1, 4, 1, 1])
            col1.markdown(f"**{i+1}**")
            col2.markdown(f"{c['icon']} {c['title']}")
            
            with col3:
                if i > 0:
                    if st.button("🔼", key=f"up_{cid}"):
                        temp_order[i], temp_order[i-1] = temp_order[i-1], temp_order[i]
                        st.session_state["temp_order"] = temp_order
                        st.rerun()
            with col4:
                if i < len(temp_order) - 1:
                    if st.button("🔽", key=f"dn_{cid}"):
                        temp_order[i], temp_order[i+1] = temp_order[i+1], temp_order[i]
                        st.session_state["temp_order"] = temp_order
                        st.rerun()
                        
        if st.button("💾 내 순서 저장", type="primary"):
            update_user_card_order(current_user, st.session_state["temp_order"])
            st.success("내 맞춤 순서가 저장되었습니다.")
            st.rerun()
    else:
        # 3열 그리드로 카드 렌더링
        for row_idx in range(0, len(admin_cards), 3):
            cols = st.columns(3)
            for col_idx in range(3):
                if row_idx + col_idx < len(admin_cards):
                    card = admin_cards[row_idx + col_idx]
                    with cols[col_idx]:
                        st.markdown(f"""
                        <div class="admin-card">
                            <h3>{card['icon']} {card['title']}</h3>
                            <p>{card['desc']}</p>
                        </div>
                        """, unsafe_allow_html=True)
                        if st.button(f"{card['title']} 편집하기", key=f"btn_go_{card['id']}", use_container_width=True):
                            st.session_state["admin_current_view"] = card['id']
                            st.rerun()

elif st.session_state["admin_current_view"] == "users":
    c = cards_dict.get("users", {})
    st.header(f"{c.get('icon', '')} {c.get('title', '')}")
    users = get_all_users()
    
    role_labels = {
        "user": "승인 대기 (권한 없음)",
        "operator": "현장운영 (바코드 POS / PC)",
        "inventory": "재고관리 (모바일 실사)",
        "schedule": "스케줄 관리자 (일정 관리)",
        "admin": "총괄 관리자 (모든 권한)"
    }
    inverse_role_labels = {v: k for k, v in role_labels.items()}
    
    for u in users:
        user_roles = u.get('role', ['user'])
        if isinstance(user_roles, str):
            user_roles = [user_roles]
            
        current_labels = [role_labels.get(r, r) for r in user_roles]
        label_str = ", ".join(current_labels)
        
        with st.expander(f"👤 {u['name']} ({u['user_id']}) - 현재 권한: {label_str}"):
            col1, col2 = st.columns(2)
            with col1:
                options = list(role_labels.values())
                valid_current_labels = [lbl for lbl in current_labels if lbl in options]
                
                selected_labels = st.multiselect("부여할 권한들을 모두 선택하세요:", options, default=valid_current_labels, key=f"role_{u['user_id']}")
                
                if st.button("권한 부여 / 수정", key=f"btn_role_{u['user_id']}", type="primary"):
                    new_roles = [inverse_role_labels[lbl] for lbl in selected_labels]
                    if not new_roles:
                        new_roles = ["user"]
                    update_user_role(u['user_id'], new_roles)
                    st.success("권한이 성공적으로 업데이트 되었습니다.")
                    st.rerun()
            with col2:
                st.write("계정 영구 삭제")
                if st.button("계정 삭제", key=f"btn_del_{u['user_id']}"):
                    delete_user(u['user_id'])
                    st.warning("삭제되었습니다.")
                    st.rerun()

elif st.session_state["admin_current_view"] == "space":
    c = cards_dict.get("space", {})
    st.header(f"{c.get('icon', '')} {c.get('title', '')}")
    
    tab1, tab2 = st.tabs(["🏗️ 구역 텍스트 구조 관리", "🗺️ 대화형 평면도 에디터"])
    
    with tab1:
        st.write("모바일 재고 실사 앱에 표시될 블록형 동적 맵의 구역(대구역)과 세부 구역(소구역)을 관리합니다.")
        
        zones = get_zones()
        for z_name, sub_zones in zones.items():
            with st.expander(f"📍 {z_name}"):
                new_sub = st.text_input("세부 구역 목록 (쉼표 `,` 로 구분하여 입력)", value=", ".join(sub_zones), key=f"sz_{z_name}")
                col1, col2 = st.columns(2)
                if col1.button("구역 구조 수정 저장", key=f"btn_upd_{z_name}", type="primary"):
                    update_zone(z_name, [x.strip() for x in new_sub.split(",") if x.strip()])
                    st.success("구역 구조가 저장되었습니다.")
                    st.rerun()
                if col2.button("이 대구역 통째로 삭제", key=f"btn_del_{z_name}"):
                    delete_zone(z_name)
                    st.warning("구역이 삭제되었습니다.")
                    st.rerun()
        
        st.write("---")
        st.subheader("➕ 새로운 대구역 추가")
        with st.form("new_zone_form", clear_on_submit=True):
            new_z_name = st.text_input("새 대구역 이름 (예: [구역4] 외부 냉동고)")
            new_sz_list = st.text_input("세부 구역 목록 (쉼표 `,` 로 구분, 예: 좌측 문, 우측 문)")
            if st.form_submit_button("신규 구역 추가", type="primary"):
                if new_z_name:
                    update_zone(new_z_name, [x.strip() for x in new_sz_list.split(",") if x.strip()])
                    st.success(f"{new_z_name} 구역이 시스템에 추가되었습니다.")
                    st.rerun()

    with tab2:
        st.write("아래 도면에서 박스(랙)를 마우스로 드래그하여 자유롭게 배치하고 저장하세요.")
        
        history = get_layout_history()
        if history:
            st.subheader("⏱️ 과거 평면도로 복원 (타임머신)")
            history_options = {f"{h['timestamp']} (저장: {h.get('saved_by', 'admin')})": h['data'] for h in history}
            selected_hist = st.selectbox("과거 시점 선택", ["현재 유지"] + list(history_options.keys()))
            if selected_hist != "현재 유지":
                if st.button("선택한 시점으로 평면도 복구", type="primary"):
                    save_layout(history_options[selected_hist])
                    st.success("과거 평면도로 성공적으로 복원되었습니다.")
                    st.rerun()
        
        st.subheader("🛠️ 에디터 화면")
        full_layout = get_current_layout()
        
        if "zone_1" in full_layout:
            zone_keys = list(full_layout.keys())
            zone_names = [full_layout[k].get("name", k) for k in zone_keys]
            tabs = st.tabs(zone_names)
            
            for i, tab in enumerate(tabs):
                with tab:
                    z_key = zone_keys[i]
                    current_zone_data = full_layout[z_key]
                    
                    result = map_editor_component(layout_data=current_zone_data, key=f"map_editor_ui_{z_key}")
                    
                    if result is not None:
                        if full_layout[z_key] != result:
                            full_layout[z_key] = result
                            save_layout(full_layout)
                            st.success(f"[{zone_names[i]}] 레이아웃이 성공적으로 저장되었습니다!")
                            st.rerun()
        else:
            result = map_editor_component(layout_data=full_layout, key="map_editor_ui_legacy")
            if result is not None and full_layout != result:
                save_layout(result)
                st.success("새로운 레이아웃이 DB에 저장되었습니다!")
                st.rerun()

elif st.session_state["admin_current_view"] == "fms":
    c = cards_dict.get("fms", {})
    st.header(f"{c.get('icon', '')} {c.get('title', '')}")
    fms_status = get_fms_status()
    if fms_status:
        st.info(f"🟢 **현재 적용된 FMS 기준재고**\n- 최근 업데이트: {fms_status.get('last_updated', '알 수 없음')}\n- 등록된 품목 수: {fms_status.get('total_items', 0)}개\n\n새로운 엑셀 파일을 업로드하기 전까지 이 데이터가 유지됩니다.")
    else:
        st.warning("현재 등록된 FMS 기준재고가 없습니다. 엑셀 파일을 업로드해주세요.")
    
    st.write("FMS 시스템에서 다운로드한 엑셀 파일(품목명, 수량 컬럼 포함)을 업로드하여 기준 재고를 동기화합니다.")
    
    uploaded_fms = st.file_uploader("FMS 엑셀 업로드 (.xlsx, .csv)", type=["xlsx", "csv"])
    if uploaded_fms:
        try:
            if uploaded_fms.name.endswith(".csv"):
                df = pd.read_csv(uploaded_fms)
            else:
                df = pd.read_excel(uploaded_fms)
            
            col_map = _detect_fms_columns(df)
            
            if col_map.get("item_name") and col_map.get("qty"):
                detected_info = []
                label_map = {
                    "item_name": "물품명", "qty": "수량", "barcode": "바코드",
                    "category": "대분류", "donor": "기부자", "donated_date": "기부일자",
                    "expiry": "유통기한", "center": "접수센터", "unit_price": "장부단가",
                    "total_price": "장부금액", "storage": "보관장소"
                }
                for key, col_name in col_map.items():
                    detected_info.append(f"**{label_map.get(key, key)}** → `{col_name}`")
                
                st.success(f"✅ **{len(col_map)}개 컬럼 자동 감지 완료** (총 {len(df)}행)")
                with st.expander("🔍 감지된 컬럼 매핑 확인"):
                    st.markdown(" | ".join(detected_info))
                
                aggregated, preview = _aggregate_fms_data(df, col_map)
                
                if preview:
                    st.subheader(f"📋 합산 미리보기 ({len(preview)}개 품목)")
                    preview_df = pd.DataFrame(preview)
                    
                    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
                    thirty_days = (datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
                    
                    expiring_items = []
                    for p in preview:
                        exp = p.get("유통기한(최근)")
                        if exp and exp != "-" and exp <= thirty_days and exp >= today_str:
                            expiring_items.append(f"⚠️ **{p['물품명']}** (유통기한: {exp})")
                    
                    expired_items = []
                    for p in preview:
                        exp = p.get("유통기한(최근)")
                        if exp and exp != "-" and exp < today_str:
                            expired_items.append(f"🚨 **{p['물품명']}** (유통기한: {exp})")
                    
                    if expired_items:
                        st.error(f"**유통기한 경과 품목 {len(expired_items)}건:**\n\n" + "\n\n".join(expired_items[:10]))
                    if expiring_items:
                        st.warning(f"**유통기한 30일 이내 임박 품목 {len(expiring_items)}건:**\n\n" + "\n\n".join(expiring_items[:10]))
                    
                    def style_expiry(val):
                        if val and val != "-":
                            if val < today_str:
                                return "background-color: rgba(244, 67, 54, 0.2); color: #c62828; font-weight: bold;"
                            elif val <= thirty_days:
                                return "background-color: rgba(255, 193, 7, 0.2); color: #f57f17; font-weight: bold;"
                        return ""
                    
                    styled_preview = preview_df.style.map(style_expiry, subset=["유통기한(최근)"])
                    st.dataframe(styled_preview, use_container_width=True, hide_index=True)
                    
                    total_qty = sum(p["합산 수량"] for p in preview)
                    total_items = len(preview)
                    has_expiry = sum(1 for p in preview if p["유통기한(최근)"] != "-")
                    
                    col_s1, col_s2, col_s3 = st.columns(3)
                    col_s1.metric("📦 총 품목 수", f"{total_items}종")
                    col_s2.metric("📊 총 재고 수량", f"{total_qty:,}개")
                    col_s3.metric("📅 유통기한 있음", f"{has_expiry}종")
                    
                    if st.button("✅ 위 내용으로 FMS 재고 동기화", type="primary", use_container_width=True):
                        upload_fms_excel(df, col_map)
                        st.success(f"✅ FMS 전산 재고가 성공적으로 반영되었습니다! ({total_items}개 품목, 총 {total_qty:,}개)")
                        st.rerun()
                else:
                    st.warning("엑셀에서 유효한 데이터를 찾지 못했습니다. 물품명과 수량이 올바르게 입력되었는지 확인해 주세요.")
            else:
                missing = []
                if not col_map.get("item_name"):
                    missing.append("물품명(또는 품목명)")
                if not col_map.get("qty"):
                    missing.append("현 재고(또는 수량)")
                st.error(f"엑셀 파일에서 필수 컬럼을 찾지 못했습니다: {', '.join(missing)}\n\n감지된 컬럼: {list(df.columns)}")
        except Exception as e:
            st.error(f"엑셀을 읽는 중 오류가 발생했습니다: {e}\n(pandas 및 openpyxl 패키지가 필요합니다.)")

elif st.session_state["admin_current_view"] == "audit":
    c = cards_dict.get("audit", {})
    st.header(f"{c.get('icon', '')} {c.get('title', '')}")
    st.write("누가 언제 어떤 품목의 재고를 입력하고 수정했는지 확인할 수 있습니다.")
    
    logs = get_audit_logs()
    
    if logs:
        summary = get_inventory_summary()
        if summary:
            total_items = len(summary)
            match_count = sum(1 for s in summary if "일치" in s["상태"])
            short_count = sum(1 for s in summary if "부족" in s["상태"])
            over_count = sum(1 for s in summary if "초과" in s["상태"])
            match_rate = (match_count / total_items * 100) if total_items > 0 else 0
            
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            col_m1.metric("전체 품목", f"{total_items}건")
            col_m2.metric("🟢 일치", f"{match_count}건", f"{match_rate:.0f}%")
            col_m3.metric("🟡 초과", f"{over_count}건")
            col_m4.metric("🔴 부족", f"{short_count}건")
            
            if match_rate == 100:
                st.success("🎉 모든 품목이 FMS 기준재고와 완벽하게 일치합니다!")
            elif short_count > 0:
                st.error(f"⚠️ {short_count}개 품목이 기준재고보다 부족합니다. 재확인이 필요합니다.")
        
        st.markdown("---")
        
        log_df = pd.DataFrame(logs)
        if not log_df.empty:
            def format_timestamp(ts):
                try:
                    if isinstance(ts, str):
                        dt = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                    else:
                        dt = ts
                    return dt.strftime("%m월 %d일 %H:%M")
                except:
                    return str(ts)
            
            if "timestamp" in log_df.columns:
                log_df["timestamp"] = log_df["timestamp"].apply(format_timestamp)
            
            log_df = log_df.rename(columns={
                "timestamp": "입력 시간",
                "user_name": "작업자 이름",
                "user_id": "작업자 ID",
                "location": "구역/위치",
                "item_id": "품목명",
                "quantity": "입력 수량",
                "message": "비고(메시지)"
            })
            cols = ["입력 시간", "구역/위치", "품목명", "입력 수량", "작업자 이름", "작업자 ID", "비고(메시지)"]
            existing_cols = [c for c in cols if c in log_df.columns]
            st.dataframe(log_df[existing_cols], use_container_width=True, hide_index=True)
    else:
        st.info("아직 기록된 로그가 없습니다.")

elif st.session_state["admin_current_view"] == "portal":
    c = cards_dict.get("portal", {})
    st.header(f"{c.get('icon', '')} {c.get('title', '')}")
    st.write("첫 화면의 애니메이션, 환영 GIF, 안내 문구, 토글 색상, 선택지를 관리합니다.")
    
    portal_config = get_portal_config()
    
    with st.expander("🛠️ 메인 화면 항목 편집기", expanded=True):
        st.markdown("#### 🖼️ 환영 이미지 (GIF) 설정")
        uploaded_file = st.file_uploader("새로운 환영 이미지 파일 업로드 (선택)", type=["gif", "png", "jpg", "jpeg"])
        
        if uploaded_file is not None:
            import time
            os.makedirs("basic", exist_ok=True)
            file_ext = os.path.splitext(uploaded_file.name)[1]
            unique_filename = f"welcome_{int(time.time())}{file_ext}"
            file_path = os.path.join("basic", unique_filename)
            
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            new_gif_path = file_path
            st.success(f"이미지가 성공적으로 업로드되었습니다: {file_path}")
        else:
            new_gif_path = st.text_input("환영 이미지 경로 (위젯을 통해 업로드하면 자동 변경됩니다)", value=portal_config.get("gif_path", "basic/hello.gif"))
        
        new_subtitle = st.text_input("메인 안내 문구", value=portal_config.get("subtitle", "이용하실 서비스를 선택해주세요"))
        
        st.markdown("#### 🔠 폰트 및 크기 설정")
        new_subtitle_size = st.slider("메인 안내 문구 크기 (px)", min_value=14, max_value=40, value=portal_config.get("subtitle_size", 24))
        new_guide_text_size = st.slider("가이드 본문 크기 (px)", min_value=12, max_value=30, value=portal_config.get("guide_text_size", 18))
        new_slider_width_pc = st.slider("PC 선택창 가로 최대 길이 (px)", min_value=300, max_value=1200, value=portal_config.get("slider_width_pc", 600))
        new_slider_width_mobile_pct = st.slider("모바일 선택창 가로 비율 (%)", min_value=50, max_value=100, value=portal_config.get("slider_width_mobile_pct", 95))
        new_slider_font_size = st.slider("선택창 글씨 크기 (rem)", min_value=0.8, max_value=2.5, step=0.1, value=float(portal_config.get("slider_font_size", 1.2)))
        
        st.markdown("#### 📌 서비스 선택지 (이용자 분류)")
        
        if "admin_portal_options" not in st.session_state:
            st.session_state["admin_portal_options"] = portal_config.get("options", ["🛒 은평푸드 마켓 이용자", "🎁 그냥드림 이용자"])
        
        cols = st.columns([4, 1])
        with cols[0]:
            new_option_text = st.text_input("새로운 선택지 추가 (이름)", key="new_opt_input")
        with cols[1]:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("추가", key="add_opt_btn"):
                if new_option_text and new_option_text not in st.session_state["admin_portal_options"]:
                    st.session_state["admin_portal_options"].append(new_option_text)
                    st.rerun()
                    
        def update_option_name(idx, old_name):
            new_name = st.session_state[f"opt_edit_{idx}"]
            if new_name and new_name != old_name:
                st.session_state["admin_portal_options"][idx] = new_name
                state = _load_shared_state()
                guides = state.get("public_guides", {})
                if old_name in guides:
                    guides[new_name] = guides.pop(old_name)
                else:
                    guides[new_name] = []
                state["public_guides"] = guides
                _save_shared_state(state)
    
        for i, opt in enumerate(st.session_state["admin_portal_options"]):
            col_text, col_btn = st.columns([4, 1])
            with col_text:
                st.text_input(
                    f"선택지 {i+1} (수정 후 엔터)", 
                    value=opt, 
                    key=f"opt_edit_{i}", 
                    on_change=update_option_name,
                    args=(i, opt)
                )
            with col_btn:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("삭제", key=f"del_opt_{i}"):
                    st.session_state["admin_portal_options"].pop(i)
                    st.rerun()
    
        st.markdown("#### 👁️ 모바일/PC 환경 토글 미리보기")
        num_opts = len(st.session_state["admin_portal_options"]) if len(st.session_state["admin_portal_options"]) > 0 else 1
        pct = 100 / num_opts
        preview_css = f"""
        .preview-container {{
            background-color: transparent;
            padding: 20px 0;
            display: flex;
            justify-content: center;
            align-items: center;
        }}
        .preview-radiogroup {{
            display: flex;
            flex-direction: row;
            background: #f1f5f9;
            border-radius: 50px;
            padding: 5px;
            position: relative;
            width: {new_slider_width_pc}px;
            max-width: 100%;
            box-shadow: inset 0 2px 10px rgba(0,0,0,0.05);
            font-family: 'Pretendard', sans-serif;
        }}
        @media (max-width: 768px) {{
            .preview-radiogroup {{
                width: {new_slider_width_mobile_pct}vw;
            }}
        }}
        .preview-radiogroup::before {{
            content: "";
            position: absolute;
            top: 5px;
            left: 5px;
            width: calc({pct}% - {10/num_opts}px);
            height: calc(100% - 10px);
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            border-radius: 50px;
            box-shadow: 0 10px 25px rgba(0, 198, 255, 0.4);
        }}
        .preview-label {{
            flex: 1;
            text-align: center;
            padding: 20px 0;
            z-index: 2;
        }}
        .preview-label p {{
            font-weight: 700;
            font-size: {new_slider_font_size}rem;
            margin: 0;
            transition: all 0.4s;
        }}
        .preview-label.active p {{
            color: #ffffff;
            transform: scale(1.25);
            text-shadow: 0 2px 10px rgba(0,0,0,0.2);
        }}
        .preview-label.inactive p {{
            color: #7f8c8d;
        }}
        """
        labels_html = ""
        for idx, opt in enumerate(st.session_state["admin_portal_options"]):
            active_class = "active" if idx == 0 else "inactive"
            labels_html += f'<div class="preview-label {active_class}"><p>{opt}</p></div>'
            
        preview_html = f'<style>{preview_css}</style><div class="preview-container"><div class="preview-radiogroup">{labels_html}</div></div>'
        components.html(preview_html, height=150)
        
        st.warning("⚠️ **주의**: 위에서 조절한 미리보기 상태는 하단의 **[💾 포털 디자인 저장]** 버튼을 눌러야만 시스템에 최종 반영됩니다.")
    
        if st.button("💾 포털 디자인 저장", type="primary", use_container_width=True):
            new_config = {
                "gif_path": new_gif_path,
                "subtitle": new_subtitle,
                "subtitle_size": new_subtitle_size,
                "guide_text_size": new_guide_text_size,
                "slider_width_pc": new_slider_width_pc,
                "slider_width_mobile_pct": new_slider_width_mobile_pct,
                "slider_font_size": new_slider_font_size,
                "options": st.session_state["admin_portal_options"]
            }
            update_portal_config(new_config)
            st.success("디자인 설정이 저장되었습니다.")

elif st.session_state["admin_current_view"] == "sitemap":
    c = cards_dict.get("sitemap", {})
    st.header(f"{c.get('icon', '')} {c.get('title', '')}")
    st.write("사용자들이 사이트 내의 전체 서비스를 이해할 수 있도록 제공되는 사이트맵 설명을 관리합니다.")
    
    sitemap_config = get_sitemap_config()
    
    with st.expander("🛠️ 사이트맵 설명 수정", expanded=True):
        new_sitemap_desc = st.text_area("사이트맵 전체 개요", value=sitemap_config.get("description", ""))
        
        st.markdown("#### 📄 각 페이지별 설명")
        
        if "admin_sitemap_pages" not in st.session_state:
            st.session_state["admin_sitemap_pages"] = sitemap_config.get("pages", [])
            
        cols = st.columns([2, 3, 1])
        with cols[0]:
            new_page_name = st.text_input("새 페이지 이름", key="smap_new_name")
        with cols[1]:
            new_page_purpose = st.text_input("페이지 이용 목적(설명)", key="smap_new_purpose")
        with cols[2]:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("페이지 추가", key="smap_add_btn"):
                if new_page_name and new_page_purpose:
                    st.session_state["admin_sitemap_pages"].append({"name": new_page_name, "purpose": new_page_purpose})
                    st.rerun()
    
        for i, page in enumerate(st.session_state["admin_sitemap_pages"]):
            col_name, col_purpose, col_del = st.columns([2, 3, 1])
            with col_name:
                updated_name = st.text_input(f"페이지 {i+1} 이름", value=page["name"], key=f"smap_name_{i}")
            with col_purpose:
                updated_purpose = st.text_input(f"페이지 {i+1} 설명", value=page["purpose"], key=f"smap_purpose_{i}")
            with col_del:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("삭제", key=f"smap_del_{i}"):
                    st.session_state["admin_sitemap_pages"].pop(i)
                    st.rerun()
            
            if updated_name != page["name"] or updated_purpose != page["purpose"]:
                st.session_state["admin_sitemap_pages"][i] = {"name": updated_name, "purpose": updated_purpose}
    
        if st.button("💾 사이트맵 저장", type="primary", use_container_width=True):
            new_smap = {
                "description": new_sitemap_desc,
                "pages": st.session_state["admin_sitemap_pages"]
            }
            update_sitemap_config(new_smap)
            st.success("사이트맵 설정이 저장되었습니다.")

elif st.session_state["admin_current_view"] == "public_guide":
    c = cards_dict.get("public_guide", {})
    st.header(f"{c.get('icon', '')} {c.get('title', '')}")
    st.write("QR 코드 등을 통해 로그인 없이 접속하는 일반 이용자들의 단계별 안내 화면을 구성합니다.")
    
    guides = get_public_guides()
    portal_config = get_portal_config()
    options = portal_config.get("options", [])
    
    if not options:
        st.warning("먼저 포털 디자인 에디터에서 선택지를 하나 이상 추가해주세요.")
    else:
        tabs = st.tabs(options)
        
        def render_guide_editor(guide_list, key_prefix):
            new_list = []
            to_delete = None
            for i, step in enumerate(guide_list):
                with st.expander(f"{i+1}단계: {step.get('title', '')}"):
                    t = st.text_input("제목", value=step.get("title", ""), key=f"{key_prefix}_t_{i}")
                    st.write("**설명 (텍스트)** - 텍스트를 마우스로 드래그하여 글자색이나 크기를 바꿀 수 있습니다.")
                    try:
                        from streamlit_quill import st_quill
                        c = st_quill(value=step.get("content", ""), key=f"{key_prefix}_c_{i}", html=True)
                    except ImportError:
                        st.warning("직관적인 에디터 패키지가 설치되지 않았습니다. 백그라운드 설치를 기다려주세요.")
                        c = st.text_area("설명 (텍스트)", value=step.get("content", ""), key=f"{key_prefix}_c_{i}", height=150)
                    m = st.text_input("미디어 URL (이미지/유튜브 등 링크)", value=step.get("media_url", ""), key=f"{key_prefix}_m_{i}")
                    
                    if st.button("🗑️ 이 단계 삭제", key=f"btn_del_{key_prefix}_{i}"):
                        to_delete = i
                    else:
                        new_list.append({"title": t, "content": c, "media_url": m})
            return new_list, to_delete
    
        all_updated_guides = {}
        category_styles = get_category_styles()
        uploaded_fonts = get_custom_fonts()
        available_fonts = ["Pretendard (기본)"] + [os.path.basename(f) for f in uploaded_fonts]
        
        for i, opt in enumerate(options):
            with tabs[i]:
                current_style = category_styles.get(opt, {
                    "font_family": "Pretendard (기본)",
                    "title_color": "#2c3e50",
                    "title_size": 24,
                    "content_color": "#2c3e50",
                    "content_size": 18
                })
                
                with st.expander(f"🎨 [{opt}] 전용 텍스트 스타일 설정"):
                    font_idx = 0
                    if current_style["font_family"] in available_fonts:
                        font_idx = available_fonts.index(current_style["font_family"])
                        
                    sel_font = st.selectbox("적용할 폰트", available_fonts, index=font_idx, key=f"f_font_{i}")
                    col_st1, col_st2 = st.columns(2)
                    with col_st1:
                        sel_t_col = st.color_picker("제목 색상", current_style["title_color"], key=f"f_tcol_{i}")
                        sel_t_siz = st.slider("제목 크기 (px)", 14, 40, current_style["title_size"], key=f"f_tsiz_{i}")
                    with col_st2:
                        sel_c_col = st.color_picker("본문 색상", current_style["content_color"], key=f"f_ccol_{i}")
                        sel_c_siz = st.slider("본문 크기 (px)", 12, 30, current_style["content_size"], key=f"f_csiz_{i}")
                        
                    if st.button("스타일 저장", key=f"btn_save_style_{i}"):
                        category_styles[opt] = {
                            "font_family": sel_font,
                            "title_color": sel_t_col,
                            "title_size": sel_t_siz,
                            "content_color": sel_c_col,
                            "content_size": sel_c_siz
                        }
                        update_category_styles(category_styles)
                        st.success("스타일이 저장되었습니다. 메인 앱에 반영됩니다.")
                        
                st.markdown("<br>", unsafe_allow_html=True)
                
                current_guides = guides.get(opt, [])
                updated_guides, del_idx = render_guide_editor(current_guides, f"guide_{i}")
                all_updated_guides[opt] = updated_guides
                
                if del_idx is not None:
                    guides[opt] = updated_guides
                    state = _load_shared_state()
                    state["public_guides"] = guides
                    _save_shared_state(state)
                    st.rerun()
                    
                if st.button(f"➕ {opt} 새로운 단계 추가", key=f"btn_add_{i}"):
                    updated_guides.append({"title": "새 단계", "content": "", "media_url": ""})
                    guides[opt] = updated_guides
                    state = _load_shared_state()
                    state["public_guides"] = guides
                    _save_shared_state(state)
                    st.rerun()
    
        if st.button("💾 퍼블릭 가이드 전체 변경사항 저장", type="primary", use_container_width=True):
            state = _load_shared_state()
            state["public_guides"] = all_updated_guides
            _save_shared_state(state)
            st.success("모든 안내 콘텐츠가 저장되었습니다.")

elif st.session_state["admin_current_view"] == "fonts":
    c = cards_dict.get("fonts", {})
    st.header(f"{c.get('icon', '')} {c.get('title', '')}")
    st.write("로컬에 있는 무료 폰트 파일(.ttf, .otf, .woff 등)을 서버에 업로드하여 가이드 화면에 적용할 수 있습니다.")
    font_file = st.file_uploader("새 폰트 파일 업로드", type=["ttf", "otf", "woff", "woff2"])
    if font_file:
        os.makedirs("basic/fonts", exist_ok=True)
        safe_name = font_file.name.replace(" ", "_")
        fpath = os.path.join("basic/fonts", safe_name)
        with open(fpath, "wb") as f:
            f.write(font_file.getbuffer())
        st.success(f"폰트 파일 업로드 성공: {safe_name}")
        st.rerun()
        
    uploaded_fonts = get_custom_fonts()
    if uploaded_fonts:
        st.markdown("---")
        st.markdown("**현재 업로드된 폰트 목록**")
        for uf in uploaded_fonts:
            col_f1, col_f2 = st.columns([4, 1])
            col_f1.code(os.path.basename(uf))
            if col_f2.button("삭제", key=f"del_font_{uf}"):
                os.remove(uf)
                st.rerun()

elif st.session_state["admin_current_view"] == "geodream_theme":
    c = cards_dict.get("geodream_theme", {})
    st.header(f"{c.get('icon', '')} {c.get('title', '')}")
    st.markdown("그냥드림 지도의 반응형 UI 색상과 폰트를 자유롭게 커스터마이징하세요.")
    
    theme = get_geodream_theme()
    with st.expander("테마 설정 열기", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            bg_color = st.color_picker("배경 색상 (미니멀 컨테이너)", value=theme.get("bg_color", "#D7E4D3"))
            tooltip_bg = st.text_input("툴팁 배경 색상 (rgba 권장)", value=theme.get("tooltip_bg", "rgba(30, 42, 33, 0.95)"))
            tooltip_text = st.color_picker("툴팁 글씨 색상", value=theme.get("tooltip_text", "#F0E6D2"))
        with col2:
            highlight_color = st.color_picker("강조 포인트 색상 (글로우 효과)", value=theme.get("highlight_color", "#E6D8A7"))
            font_family = st.selectbox("폰트 스타일", 
                                       options=["'Noto Sans KR', sans-serif", "'Pretendard', sans-serif", "'Gowun Dodum', sans-serif"], 
                                       index=0 if "'Noto Sans KR'" in theme.get("font_family", "") else 1)
            
        if st.button("테마 저장 및 적용", type="primary", use_container_width=True):
            new_theme = {
                "bg_color": bg_color,
                "tooltip_bg": tooltip_bg,
                "tooltip_text": tooltip_text,
                "highlight_color": highlight_color,
                "font_family": font_family
            }
            update_geodream_theme(new_theme)
            st.success("데이터맵 테마가 성공적으로 업데이트되었습니다!")
            st.rerun()
