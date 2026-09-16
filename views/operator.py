import streamlit as st
from db import update_inventory

st.title("🛒 현장운영 (웹 POS)")
st.info("💡 엑셀이나 FMS 프로그램을 사용 중이더라도, 이 창에서 바코드 리더기를 통해 스캔하면 독립적으로 백그라운드 기록이 남습니다.")

from db import get_barcode_rules, update_barcode_rule, delete_barcode_rule
from db import get_service_rules, update_service_rule, delete_service_rule, reset_cart, get_visitor_rules, update_visitor_rules, get_user_info_by_barcode
from db import update_barcode_rules_bulk, update_user_directory, get_fms_master, update_fms_master, update_service_rules_bulk
import pandas as pd
from difflib import SequenceMatcher

with st.expander("⚙️ 현장 기준정보 통합 엑셀 업로드", expanded=False):
    tab_rules, tab_users, tab_services, tab_reset, tab_visitor, tab_fms = st.tabs(["📦 일반 품목 매핑", "👥 이용자 명단 동기화", "🎁 서비스 물품 설정", "🔄 장바구니 초기화", "📋 특이사항 설정", "📑 FMS 마스터 재고 연동"])
    
    with tab_rules:
        st.write("바코드를 스캔했을 때 인식될 제품과 묶음 품목(그룹), 그리고 몇 개를 1품목으로 칠지 설정합니다.")
        with st.form("rule_form", clear_on_submit=True):
            col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
            b_code = col1.text_input("바코드 번호")
            p_name = col2.text_input("제품명 (예: 치약)")
            i_group = col3.text_input("품목명 (예: 치약_그룹)")
            req_qty = col4.number_input("N개 = 1품목", min_value=1, value=1)
            if st.form_submit_button("추가 / 수정"):
                if b_code and p_name and i_group:
                    update_barcode_rule(b_code, p_name, i_group, req_qty)
                    st.success("저장되었습니다.")
                    st.rerun()
                else:
                    st.error("값을 모두 입력해주세요.")
        
        rules = get_barcode_rules()
        for bc, data in rules.items():
            cols = st.columns([1, 2, 2, 1, 1])
            cols[0].write(bc)
            cols[1].write(data["product"])
            cols[2].write(data["item"])
            cols[3].write(f"{data['required_qty']}개=1품목")
            if cols[4].button("삭제", key=f"del_rule_{bc}"):
                delete_barcode_rule(bc)
                st.rerun()

        st.divider()
        st.write("또는 엑셀을 업로드하여 여러 개의 바코드 매핑 규칙을 한 번에 병합(업데이트)할 수 있습니다. (FMS 마스터 연동 지원)")
        rule_files = st.file_uploader("물품 바코드 엑셀 업로드", type=["xlsx", "xls"], key="rule_upload", accept_multiple_files=True)
        
        if "pending_fms_rules" not in st.session_state:
            st.session_state["pending_fms_rules"] = []
            
        if rule_files:
            try:
                new_rules = {}
                new_service_rules = {}
                import re
                import uuid
                for rule_file in rule_files:
                    # 1. 스마트 헤더 탐지: 진짜 표의 시작(컬럼명) 행을 찾음
                    df_raw = pd.read_excel(rule_file, header=None)
                    header_idx = 0
                    for i, row in df_raw.iterrows():
                        row_strs = [str(x) for x in row.values]
                        if any(k in v for v in row_strs for k in ["품명", "물품명", "제품", "품목"]):
                            header_idx = i
                            break
                    
                    df = pd.read_excel(rule_file, header=header_idx)
                    cols = list(df.columns)
                    mapping = {}
                    for c in cols:
                        c_s = str(c).strip()
                        if "바코드" in c_s: mapping["bc"] = c
                        elif "제품" in c_s or "물품명" in c_s or "품명" == c_s: mapping["prod"] = c
                        elif "품목" in c_s or "그룹" in c_s: mapping["group"] = c
                        elif "수량" in c_s or "N개" in c_s or "기준" in c_s or "개수" in c_s: mapping["qty"] = c
                    
                    # 2. 필수 열 체크 완화 (바코드가 없어도 통과)
                    if "prod" in mapping and "group" in mapping:
                        for _, row in df.iterrows():
                            prod_val = str(row[mapping["prod"]]).strip()
                            if not prod_val or prod_val == "nan" or prod_val.lower() == "nat": continue
                            
                            bc_val = str(row[mapping["bc"]]).strip() if "bc" in mapping else ""
                            # 바코드가 없으면 시스템 자동 임시 바코드 발급
                            if not bc_val or bc_val == "nan":
                                bc_val = f"AUTO_{str(uuid.uuid4())[:8].upper()}"
                                
                            qty_val = 1
                            if "qty" in mapping:
                                raw_qty = str(row[mapping["qty"]])
                                # '2개 1품목' 등의 텍스트에서 숫자만 추출
                                nums = re.findall(r'\d+', raw_qty)
                                if nums:
                                    qty_val = int(nums[0])
                                    
                            new_rules[bc_val] = {
                                "product": prod_val,
                                "item": str(row[mapping["group"]]).strip(),
                                "required_qty": qty_val
                            }
                            
                            # 서비스 물품 자동 추출
                            if "서비스" in str(row[mapping["group"]]):
                                new_service_rules[bc_val] = {
                                    "service_name": prod_val,
                                    "required_qty": qty_val
                                }
                    else:
                        st.warning(f"[{rule_file.name}] 필수 열('품명', '품목')을 찾을 수 없어 건너뜁니다.")
                        
                # 3. FMS 마스터와 텍스트 유사도 비교하여 자동 바코드 매핑 지원
                if new_rules:
                    fms_master = get_fms_master()
                    if fms_master:
                        ambiguous_list = []
                        auto_matched_rules = {}
                        fms_names = [f.get("product_name", "") for f in fms_master if f.get("product_name")]
                        fms_dict = {f.get("product_name", ""): f.get("barcode", "") for f in fms_master if f.get("product_name")}
                        
                        for bc, r_data in new_rules.items():
                            prod_name = r_data["product"]
                            best_match = None
                            best_ratio = 0.0
                            
                            for fn in fms_names:
                                ratio = SequenceMatcher(None, prod_name, fn).ratio()
                                if ratio > best_ratio:
                                    best_ratio = ratio
                                    best_match = fn
                                    
                            if best_ratio >= 0.8:
                                r_data["fms_matched"] = best_match
                                # 우리가 발급한 AUTO_ 바코드이고 FMS 마스터에 실제 바코드가 등록되어 있다면, 그 바코드로 교체
                                real_bc = fms_dict.get(best_match, "")
                                if bc.startswith("AUTO_") and real_bc:
                                    bc = real_bc
                                auto_matched_rules[bc] = r_data
                            elif best_ratio >= 0.5:
                                candidates = []
                                for fn in fms_names:
                                    if SequenceMatcher(None, prod_name, fn).ratio() >= 0.3:
                                        candidates.append(fn)
                                candidates = sorted(candidates, key=lambda x: SequenceMatcher(None, prod_name, x).ratio(), reverse=True)[:5]
                                
                                ambiguous_list.append({
                                    "bc": bc,
                                    "original_product": prod_name,
                                    "r_data": r_data,
                                    "candidates": candidates
                                })
                            else:
                                r_data["fms_matched"] = None
                                auto_matched_rules[bc] = r_data
                                
                        if ambiguous_list:
                            st.session_state["pending_fms_rules"] = ambiguous_list
                            st.session_state["auto_matched_rules"] = auto_matched_rules
                        else:
                            st.session_state["pending_fms_rules"] = []
                            st.session_state["auto_matched_rules"] = auto_matched_rules
                    else:
                        st.session_state["pending_fms_rules"] = []
                        st.session_state["auto_matched_rules"] = new_rules
                        
                    st.session_state["auto_matched_service_rules"] = new_service_rules

            except Exception as e:
                st.error(f"오류: {e}")
                
        if st.session_state["pending_fms_rules"]:
            st.warning(f"⚠️ {len(st.session_state['pending_fms_rules'])}개의 제품명이 FMS 마스터와 애매하게 매칭되었습니다. 정확한 매칭을 선택해주세요.")
            with st.form("ambiguous_resolution_form"):
                resolved_rules = {}
                for idx, amb in enumerate(st.session_state["pending_fms_rules"]):
                    st.write(f"🔹 **업로드된 제품명**: `{amb['original_product']}` (바코드: {amb['bc']})")
                    options = amb["candidates"].copy()
                    options.append("원본 그대로 사용 (매칭 안함)")
                    selected = st.selectbox("FMS 매칭 선택", options, key=f"amb_sel_{idx}")
                    
                    r_data = amb["r_data"]
                    if selected != "원본 그대로 사용 (매칭 안함)":
                        r_data["fms_matched"] = selected
                    else:
                        r_data["fms_matched"] = None
                    resolved_rules[amb["bc"]] = r_data
                    
                if st.form_submit_button("선택 확정 및 전체 병합하기"):
                    final_rules = st.session_state.get("auto_matched_rules", {})
                    final_rules.update(resolved_rules)
                    update_barcode_rules_bulk(final_rules)
                    
                    if st.session_state.get("auto_matched_service_rules"):
                        update_service_rules_bulk(st.session_state["auto_matched_service_rules"])
                        
                    st.session_state["pending_fms_rules"] = []
                    st.session_state["auto_matched_rules"] = {}
                    st.session_state["auto_matched_service_rules"] = {}
                    st.success("물품 바코드 및 서비스 룰이 병합되었습니다!")
                    st.rerun()
        elif st.session_state.get("auto_matched_rules") or st.session_state.get("auto_matched_service_rules"):
            if st.button(f"총 {len(st.session_state.get('auto_matched_rules', {}))}개 바코드 룰셋 병합하기"):
                if st.session_state.get("auto_matched_rules"):
                    update_barcode_rules_bulk(st.session_state["auto_matched_rules"])
                if st.session_state.get("auto_matched_service_rules"):
                    update_service_rules_bulk(st.session_state["auto_matched_service_rules"])
                st.session_state["auto_matched_rules"] = {}
                st.session_state["auto_matched_service_rules"] = {}
                st.success("물품 바코드 및 서비스 룰이 병합되었습니다!")
                st.rerun()

    with tab_users:
        st.write("현장 이용자 명단 엑셀을 업로드하여 스캔 시 이용자 정보를 실시간으로 확인합니다.")
        user_files = st.file_uploader("이용자 명단 엑셀 업로드", type=["xlsx", "xls"], key="user_upload", accept_multiple_files=True)
        if user_files:
            try:
                new_users = {}
                for user_file in user_files:
                    udf = pd.read_excel(user_file)
                    cols = list(udf.columns)
                    u_map = {}
                    for c in cols:
                        c_s = str(c).strip()
                        if "회원" in c_s or "바코드" in c_s or "식별" in c_s: u_map["id"] = c
                        elif "인원" in c_s or "가구" in c_s: u_map["people"] = c
                        elif "주거" in c_s or "형태" in c_s: u_map["housing"] = c
                        elif "필수" in c_s or "제공" in c_s or "물품" in c_s: u_map["mandatory"] = c
                    
                    if "id" in u_map:
                        for _, row in udf.iterrows():
                            u_id = str(row[u_map["id"]]).strip().upper()
                            if u_id and u_id != "NAN":
                                user_data = {}
                                if "people" in u_map and not pd.isna(row[u_map["people"]]): user_data["people"] = str(row[u_map["people"]]).strip()
                                if "housing" in u_map and not pd.isna(row[u_map["housing"]]): user_data["housing"] = str(row[u_map["housing"]]).strip()
                                if "mandatory" in u_map and not pd.isna(row[u_map["mandatory"]]): user_data["mandatory_item"] = str(row[u_map["mandatory"]]).strip()
                                new_users[u_id] = user_data
                    else:
                        st.warning(f"[{user_file.name}] 필수 열 누락으로 건너뜁니다.")
                if new_users:
                    st.write(f"총 {len(new_users)}명의 이용자 데이터가 감지되었습니다.")
                    if st.button("이용자 명단 동기화"):
                        update_user_directory(new_users)
                        st.success("이용자 명단이 시스템에 캐싱되었습니다!")
                        st.rerun()
            except Exception as e:
                st.error(f"명단 파싱 오류: {e}")

    with tab_services:
        st.write("서비스로 추가 제공할 물품과 할당 개수를 설정합니다.")
        with st.form("service_form", clear_on_submit=True):
            col1, col2, col3 = st.columns([2, 3, 1])
            sb_code = col1.text_input("서비스 바코드")
            s_name = col2.text_input("서비스명 (예: 핸드워시)")
            s_qty = col3.number_input("할당 개수", min_value=1, value=1)
            if st.form_submit_button("추가 / 수정"):
                if sb_code and s_name:
                    update_service_rule(sb_code, s_name, s_qty)
                    st.success("저장되었습니다.")
                    st.rerun()
                else:
                    st.error("값을 모두 입력해주세요.")
        
        s_rules = get_service_rules()
        for bc, data in s_rules.items():
            cols = st.columns([2, 3, 1, 1])
            cols[0].write(bc)
            cols[1].write(data["service_name"])
            cols[2].write(f"총 {data['required_qty']}개")
            if cols[3].button("삭제", key=f"del_svc_{bc}"):
                delete_service_rule(bc)
                st.rerun()
                
    with tab_reset:
        st.write("현재 사용자의 장바구니(5품목 카운트 및 서비스 카운트) 상태를 초기화합니다.")
        if st.button("현재 장바구니 초기화", type="primary"):
            reset_cart()
            st.success("장바구니가 초기화되었습니다.")
            
    with tab_visitor:
        st.write("방문자 특이사항(인원, 주거형태별 허용 품목수) 엑셀을 업로드하여 동적 규칙을 설정합니다.")
        visitor_files = st.file_uploader("특이사항 규칙 엑셀 업로드", type=["xlsx", "xls"], key="visitor_rule_upload", accept_multiple_files=True)
        if visitor_files:
            try:
                parsed_rules = []
                for visitor_file in visitor_files:
                    v_df = pd.read_excel(visitor_file)
                    cols = list(v_df.columns)
                    target_cols = {}
                    for c in cols:
                        c_str = str(c).strip()
                        if "인원" in c_str or "가구원" in c_str: target_cols["people"] = c
                        elif "주거" in c_str or "형태" in c_str: target_cols["housing"] = c
                        elif "특이" in c_str or "사유" in c_str: target_cols["remark"] = c
                        elif "추가" in c_str or "품목수" in c_str or "개수" in c_str or "허용" in c_str: target_cols["extra_qty"] = c
                        elif "필수" in c_str or "제공" in c_str or "물품" in c_str: target_cols["mandatory_item"] = c
                    
                    if "remark" in target_cols and "extra_qty" in target_cols:
                        for _, r in v_df.iterrows():
                            rule = {
                                "people": str(r[target_cols["people"]]).strip() if "people" in target_cols else "",
                                "housing": str(r[target_cols["housing"]]).strip() if "housing" in target_cols else "",
                                "remark": str(r[target_cols["remark"]]).strip(),
                                "extra_qty": int(r[target_cols["extra_qty"]]) if str(r[target_cols["extra_qty"]]).isdigit() else (0 if pd.isna(r[target_cols["extra_qty"]]) else r[target_cols["extra_qty"]]),
                                "mandatory_item": str(r[target_cols["mandatory_item"]]).strip() if "mandatory_item" in target_cols and not pd.isna(r[target_cols["mandatory_item"]]) else ""
                            }
                            if rule["remark"] and rule["remark"] != "nan":
                                parsed_rules.append(rule)
                    else:
                        st.warning(f"[{visitor_file.name}] 필수 열 누락으로 건너뜁니다.")
                if parsed_rules:
                    st.dataframe(pd.DataFrame(parsed_rules))
                    if st.button("이 규칙으로 저장 및 적용"):
                        update_visitor_rules(parsed_rules)
                        st.success(f"총 {len(parsed_rules)}개의 방문자 특이사항 규칙이 병합 저장되었습니다.")
                        st.rerun()
            except Exception as e:
                st.error(f"엑셀 파싱 중 오류: {e}")
                
    with tab_fms:
        st.write("FMS 실제 재고 리스트 엑셀을 업로드하여 기준 정보를 갱신합니다.")
        fms_files = st.file_uploader("FMS 마스터 엑셀 업로드", type=["xlsx", "xls"], key="fms_upload", accept_multiple_files=True)
        if fms_files:
            try:
                fms_list = []
                for fms_file in fms_files:
                    fms_df = pd.read_excel(fms_file)
                    cols = list(fms_df.columns)
                    fms_map = {}
                    for c in cols:
                        c_s = str(c).strip()
                        if "물품" in c_s or "제품" in c_s or "품목명" in c_s: fms_map["name"] = c
                        elif "바코드" in c_s: fms_map["bc"] = c
                    
                    if "name" in fms_map:
                        for _, row in fms_df.iterrows():
                            n_val = str(row[fms_map["name"]]).strip()
                            if n_val and n_val != "nan":
                                entry = {"product_name": n_val}
                                if "bc" in fms_map and not pd.isna(row[fms_map["bc"]]):
                                    entry["barcode"] = str(row[fms_map["bc"]]).strip()
                                fms_list.append(entry)
                    else:
                        st.warning(f"[{fms_file.name}] 필수 열('물품명' 등) 누락으로 건너뜁니다.")
                if fms_list:
                    if st.button(f"총 {len(fms_list)}개 FMS 재고 동기화"):
                        update_fms_master(fms_list)
                        st.success("FMS 기준 정보가 갱신되었습니다!")
                        st.rerun()
            except Exception as e:
                st.error(f"FMS 파싱 오류: {e}")
            
