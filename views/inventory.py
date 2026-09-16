import streamlit as st
import datetime
import pandas as pd
from db import get_inventory, update_inventory, get_zones, get_audit_logs, get_inventory_summary

st.title("📱 모바일 재고 실사")

# 상태 초기화
if "selected_zone" not in st.session_state:
    st.session_state.selected_zone = None

# DB에서 관리자가 설정한 구역 목록 불러오기
zones_dict = get_zones()

st.subheader("🗺️ 인터랙티브 평면도 선택")
st.write("아래 도면에서 실사할 위치(박스)를 직접 터치해 주세요.")

from db import get_current_layout
from components_loader import map_viewer_component

full_layout = get_current_layout()

selected_rack_id = None
selected_rack_name = None
full_location = "선택 안됨"

if "zone_1" in full_layout:
    zone_keys = list(full_layout.keys())
    zone_names = [full_layout[k].get("name", k) for k in zone_keys]
    tabs = st.tabs(zone_names)
    
    for i, tab in enumerate(tabs):
        with tab:
            z_key = zone_keys[i]
            current_zone_data = full_layout[z_key]
            
            result = map_viewer_component(layout_data=current_zone_data, key=f"map_viewer_ui_{z_key}")
            
            if result is not None and "selected_rack_id" in result:
                selected_rack_id = result["selected_rack_id"]
                for r in current_zone_data.get("racks", []):
                    if r["id"] == selected_rack_id:
                        selected_rack_name = r["name"]
                        full_location = f"{current_zone_data['name']} > {selected_rack_name}"
                        break
else:
    result = map_viewer_component(layout_data=full_layout, key="map_viewer_ui_legacy")
    if result is not None and "selected_rack_id" in result:
        selected_rack_id = result["selected_rack_id"]
        for r in full_layout.get("racks", []):
            if r["id"] == selected_rack_id:
                selected_rack_name = r["name"]
                full_location = f"{r.get('zone', 'Zone')} > {selected_rack_name}"
                break

st.divider()

if selected_rack_id:
    st.markdown(f"### 🎯 현재 위치: `{full_location}`")
    
    # DB에서 FMS 데이터 불러오기 (풍부한 메타데이터 포함)
    fms_data = get_inventory()
    fms_dict = {item["item"]: item["fms_qty"] for item in fms_data} if fms_data else {}
    
    # 바코드 → 물품명 역방향 매핑 구축
    barcode_to_item = {}
    fms_meta = {}  # {물품명: {category, barcodes, ...}}
    if fms_data:
        for item in fms_data:
            item_name = item["item"]
            fms_meta[item_name] = item
            for bc in item.get("barcodes", []):
                barcode_to_item[bc] = item_name
    
    if not fms_data:
        st.warning("시스템에 엑셀(FMS) 기준 재고가 없어 모든 입력이 신규 등록으로 처리됩니다.")

    # 동의어 사전
    synonym_dict = {
        "사과": "프리미엄 꿀사과 (10kg)",
        "생수": "생수 2L (6개입 묶음)",
        "물": "생수 2L (6개입 묶음)",
        "라면": "신라면 (40봉 박스)"
    }

    search_term = st.text_input("🔍 품목명 또는 바코드 검색", placeholder="예: 선풍기, 8809301470893")
    selected_item = None

    if search_term:
        # 0. 바코드 매칭 검사 (숫자만으로 구성된 경우)
        search_clean = search_term.strip()
        if search_clean in barcode_to_item:
            selected_item = barcode_to_item[search_clean]
            cat_info = fms_meta.get(selected_item, {}).get("category", "")
            cat_label = f" [{cat_info}]" if cat_info else ""
            st.success(f"📊 바코드 매칭: `{search_clean}` ➔ **{selected_item}**{cat_label}")
        
        # 1. 동의어 매칭 검사
        if not selected_item:
            for key, official_name in synonym_dict.items():
                if key in search_term:
                    selected_item = official_name
                    st.success(f"💡 빠른 매칭: '{search_term}' ➔ **{official_name}**")
                    break
                
        # 2. 부분 일치 검색 (물품명)
        if not selected_item:
            matches = [k for k in fms_dict.keys() if search_term in k]
            if matches:
                selected_item = st.selectbox("검색된 전산 품목 선택", matches)
            else:
                st.warning(f"전산 재고에 없어 신규 수동 등록으로 진행합니다.")
                selected_item = search_term

    if selected_item:
        st.markdown(f"### 👉 물품: `{selected_item}`")
        
        fms_qty = fms_dict.get(selected_item, 0)
        if selected_item in fms_dict:
            st.write(f"📊 전산 기준 재고(FMS): **{fms_qty}개**")
        else:
            st.write("📊 전산 기준 재고: **없음 (신규)**")
            
        qty_input = st.number_input("🔢 확인된 실제 수량", min_value=0, value=fms_qty, step=1, key=f"qty_{selected_item}")
        
        diff = qty_input - fms_qty
        if selected_item in fms_dict:
            if diff == 0:
                st.success("🟢 전산과 완벽하게 일치합니다.")
                log_msg = f"일치 (FMS: {fms_qty})"
            elif diff > 0:
                st.warning(f"🟡 전산보다 {diff}개 더 많습니다.")
                log_msg = f"초과 (FMS: {fms_qty}, 오차: +{diff})"
            else:
                st.error(f"🔴 전산보다 {abs(diff)}개 부족합니다.")
                log_msg = f"부족 (FMS: {fms_qty}, 오차: {diff})"
        else:
            st.info("신규 품목으로 기록됩니다.")
            log_msg = "신규 수동 추가"
            
        if st.button("💾 이 물품 실사 저장", type="primary", use_container_width=True):
            update_inventory(selected_item, qty_input, full_location, log_msg)
            st.success(f"🎉 [{selected_item}] {qty_input}개가 {full_location}에 기록되었습니다!")