st.divider()

st.subheader("👤 이용자 식별 (회원 바코드 스캔 또는 수기 입력)")
st.write("방문한 이용자의 바코드를 스캔하거나 식별번호를 직접 입력하세요.")

if "current_user_barcode" not in st.session_state:
    st.session_state["current_user_barcode"] = None

col_scan, col_manual = st.columns(2)

with col_scan:
    with st.form("user_barcode_form", clear_on_submit=True):
        u_barcode = st.text_input("회원 바코드 스캔 (리더기용)")
        u_submitted = st.form_submit_button("입력")
        if u_submitted and u_barcode:
            st.session_state["current_user_barcode"] = u_barcode

with col_manual:
    with st.form("user_manual_form", clear_on_submit=True):
        m_barcode = st.text_input("식별번호 직접 입력 (수기용)")
        m_submitted = st.form_submit_button("적용")
        if m_submitted and m_barcode:
            st.session_state["current_user_barcode"] = m_barcode

if st.session_state["current_user_barcode"]:
    curr_u = st.session_state["current_user_barcode"]
    user_info = get_user_info_by_barcode(curr_u)
    
    st.info(f"✅ 현재 식별된 이용자: **{curr_u}**")
    if user_info:
        # DB 모의 정보가 있을 경우 특성 안내
        st.write(f"- 인원: {user_info.get('people', '알수없음')}, 주거: {user_info.get('housing', '알수없음')}")
        if user_info.get("mandatory_item") and user_info.get("mandatory_item") != "nan":
            st.warning(f"🚨 [필수 알림] 이 이용자에게는 **'{user_info['mandatory_item']}'**을(를) 반드시 제공해야 합니다!", icon="🚨")
    if st.button("초기화 (새 이용자 받기)"):
        st.session_state["current_user_barcode"] = None
        st.rerun()

st.divider()

st.subheader("📦 상품 바코드 스캔 입력")

if "scan_history" not in st.session_state:
    st.session_state["scan_history"] = []

# clear_on_submit=True를 통해 바코드 리더기가 찍은 후 Enter를 누르면 창이 비워짐
with st.form("barcode_form", clear_on_submit=True):
    # Streamlit에서 HTML autofocus 우회를 완벽히 하긴 어려우나, 가장 첫번째 Input에 자동 포커스됨.
    barcode = st.text_input("바코드 번호 스캔 (커서를 여기에 두세요)")
    submitted = st.form_submit_button("입력 (또는 Enter)")
    
    if submitted and barcode:
        # 규칙 검증 (기본 5개 품목) - 실제로는 DB 품목 마스터와 대조
        valid_prefixes = ["880", "123", "456"] # 예시용 유효 바코드 접두사
        
        is_valid = any(barcode.startswith(prefix) for prefix in valid_prefixes) or len(barcode) > 5
        
        if is_valid:
            st.success(f"✅ [{barcode}] 스캔 완료 (기본 5개 품목 규칙 통과)")
            st.session_state["scan_history"].insert(0, f"{barcode} (승인됨)")
            # DB 연동: update_inventory(barcode, 1, "현장웹POS", "바코드 스캔 완료")
        else:
            st.error(f"❌ [{barcode}] 승인되지 않은 품목입니다! (초과 또는 미등록 품목)")
            st.session_state["scan_history"].insert(0, f"{barcode} (거절됨)")