else:
    st.info("👆 위 평면도를 보고 실사할 박스(구역)를 직접 터치해 주세요.")

# ========================================
# 📊 실사 이력 및 재고 현황 대시보드
# ========================================
st.divider()
st.header("📊 실사 이력 및 재고 현황")

current_user_id = st.session_state.get("user_id", "")
current_user_name = st.session_state.get("name", "")

tab_my, tab_all, tab_summary = st.tabs(["📋 내 입력 이력", "👥 전체 입력 현황", "📊 전체 재고 합산 & FMS 대조"])

# --- 탭 1: 내 입력 이력 ---
with tab_my:
    logs = get_audit_logs()
    my_logs = [log for log in logs if log.get("user_id") == current_user_id]
    
    if my_logs:
        st.markdown(f"**{current_user_name}**님이 입력한 실사 기록 ({len(my_logs)}건)")
        
        my_df = pd.DataFrame(my_logs)
        my_df = my_df.rename(columns={
            "timestamp": "입력 시간",
            "location": "위치",
            "item_id": "품목명",
            "quantity": "입력 수량",
            "message": "비고"
        })
        display_cols = ["입력 시간", "위치", "품목명", "입력 수량", "비고"]
        existing_cols = [c for c in display_cols if c in my_df.columns]
        
        st.dataframe(
            my_df[existing_cols],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("아직 입력한 실사 기록이 없습니다. 위에서 품목을 검색하고 수량을 저장해 보세요.")

# --- 탭 2: 전체 입력 현황 (다른 사람 비교) ---
with tab_all:
    logs = get_audit_logs()
    
    if logs:
        st.markdown(f"전체 실사 기록 ({len(logs)}건) — 🟦 파란 행이 내 기록입니다.")
        
        all_df = pd.DataFrame(logs)
        all_df = all_df.rename(columns={
            "timestamp": "입력 시간",
            "user_name": "작업자",
            "user_id": "작업자 ID",
            "location": "위치",
            "item_id": "품목명",
            "quantity": "입력 수량",
            "message": "비고"
        })
        display_cols = ["입력 시간", "작업자", "위치", "품목명", "입력 수량", "비고"]
        existing_cols = [c for c in display_cols if c in all_df.columns]
        
        # 본인 행 하이라이트를 위한 스타일 함수
        def highlight_my_rows(row):
            if "작업자 ID" in all_df.columns:
                is_mine = row.name in all_df.index[all_df["작업자 ID"] == current_user_id]
            else:
                is_mine = False
            if is_mine:
                return ["background-color: rgba(33, 150, 243, 0.15); font-weight: bold;"] * len(row)
            return [""] * len(row)
        
        styled_df = all_df[existing_cols].style.apply(highlight_my_rows, axis=1)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        # 사용자별 입력 건수 요약
        if "작업자" in all_df.columns:
            st.markdown("---")
            st.markdown("##### 👤 작업자별 입력 건수")
            user_counts = all_df["작업자"].value_counts().reset_index()
            user_counts.columns = ["작업자", "입력 건수"]
            st.dataframe(user_counts, use_container_width=True, hide_index=True)
    else:
        st.info("아직 기록된 실사 데이터가 없습니다.")

# --- 탭 3: 전체 재고 합산 & FMS 대조 ---
with tab_summary:
    summary = get_inventory_summary()
    
    if summary:
        # FMS 메타데이터에서 대분류 가져오기
        fms_data_for_summary = get_inventory()
        fms_category_map = {}
        if fms_data_for_summary:
            for item in fms_data_for_summary:
                fms_category_map[item["item"]] = item.get("category", "")
        
        # summary에 대분류 추가
        for s in summary:
            s["대분류"] = fms_category_map.get(s["품목명"], "")
        
        # 상단 메트릭 카드
        total_items = len(summary)
        match_count = sum(1 for s in summary if "일치" in s["상태"])
        over_count = sum(1 for s in summary if "초과" in s["상태"])
        short_count = sum(1 for s in summary if "부족" in s["상태"])
        new_count = sum(1 for s in summary if "신규" in s["상태"])
        
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
        elif over_count > 0:
            st.warning(f"📦 {over_count}개 품목이 기준재고보다 많습니다. 미등록 입고가 있을 수 있습니다.")
        
        st.markdown("---")
        
        # 대조 테이블 (대분류 포함)
        summary_df = pd.DataFrame(summary)
        display_cols = ["대분류", "품목명", "실사 합산", "FMS 기준", "오차", "상태", "입력자 수"]
        existing_display = [c for c in display_cols if c in summary_df.columns]
        display_summary = summary_df[existing_display].copy()
        
        def color_status(val):
            if "일치" in str(val):
                return "background-color: rgba(76, 175, 80, 0.2); color: #2e7d32;"
            elif "초과" in str(val):
                return "background-color: rgba(255, 193, 7, 0.2); color: #f57f17;"
            elif "부족" in str(val):
                return "background-color: rgba(244, 67, 54, 0.2); color: #c62828;"
            elif "신규" in str(val):
                return "background-color: rgba(33, 150, 243, 0.2); color: #1565c0;"
            return ""
        
        def color_diff(val):
            try:
                v = int(val)
                if v > 0:
                    return "color: #f57f17; font-weight: bold;"
                elif v < 0:
                    return "color: #c62828; font-weight: bold;"
                else:
                    return "color: #2e7d32;"
            except:
                return ""
        
        style_subsets = {}
        if "상태" in display_summary.columns:
            style_subsets["상태"] = color_status
        if "오차" in display_summary.columns:
            style_subsets["오차"] = color_diff
        
        styled_summary = display_summary.style
        for col_name, func in style_subsets.items():
            styled_summary = styled_summary.map(func, subset=[col_name])
        
        st.dataframe(styled_summary, use_container_width=True, hide_index=True)
        
        # 품목별 입력자 상세 (확장 가능)
        st.markdown("---")
        st.markdown("##### 🔍 품목별 입력자 상세 보기")
        for item in summary:
            if item["입력자 수"] > 0:
                with st.expander(f"{item['상태']} {item['품목명']} — 합산: {item['실사 합산']}개 (입력자 {item['입력자 수']}명)"):
                    detail_data = []
                    for c in item["입력자 상세"]:
                        detail_data.append({
                            "작업자": c["user_name"],
                            "입력 수량": c["quantity"]
                        })
                    detail_df = pd.DataFrame(detail_data)
                    st.dataframe(detail_df, use_container_width=True, hide_index=True)
    else:
        st.info("아직 실사 데이터가 없거나 FMS 기준재고가 등록되지 않았습니다.")