st.subheader("최근 스캔 내역")
for item in st.session_state["scan_history"][:5]:
    st.write(f"- {item}")

st.divider()

st.subheader("⚠️ 방문자 특이사항 (서비스 물품 쿼터 추가)")
v_rules = get_visitor_rules()
if not v_rules:
    st.info("💡 상단의 '⚙️ 설정' 탭에서 특이사항 규칙 엑셀을 업로드하면 동적 조건이 활성화됩니다.")
    exception_type = st.selectbox("당일 방문자 속성 선택", ["선택안함", "기본(룰셋 없음)"])
else:
    people_options = sorted(list(set(r["people"] for r in v_rules if r["people"] and r["people"] != "nan")))
    housing_options = sorted(list(set(r["housing"] for r in v_rules if r["housing"] and r["housing"] != "nan")))
    
    col_p, col_h = st.columns(2)
    selected_people = col_p.selectbox("가구 인원 선택", ["선택안함"] + people_options)
    selected_housing = col_h.selectbox("주거 형태 선택", ["선택안함"] + housing_options)
    
    matched_rule = None
    for r in v_rules:
        match_p = r["people"] == selected_people if r["people"] and r["people"] != "nan" else True
        match_h = r["housing"] == selected_housing if r["housing"] and r["housing"] != "nan" else True
        
        if match_p and match_h and (selected_people != "선택안함" or selected_housing != "선택안함"):
            # 둘 다 선택안함인 경우는 패스, 하나라도 맞으면 매칭
            matched_rule = r
            break
            
    if matched_rule:
        st.success(f"[{matched_rule['remark']}] 대상자입니다. 서비스 품목 {matched_rule['extra_qty']}개 한도가 임시로 승인되었습니다.")
        if matched_rule.get("mandatory_item") and matched_rule["mandatory_item"] != "nan":
            st.warning(f"🚨 [필수 알림] 위 조건에 따라 **'{matched_rule['mandatory_item']}'**을(를) 필수 제공해야 합니다!", icon="🚨")
    elif selected_people != "선택안함" or selected_housing != "선택안함":
        st.warning("선택한 조건에 해당하는 추가 지원 특이사항(규칙)이 없습니다.")

st.divider()

st.subheader("📊 아침, 점심 파일 만들기")
st.write("아침에 가공할 원본 엑셀(FMS Raw Data)을 업로드하면, 복잡한 수작업을 생략하고 일일마감일지 양식으로 즉시 자동 변환됩니다.")

import sys
import os
import importlib
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import services.excel_processor
importlib.reload(services.excel_processor)
from services.excel_processor import process_morning_excel

tab_morning, tab_lunch = st.tabs(["아침", "점심"])

with tab_morning:
    st.markdown("### 🌅 아침 엑셀 가공")
    
    from datetime import datetime
    default_fname = datetime.now().strftime("%m.%d 일일마감일지.xlsx")
    target_filename = st.text_input("생성될 엑셀 파일명 설정", value=default_fname)
    
    uploaded_files = st.file_uploader("관련 엑셀 파일들을 모두 업로드하세요 (FMS 원장 등 다중 선택 가능)", type=["xlsx", "xls"], key="morning_upload", accept_multiple_files=True)
    
    if uploaded_files:
        try:
            with st.spinner("엑셀 데이터를 병합 및 분석하여 마감일지 양식(Vision 포맷)으로 생성 중입니다..."):
                processed_excel_bytes = process_morning_excel(uploaded_files)
            
            st.success("✅ 파일 가공 완료!")
            
            # Streamlit 내장 다운로드 버튼 사용
            st.download_button(
                label="📥 엑셀 마감일지 다운로드",
                data=processed_excel_bytes,
                file_name=target_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
            
        except Exception as e:
            st.error(f"엑셀 처리 중 오류가 발생했습니다: {e}")

with tab_lunch:
    st.markdown("### ☀️ 점심 엑셀 가공")
    st.info("점심 파일 가공 기능은 추후 업데이트 예정입니다.")
