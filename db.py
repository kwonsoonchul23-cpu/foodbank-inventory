import streamlit as st
from firebase_admin import firestore # 누락된 firestore 임포트 추가

# Streamlit 캐시 리로드 트리거용 주석
def _check_permission(allowed_roles):
    """현재 세션의 role(리스트)이 허용된 역할에 하나라도 포함되는지 검증"""
    current_roles = st.session_state.get("role", [])
    if isinstance(current_roles, str):
        current_roles = [current_roles] # 구버전 호환
        
    if "admin" in current_roles:
        return # admin은 무조건 패스
        
    has_permission = any(role in allowed_roles for role in current_roles)
    if not has_permission:
        raise PermissionError(f"접근 거부: 현재 권한({current_roles})으로는 실행할 수 없습니다.")

def get_all_users():
    """[관리자 전용] 모든 사용자 목록 조회"""
    _check_permission(["admin"])
    
    if st.session_state.get("firebase_inited"):
        db = st.session_state["db"]
        users = db.collection("users").stream()
        return [user.to_dict() for user in users]
    else:
        state = _load_shared_state()
        return list(state.get("users", {}).values())

def update_user_role(user_id, new_role):
    """[관리자 전용] 사용자 권한 수정"""
    _check_permission(["admin"])
    
    if st.session_state.get("firebase_inited"):
        db = st.session_state["db"]
        db.collection("users").document(user_id).update({"role": new_role})
    else:
        state = _load_shared_state()
        if "users" not in state:
            state["users"] = {}
        if user_id in state["users"]:
            state["users"][user_id]["role"] = new_role
            _save_shared_state(state)

def delete_user(user_id):
    """[관리자 전용] 사용자 계정 삭제"""
    _check_permission(["admin"])
    
    if st.session_state.get("firebase_inited"):
        db = st.session_state["db"]
        db.collection("users").document(user_id).delete()
        # 해당 사용자의 스케줄도 연쇄 삭제
        tasks = db.collection("tasks").where("user_id", "==", user_id).stream()
        for task in tasks:
            db.collection("tasks").document(task.id).delete()
    else:
        state = _load_shared_state()
        if user_id in state.get("users", {}):
            del state["users"][user_id]
            
            # 해당 사용자의 스케줄 연쇄 삭제
            if "tasks" in state:
                tasks_to_delete = [t_id for t_id, t in state["tasks"].items() if t.get("user_id") == user_id]
                for t_id in tasks_to_delete:
                    del state["tasks"][t_id]
                    
            _save_shared_state(state)

def get_inventory():
    """모든 권한(승인된) 조회 가능. FMS 기준 전산 재고 반환"""
    _check_permission(["admin", "operator", "inventory"])
    
    if st.session_state.get("firebase_inited"):
        db = st.session_state["db"]
        items = db.collection("inventory").stream()
        return [item.to_dict() for item in items]
    else:
        state = _load_shared_state()
        return list(state.get("inventory", {}).values())

def _detect_fms_columns(df):
    """FMS 엑셀의 컬럼명을 자동 감지하여 표준 매핑을 반환합니다.
    
    지원하는 양식:
    1) FMS 원본: 물품명, 현 재고, 바코드, 대분류, 기부자, 기부일자, 유통기한(소비기한), ...
    2) 간이 양식: 품목명, 수량
    """
    col_map = {}
    columns = list(df.columns)
    
    # 물품명 / 품목명
    for c in columns:
        c_clean = str(c).strip()
        if c_clean in ("물품명", "품목명", "상품명", "품명"):
            col_map["item_name"] = c
            break
    
    # 수량 / 현 재고
    for c in columns:
        c_clean = str(c).strip()
        if c_clean in ("현 재고", "현재고", "수량", "재고수량", "재고"):
            col_map["qty"] = c
            break
    
    # 바코드
    for c in columns:
        c_clean = str(c).strip()
        if c_clean in ("바코드", "바코드번호", "코드"):
            col_map["barcode"] = c
            break
    
    # 대분류
    for c in columns:
        c_clean = str(c).strip()
        if c_clean in ("대분류", "분류", "카테고리"):
            col_map["category"] = c
            break
    
    # 기부자
    for c in columns:
        c_clean = str(c).strip()
        if c_clean in ("기부자", "기부처", "공급자"):
            col_map["donor"] = c
            break
    
    # 기부일자
    for c in columns:
        c_clean = str(c).strip()
        if c_clean in ("기부일자", "입고일", "입고일자"):
            col_map["donated_date"] = c
            break
    
    # 유통기한
    for c in columns:
        c_clean = str(c).strip()
        if "유통기한" in c_clean or "소비기한" in c_clean or "소비" in c_clean:
            col_map["expiry"] = c
            break
    
    # 접수센터
    for c in columns:
        c_clean = str(c).strip()
        if c_clean in ("접수센터", "접수처"):
            col_map["center"] = c
            break
    
    # 장부단가
    for c in columns:
        c_clean = str(c).strip()
        if c_clean in ("장부단가", "단가"):
            col_map["unit_price"] = c
            break
    
    # 장부금액
    for c in columns:
        c_clean = str(c).strip()
        if c_clean in ("장부금액",):
            col_map["total_price"] = c
            break
    
    # 보관장소
    for c in columns:
        c_clean = str(c).strip()
        if c_clean in ("보관장소", "저장위치"):
            col_map["storage"] = c
            break
    
    return col_map


def _aggregate_fms_data(df, col_map):
    """FMS DataFrame을 물품명 기준으로 합산하고 메타데이터를 구조화합니다.
    
    Returns:
        dict: {물품명: {item, fms_qty, category, barcodes, details, earliest_expiry}}
        list: 미리보기용 요약 리스트
    """
    import pandas as pd
    
    item_col = col_map.get("item_name")
    qty_col = col_map.get("qty")
    
    if not item_col or not qty_col:
        return {}, []
    
    aggregated = {}  # {물품명: {...}}
    last_category = None  # 대분류 전파용 (FMS 양식에서 첫 행에만 대분류가 나옴)
    
    for idx, row in df.iterrows():
        item_name = row.get(item_col)
        
        # 빈 행 또는 합계 행 제외
        if pd.isna(item_name) or str(item_name).strip() == "":
            continue
        item_name = str(item_name).strip()
        if item_name in ("합계", "총합계", "소계"):
            continue
        
        # 수량 파싱
        raw_qty = row.get(qty_col, 0)
        try:
            qty = int(float(raw_qty)) if not pd.isna(raw_qty) else 0
        except (ValueError, TypeError):
            qty = 0
        
        # 대분류 전파 (FMS 양식: 카테고리가 변경될 때만 값이 존재)
        cat_col = col_map.get("category")
        if cat_col:
            cat_val = row.get(cat_col)
            if not pd.isna(cat_val) and str(cat_val).strip():
                last_category = str(cat_val).strip()
        
        # 바코드
        barcode = None
        bc_col = col_map.get("barcode")
        if bc_col:
            bc_val = row.get(bc_col)
            if not pd.isna(bc_val):
                barcode = str(bc_val).strip()
                # 소수점 제거 (엑셀에서 숫자로 읽힌 경우)
                if barcode.endswith(".0"):
                    barcode = barcode[:-2]
        
        # 기부자
        donor = None
        dn_col = col_map.get("donor")
        if dn_col:
            dn_val = row.get(dn_col)
            if not pd.isna(dn_val):
                donor = str(dn_val).strip()
        
        # 기부일자
        donated_date = None
        dd_col = col_map.get("donated_date")
        if dd_col:
            dd_val = row.get(dd_col)
            if not pd.isna(dd_val):
                try:
                    donated_date = str(dd_val)[:10]  # YYYY-MM-DD
                except:
                    donated_date = str(dd_val)
        
        # 유통기한
        expiry = None
        exp_col = col_map.get("expiry")
        if exp_col:
            exp_val = row.get(exp_col)
            if not pd.isna(exp_val):
                try:
                    expiry = str(exp_val)[:10]
                except:
                    expiry = str(exp_val)
        
        # 집계
        if item_name not in aggregated:
            aggregated[item_name] = {
                "item": item_name,
                "fms_qty": 0,
                "category": last_category or "",
                "barcodes": [],
                "details": [],
                "earliest_expiry": None
            }
        
        aggregated[item_name]["fms_qty"] += qty
        
        # 대분류 갱신 (빈 값이면 이전 값 유지)
        if last_category and not aggregated[item_name]["category"]:
            aggregated[item_name]["category"] = last_category
        
        # 바코드 수집 (중복 제거)
        if barcode and barcode not in aggregated[item_name]["barcodes"]:
            aggregated[item_name]["barcodes"].append(barcode)
        
        # 상세 내역 추가
        detail = {"수량": qty}
        if donor:
            detail["기부자"] = donor
        if donated_date:
            detail["기부일자"] = donated_date
        if expiry:
            detail["유통기한"] = expiry
        aggregated[item_name]["details"].append(detail)
        
        # 가장 빠른 유통기한 추적
        if expiry:
            current_earliest = aggregated[item_name]["earliest_expiry"]
            if current_earliest is None or expiry < current_earliest:
                aggregated[item_name]["earliest_expiry"] = expiry
    
    # 미리보기 요약 리스트 생성
    preview = []
    for name, data in aggregated.items():
        preview.append({
            "물품명": name,
            "대분류": data["category"],
            "합산 수량": data["fms_qty"],
            "바코드": ", ".join(data["barcodes"]) if data["barcodes"] else "-",
            "내역 수": len(data["details"]),
            "유통기한(최근)": data["earliest_expiry"] or "-"
        })
    
    return aggregated, preview


def upload_fms_excel(df, col_map=None):
    """[관리자 전용] FMS 엑셀 파일을 읽어 기준 재고 데이터를 동기화합니다.
    
    실제 FMS 양식(물품명, 현 재고, 바코드, 대분류, 기부자 등)과
    간이 양식(품목명, 수량) 모두 자동으로 인식합니다.
    같은 물품명이 여러 행에 존재하면 합산하여 총 기준재고를 산출합니다.
    """
    _check_permission(["admin"])
    
    if col_map is None:
        col_map = _detect_fms_columns(df)
    
    aggregated, _ = _aggregate_fms_data(df, col_map)
    
    if not aggregated:
        return
    
    if st.session_state.get("firebase_inited"):
        db_ref = st.session_state["db"]
        # 기존 데이터 삭제 후 새 데이터 추가
        for doc in db_ref.collection("inventory").stream():
            doc.reference.delete()
            
        for item_name, data in aggregated.items():
            db_ref.collection("inventory").document(item_name).set(data)
            
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_ref.collection("metadata").document("fms").set({
            "last_updated": now_str,
            "total_items": len(aggregated)
        })
    else:
        state = _load_shared_state()
        state["inventory"] = {}
        for item_name, data in aggregated.items():
            state["inventory"][item_name] = data
            
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if "metadata" not in state:
            state["metadata"] = {}
        state["metadata"]["fms"] = {
            "last_updated": now_str,
            "total_items": len(aggregated)
        }
        _save_shared_state(state)

def get_fms_status():
    """현재 시스템에 저장된 기준재고(FMS) 상태 메타데이터 반환"""
    if st.session_state.get("firebase_inited"):
        db = st.session_state["db"]
        doc = db.collection("metadata").document("fms").get()
        if doc.exists:
            return doc.to_dict()
        return None
    else:
        state = _load_shared_state()
        return state.get("metadata", {}).get("fms", None)

def get_audit_logs():
    """[전체 로그인 사용자] 누가 언제 무엇을 파악했는지 로그 조회"""
    _check_permission(["admin", "operator", "inventory"])
    
    if st.session_state.get("firebase_inited"):
        db = st.session_state["db"]
        logs = db.collection("logs").order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
        return [log.to_dict() for log in logs]
    else:
        state = _load_shared_state()
        logs = list(state.get("logs", {}).values())
        return sorted(logs, key=lambda x: x.get("timestamp", ""), reverse=True)

def get_inventory_summary():
    """[전체 로그인 사용자] 품목별 실사 합산 수량과 FMS 기준재고 대조 결과 반환"""
    _check_permission(["admin", "operator", "inventory"])
    
    logs = get_audit_logs()
    fms_data = get_inventory()
    fms_dict = {item["item"]: item["fms_qty"] for item in fms_data} if fms_data else {}
    
    # 품목별 최신 입력을 사용자별로 집계 (같은 사용자가 같은 품목을 여러 번 입력하면 최신값 사용)
    user_item_latest = {}  # {(user_id, item_id): {quantity, timestamp, ...}}
    for log in logs:
        key = (log.get("user_id", ""), log.get("item_id", ""))
        if key not in user_item_latest:
            user_item_latest[key] = log
    
    # 품목별 합산
    item_totals = {}
    for (user_id, item_id), log in user_item_latest.items():
        if item_id not in item_totals:
            item_totals[item_id] = {"total_qty": 0, "contributors": []}
        item_totals[item_id]["total_qty"] += log.get("quantity", 0)
        item_totals[item_id]["contributors"].append({
            "user_name": log.get("user_name", "Unknown"),
            "quantity": log.get("quantity", 0)
        })
    
    # FMS 대조 결과 생성
    summary = []
    all_items = set(list(item_totals.keys()) + list(fms_dict.keys()))
    for item in sorted(all_items):
        total_qty = item_totals.get(item, {}).get("total_qty", 0)
        fms_qty = fms_dict.get(item, 0)
        diff = total_qty - fms_qty
        contributors = item_totals.get(item, {}).get("contributors", [])
        
        if fms_qty == 0 and item not in fms_dict:
            status = "🆕 신규"
        elif diff == 0:
            status = "🟢 일치"
        elif diff > 0:
            status = "🟡 초과"
        else:
            status = "🔴 부족"
        
        summary.append({
            "품목명": item,
            "실사 합산": total_qty,
            "FMS 기준": fms_qty,
            "오차": diff,
            "상태": status,
            "입력자 수": len(contributors),
            "입력자 상세": contributors
        })
    
    return summary

import datetime

def update_inventory(item_id, quantity, location, log_msg):
    """[현장운영, 재고관리] 재고 실사 수량 업데이트 및 로그 기록"""
    _check_permission(["admin", "operator", "inventory"])
    user_id = st.session_state.get("user_id")
    user_name = st.session_state.get("name", "Unknown")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if st.session_state.get("firebase_inited"):
        db = st.session_state["db"]
        # 로그만 중점적으로 기록 (실사 결과)
        db.collection("logs").add({
            "user_id": user_id,
            "user_name": user_name,
            "item_id": item_id,
            "quantity": quantity,
            "location": location,
            "message": log_msg,
            "timestamp": firestore.SERVER_TIMESTAMP
        })
    else:
        # Mock 로그 기록
        state = _load_shared_state()
        if "logs" not in state:
            state["logs"] = {}
        log_id = str(len(state["logs"]))
        state["logs"][log_id] = {
            "user_id": user_id,
            "user_name": user_name,
            "item_id": item_id,
            "quantity": quantity,
            "location": location,
            "message": log_msg,
            "timestamp": now_str
        }
        _save_shared_state(state)

# --- 동적 구역(Zones) 관리 로직 ---

def get_zones():
    """모든 사용자가 볼 수 있는 구역 데이터 로드"""
    if st.session_state.get("firebase_inited"):
        db = st.session_state["db"]
        zones = db.collection("zones").stream()
        return {zone.id: zone.to_dict().get("sub_zones", []) for zone in zones}
    else:
        # Mock Default Zones
        state = _load_shared_state()
        if "zones" not in state:
            state["zones"] = {
                "[구역1] 진열대": ["진열대 A열", "진열대 B열", "진열대 C열", "냉동/냉장 쇼케이스", "카운터 앞"],
                "[구역2] 지하창고": ["지하창고 입구쪽", "지하창고 안쪽 선반", "지하 바닥 파렛트", "기타 구석"],
                "[구역3] 주차장": ["주차장 좌측 파렛트", "주차장 우측 천막", "푸드뱅크 탑차 내부", "하역장"]
            }
            _save_shared_state(state)
        return state["zones"]

def update_zone(zone_name, sub_zones_list):
    """[관리자 전용] 구역 추가/수정"""
    _check_permission(["admin"])
    if st.session_state.get("firebase_inited"):
        db = st.session_state["db"]
        db.collection("zones").document(zone_name).set({"sub_zones": sub_zones_list})
    else:
        state = _load_shared_state()
        if "zones" not in state:
            state["zones"] = {}
        state["zones"][zone_name] = sub_zones_list
        _save_shared_state(state)

def delete_zone(zone_name):
    """[관리자 전용] 구역 삭제"""
    _check_permission(["admin"])
    if st.session_state.get("firebase_inited"):
        db = st.session_state["db"]
        db.collection("zones").document(zone_name).delete()
    else:
        state = _load_shared_state()
        if zone_name in state.get("zones", {}):
            del state["zones"][zone_name]
            _save_shared_state(state)

# --- 동적 평면도 레이아웃(Layout) 관리 ---

def get_current_layout():
    """현재 활성화된 평면도 레이아웃 로드 (3개 구역 포함)"""
    default_layout = {
        "zone_1": {
            "name": "장소 1: 진열대",
            "width": 1000, "height": 600,
            "racks": [
                {"id": "r1_1", "name": "진열매대 C", "x": 50, "y": 200, "w": 120, "h": 50, "color": "#e8f5e9"},
                {"id": "r1_2", "name": "진열매대 D", "x": 50, "y": 260, "w": 120, "h": 50, "color": "#e8f5e9"},
                {"id": "r1_3", "name": "서비스 매대 B", "x": 250, "y": 100, "w": 130, "h": 50, "color": "#e1bee7"},
                {"id": "r1_4", "name": "서비스 매대 A", "x": 400, "y": 100, "w": 130, "h": 50, "color": "#e1bee7"},
                {"id": "r1_5", "name": "진열매대 E", "x": 400, "y": 250, "w": 120, "h": 50, "color": "#e8f5e9"},
                {"id": "r1_6", "name": "서비스 매대 C", "x": 400, "y": 320, "w": 130, "h": 50, "color": "#e1bee7"},
                {"id": "r1_7", "name": "진열매대 B", "x": 560, "y": 100, "w": 120, "h": 50, "color": "#e8f5e9"},
                {"id": "r1_8", "name": "진열매대 A", "x": 560, "y": 160, "w": 120, "h": 50, "color": "#e8f5e9"},
                {"id": "r1_9", "name": "재고 A", "x": 720, "y": 160, "w": 100, "h": 50, "color": "#ffecb3"},
                {"id": "bg1_1", "name": "퇴실구", "x": 260, "y": 320, "w": 100, "h": 50, "color": "#ffebee", "is_bg": True},
                {"id": "bg1_2", "name": "출입구", "x": 560, "y": 320, "w": 100, "h": 50, "color": "#ffebee", "is_bg": True}
            ]
        },
        "zone_2": {
            "name": "장소 2: 지하 창고",
            "width": 1000, "height": 600,
            "racks": [
                {"id": "r2_1", "name": "파렛트 E", "x": 50, "y": 50, "w": 120, "h": 50, "color": "#e3f2fd"},
                {"id": "r2_2", "name": "파렛트 C", "x": 50, "y": 110, "w": 120, "h": 50, "color": "#e3f2fd"},
                {"id": "r2_3", "name": "파렛트 A", "x": 50, "y": 170, "w": 120, "h": 50, "color": "#e3f2fd"},
                {"id": "r2_4", "name": "파렛트 D", "x": 190, "y": 50, "w": 120, "h": 50, "color": "#e3f2fd"},
                {"id": "r2_5", "name": "파렛트 B", "x": 190, "y": 170, "w": 120, "h": 50, "color": "#e3f2fd"},
                {"id": "r2_6", "name": "냉장", "x": 560, "y": 300, "w": 120, "h": 50, "color": "#bbdefb"},
                {"id": "r2_7", "name": "냉동", "x": 700, "y": 300, "w": 120, "h": 50, "color": "#d1c4e9"},
                {"id": "bg2_1", "name": "사무용 A", "x": 500, "y": 50, "w": 100, "h": 50, "color": "#eeeeee", "is_bg": True},
                {"id": "bg2_2", "name": "사무용 B", "x": 620, "y": 50, "w": 100, "h": 50, "color": "#eeeeee", "is_bg": True},
                {"id": "bg2_3", "name": "사무용 C", "x": 740, "y": 50, "w": 100, "h": 50, "color": "#eeeeee", "is_bg": True},
                {"id": "bg2_4", "name": "사무용 D", "x": 740, "y": 170, "w": 100, "h": 50, "color": "#eeeeee", "is_bg": True},
                {"id": "bg2_5", "name": "출입구", "x": 500, "y": 110, "w": 100, "h": 50, "color": "#e8f5e9", "is_bg": True},
                {"id": "bg2_6", "name": "퇴실구", "x": 500, "y": 170, "w": 100, "h": 50, "color": "#ffebee", "is_bg": True},
                {"id": "bg2_7", "name": "퇴실구", "x": 100, "y": 250, "w": 100, "h": 50, "color": "#ffebee", "is_bg": True},
                {"id": "bg2_8", "name": "출입구", "x": 100, "y": 310, "w": 100, "h": 50, "color": "#e8f5e9", "is_bg": True}
            ]
        },
        "zone_3": {
            "name": "장소 3: 주차장",
            "width": 1000, "height": 600,
            "racks": [
                {"id": "r3_1", "name": "탑차 (구식)", "x": 100, "y": 150, "w": 200, "h": 80, "color": "#ffe0b2"},
                {"id": "r3_2", "name": "승용차", "x": 350, "y": 150, "w": 200, "h": 80, "color": "#eeeeee"},
                {"id": "r3_3", "name": "탑차 (신식)", "x": 600, "y": 150, "w": 200, "h": 80, "color": "#ffccbc"}
            ]
        }
    }
    
    if st.session_state.get("firebase_inited"):
        db = st.session_state["db"]
        doc = db.collection("layouts").document("current").get()
        if doc.exists:
            return doc.to_dict().get("data", default_layout)
        return default_layout
    else:
        state = _load_shared_state()
        if "layout_current" not in state:
            state["layout_current"] = default_layout
            _save_shared_state(state)
        return state["layout_current"]

def save_layout(layout_data):
    """[관리자 전용] 레이아웃 저장 및 히스토리(버전) 기록"""
    _check_permission(["admin"])
    user_id = st.session_state.get("user_id", "admin")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if st.session_state.get("firebase_inited"):
        db = st.session_state["db"]
        # 현재 레이아웃 갱신
        db.collection("layouts").document("current").set({
            "data": layout_data,
            "updated_by": user_id,
            "updated_at": now_str
        })
        # 히스토리에 추가
        db.collection("layout_history").add({
            "data": layout_data,
            "saved_by": user_id,
            "timestamp": now_str
        })
    else:
        state = _load_shared_state()
        state["layout_current"] = layout_data
        if "layout_history" not in state:
            state["layout_history"] = []
        
        state["layout_history"].insert(0, {
            "data": layout_data,
            "saved_by": user_id,
            "timestamp": now_str
        })
        _save_shared_state(state)

def get_layout_history():
    """[관리자 전용] 레이아웃 변경 히스토리 목록 조회"""
    _check_permission(["admin"])
    if st.session_state.get("firebase_inited"):
        db = st.session_state["db"]
        docs = db.collection("layout_history").order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
        return [doc.to_dict() for doc in docs]
    else:
        state = _load_shared_state()
        return state.get("layout_history", [])

# --- 바코드 및 장바구니 연동 관리 ---
import json
import os

SHARED_STATE_PATH = os.path.join(os.path.dirname(__file__), "shared_state.json")

def _load_shared_state():
    if not os.path.exists(SHARED_STATE_PATH):
        return {"barcode_rules": {}, "service_rules": {}, "cart": {"items": {}, "services": {}, "total_item_count": 0}}
    try:
        with open(SHARED_STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"barcode_rules": {}, "service_rules": {}, "cart": {"items": {}, "services": {}, "total_item_count": 0}}

def _save_shared_state(state):
    with open(SHARED_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=4)

def get_barcode_rules():
    state = _load_shared_state()
    return state.get("barcode_rules", {})

def update_barcode_rule(barcode, product_name, item_group, required_qty):
    _check_permission(["admin", "operator"])
    state = _load_shared_state()
    state.setdefault("barcode_rules", {})[barcode] = {
        "product": product_name,
        "item": item_group,
        "required_qty": int(required_qty)
    }
    _save_shared_state(state)

def delete_barcode_rule(barcode):
    _check_permission(["admin", "operator"])
    state = _load_shared_state()
    if barcode in state.get("barcode_rules", {}):
        del state["barcode_rules"][barcode]
        _save_shared_state(state)

def get_service_rules():
    state = _load_shared_state()
    return state.get("service_rules", {})

def update_service_rule(barcode, service_name, required_qty):
    _check_permission(["admin", "operator"])
    state = _load_shared_state()
    state.setdefault("service_rules", {})[barcode] = {
        "service_name": service_name,
        "required_qty": int(required_qty)
    }
    _save_shared_state(state)

def delete_service_rule(barcode):
    _check_permission(["admin", "operator"])
    state = _load_shared_state()
    if barcode in state.get("service_rules", {}):
        del state["service_rules"][barcode]
        _save_shared_state(state)

def update_service_rules_bulk(rules_dict):
    """업로드된 서비스 물품 룰 일괄 병합 (기존 유지 + 새 항목 덮어쓰기)"""
    state = _load_shared_state()
    if "service_rules" not in state:
        state["service_rules"] = {}
    
    # 딕셔너리 병합 (Merge)
    for k, v in rules_dict.items():
        state["service_rules"][k] = v
        
    _save_shared_state(state)


def get_cart_state():
    state = _load_shared_state()
    return state.get("cart", {"items": {}, "services": {}, "total_item_count": 0})

def reset_cart():
    _check_permission(["admin", "operator"])
    state = _load_shared_state()
    state["cart"] = {"items": {}, "services": {}, "total_item_count": 0}
    _save_shared_state(state)

def get_public_guides():
    """모든 사용자가 접근 가능한 퍼블릭 가이드 조회 (로그인 불필요)"""
    state = _load_shared_state()
    default_guides = {
        "market": [{"title": "1단계: 장바구니 준비", "content": "장바구니를 챙겨주세요.", "media_url": ""}],
        "dream": [{"title": "1단계: 바코드 준비", "content": "원하는 물품을 선택하세요.", "media_url": ""}]
    }
    return state.get("public_guides", default_guides)

def update_public_guides(market_steps, dream_steps):
    """[관리자 전용] 퍼블릭 가이드 단계별 안내 수정"""
    _check_permission(["admin"])
    state = _load_shared_state()
    state["public_guides"] = {
        "market": market_steps,
        "dream": dream_steps
    }
    _save_shared_state(state)

def get_portal_config():
    """포털 메인 화면의 동적 설정 (구조화된 데이터)을 가져옵니다."""
    state = _load_shared_state()
    default_config = {
        "gif_path": "basic/hello.gif",
        "subtitle": "이용하실 서비스를 선택해주세요",
        "subtitle_size": 24,
        "slider_icon": "✏️",
        "guide_text_size": 18,
        "slider_width_pc": 600,
        "slider_width_mobile_pct": 95,
        "slider_font_size": 1.2,
        "options": ["🛒 은평푸드 마켓 이용자", "🎁 그냥드림 이용자"]
    }
    
    saved_config = state.get("portal_config", {})
    # 이전 버전(HTML/CSS 통저장) 호환성 및 누락 키 처리
    for k, v in default_config.items():
        if k not in saved_config:
            saved_config[k] = v
            
    # 빈 리스트일 경우 방어 로직 (관리자가 삭제해서 빈 경우 제외, 초기화 오류 대비)
    if not saved_config.get("options"):
        saved_config["options"] = ["🛒 은평푸드 마켓 이용자", "🎁 그냥드림 이용자"]
        
    return saved_config

def update_portal_config(new_config):
    """[관리자 전용] 포털 디자인 세부 설정 업데이트"""
    _check_permission(["admin"])
    state = _load_shared_state()
    state["portal_config"] = new_config
    _save_shared_state(state)

def get_sitemap_config():
    """사이트맵 및 각 페이지별 이용 목적 설정 조회"""
    state = _load_shared_state()
    default_sitemap = {
        "description": "이 사이트는 푸드뱅크의 효율적인 재고 관리와 원활한 운영을 위해 제작되었습니다.",
        "pages": [
            {"name": "포털 (메인 화면)", "purpose": "일반 이용자들에게 맞춤형 단계별 안내와 QR 접속 화면을 제공합니다."},
            {"name": "재고관리 (실사)", "purpose": "현장에서 모바일 기기로 신속하게 재고 수량을 파악하고 입력할 수 있습니다."},
            {"name": "현장운영 (웹 POS)", "purpose": "바코드를 스캔하여 제품을 자동으로 인식하고 특이사항에 따른 서비스를 제공합니다."},
            {"name": "관리자 대시보드", "purpose": "데이터 통계, 엑셀 대조 오차 확인, 그리고 전체 사용자 및 포털 설정을 관리합니다."}
        ]
    }
    return state.get("sitemap_config", default_sitemap)

def update_sitemap_config(new_config):
    """[관리자 전용] 사이트맵 설명 수정"""
    _check_permission(["admin"])
    state = _load_shared_state()
    state["sitemap_config"] = new_config
    _save_shared_state(state)

def get_category_styles():
    """가이드 탭별 맞춤 폰트/스타일(크기,색상) 설정 가져오기"""
    state = _load_shared_state()
    return state.get("category_styles", {})

def update_category_styles(styles):
    """[관리자 전용] 가이드 탭별 맞춤 스타일 설정 저장"""
    _check_permission(["admin"])
    state = _load_shared_state()
    state["category_styles"] = styles
    _save_shared_state(state)

def get_custom_fonts():
    """업로드된 커스텀 폰트 파일 목록 조회"""
    import os
    font_dir = "basic/fonts"
    if not os.path.exists(font_dir):
        return []
    return [f for f in os.listdir(font_dir) if f.lower().endswith(('.ttf', '.otf', '.woff', '.woff2'))]

def get_all_users_info():
    """가입된 모든 사용자 ID 및 프로필 정보 반환"""
    if st.session_state.get("firebase_inited"):
        db = st.session_state["db"]
        users_ref = db.collection("users").stream()
        users_list = []
        for doc in users_ref:
            d = doc.to_dict()
            users_list.append({
                "id": doc.id,
                "name": d.get("name", doc.id),
                "is_visible": d.get("is_visible", True),
                "profile_image": d.get("profile_image", "")
            })
        return users_list
    else:
        try:
            import json
            with open(os.path.join(BASE_DIR, "data", "users.json"), "r", encoding="utf-8") as f:
                data = json.load(f)
                res = []
                for k, v in data.items():
                    res.append({
                        "id": k,
                        "name": v.get("name", k) if isinstance(v, dict) else k,
                        "is_visible": v.get("is_visible", True) if isinstance(v, dict) else True,
                        "profile_image": v.get("profile_image", "") if isinstance(v, dict) else ""
                    })
                return res
        except:
            return [{"id": "User1", "name": "User1", "is_visible": True, "profile_image": ""}]

def update_user_profile(user_id, name, is_visible, profile_image=""):
    """사용자 프로필 및 노출 여부 업데이트"""
    if st.session_state.get("firebase_inited"):
        db = st.session_state["db"]
        db.collection("users").document(user_id).set({
            "name": name,
            "is_visible": is_visible,
            "profile_image": profile_image
        }, merge=True)
    else:
        try:
            import json
            p = os.path.join(BASE_DIR, "data", "users.json")
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if user_id in data and not isinstance(data[user_id], dict):
                data[user_id] = {"password": data[user_id]}
            elif user_id not in data:
                data[user_id] = {}
            data[user_id]["name"] = name
            data[user_id]["is_visible"] = is_visible
            data[user_id]["profile_image"] = profile_image
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except:
            pass

def get_holidays():
    """휴무/공휴일 목록 반환 (법정 공휴일 + 사용자 지정 휴무일)"""
    import holidays
    from datetime import date
    
    kr_holidays = holidays.KR(years=[date.today().year, date.today().year + 1])
    public_holidays = [dt.strftime("%Y-%m-%d") for dt in kr_holidays.keys()]
    
    user_holidays = []
    if st.session_state.get("firebase_inited"):
        db = st.session_state["db"]
        doc = db.collection("settings").document("holidays").get()
        if doc.exists:
            user_holidays = doc.to_dict().get("dates", [])
    else:
        state = _load_shared_state()
        user_holidays = state.get("holidays", [])
        
    # 법정 공휴일과 사용자 지정 휴무일 병합 (중복 제거 후 정렬)
    combined = sorted(list(set(public_holidays + user_holidays)))
    return combined

def update_holidays(dates_list):
    """휴무/공휴일 목록 업데이트"""
    if st.session_state.get("firebase_inited"):
        db = st.session_state["db"]
        db.collection("settings").document("holidays").set({"dates": dates_list}, merge=True)
    else:
        state = _load_shared_state()
        state["holidays"] = dates_list
        _save_shared_state(state)

# --- 개인 스케줄 및 체크리스트 기능 ---

def add_task(user_id, category, sub_category, task_name, details="", shared_category="개인용", start_date=None, end_date=None, is_recurring=False):
    """사용자의 새로운 스케줄 추가 (시작일/종료일 지원)"""
    import uuid
    import datetime
    
    # 기본값 처리 (없으면 오늘)
    if start_date is None:
        start_date = datetime.date.today().strftime("%Y-%m-%d")
    if end_date is None:
        end_date = start_date

    task_id = str(uuid.uuid4())
    task_data = {
        "task_id": task_id,
        "user_id": user_id,
        "category": category, # 상위 그룹
        "sub_category": sub_category, # 담당자/태그 등
        "task_name": task_name,
        "details": details, # 상세 설명
        "shared_category": shared_category, # 공유 설정
        "start_date": start_date,
        "end_date": end_date,
        "is_recurring": is_recurring,
        "delegations": {}, # "YYYY-MM-DD": {"delegated_to": "UserB", "status": "pending"}
        "completed_dates": {} # "YYYY-MM-DD": True
    }
    
    if st.session_state.get("firebase_inited"):
        db = st.session_state["db"]
        db.collection("tasks").document(task_id).set(task_data)
    else:
        state = _load_shared_state()
        if "tasks" not in state:
            state["tasks"] = {}
        state["tasks"][task_id] = task_data
        _save_shared_state(state)

def load_template_tasks(user_id):
    """PDF 기준 기본 푸드뱅크 업무 템플릿 일괄 등록"""
    templates = [
        # 일별 - 오전
        ("일별", "오전", "일일마감일지", "어제 내용 확인"),
        ("일별", "오전", "입출고 내역관리", ""),
        ("일별", "오전", "그냥드림 명단", "엑셀 기입 + 파일철에 모으기"),
        # 일별 - 오후
        ("일별", "오후", "그냥드림 1차", "등록 및 제품 제공"),
        ("일별", "오후", "그냥드림 2차", "상담"),
        ("일별", "오후", "그냥드림 3차", "이용자가 받아와야 할 서류"),
        # 일별 - 퇴근 전
        ("일별", "퇴근 전", "재고 관리", "실재고 파악, 맞교환 등"),
        ("일별", "퇴근 전", "네이버 카페 공유", "재고 부족/초과 사항 공유"),
        # 요일별
        ("요일별", "월요일", "오전 회의", "지난주 반찬 입출고 현황 공유"),
        # 비정기적
        ("비정기적", "책상 위 서류", "입고, 배분", ""),
        ("비정기적", "전화응대", "자세히 알려주고 원칙에 근거해서 답하기", "블랙 전화번호 체크"),
        ("비정기적", "매장", "품목 기억 및 바코드 인식에 반영", "신규 물품 등록, 특이사항 처리"),
        ("비정기적", "바코드 인식", "엑셀 -> fms에서 인식", "찍기 전에 원하는 창을 선택하고 찍어야 함"),
        ("비정기적", "자동차 주유", "사회포탈 기안 작성", "3개 서류: 지출결의서 -> 품의서 -> 영수증"),
        # 월별
        ("월별", "초", "운영현황보고", "기안작성, 점검표 작성"),
        ("월별", "초(1일)", "제공현황 (식사권, 명단 등)", "식사권, 이용명단 정리, 온도/자동차 일지 등"),
        ("월별", "중순 이후", "배송서비스", "기안작성, 대상자 전화, 배송진행, 결과보고서"),
        ("월별", "말일", "마지막주일 후 화요일", "교회 2곳 물품 등록 및 인수증"),
        ("월별", "말일", "마지막주 (천불사)", "사진찍고 공유(안선생), 쌀 수요 파악"),
        ("월별", "말일", "안전점검표", "기안 작성 및 대리 도장"),
        ("월별", "말일", "전기용품 점검 일지", "정윤환 대리에게 공유"),
        # 분기별
        ("분기별", "캠페인", "희망나눔캠페인 현수막", "4월, 7월, 10월, 1월 매월 진행"),
        # 휴가/기타
        ("휴가/감사 준비", "서류준비", "일일마감일지 프린트", "이용자, 시설 등 내용 맞추기"),
        ("휴가/감사 준비", "정기기부처", "월별 파일철 준비", "빵, 떡 등")
    ]
    for cat, sub_cat, name, det in templates:
        add_task(user_id, cat, sub_cat, name, det)
        
def get_tasks(user_id, user_roles=None):
    """특정 사용자의 스케줄 및 공유받은 스케줄 조회"""
    if user_roles is None:
        user_roles = []
    
    allowed_shared = ["전체 공유"] + user_roles

    if st.session_state.get("firebase_inited"):
        db = st.session_state["db"]
        tasks_ref = db.collection("tasks").stream()
        res = []
        for t in tasks_ref:
            d = t.to_dict()
            if d.get("user_id") == user_id or d.get("shared_category") in allowed_shared:
                res.append(d)
        return res
    else:
        state = _load_shared_state()
        res = []
        for t in state.get("tasks", {}).values():
            if t.get("user_id") == user_id or t.get("shared_category") in allowed_shared:
                res.append(t)
        return res

def delete_task(task_id):
    """특정 스케줄 삭제"""
    if st.session_state.get("firebase_inited"):
        db = st.session_state["db"]
        db.collection("tasks").document(task_id).delete()
    else:
        state = _load_shared_state()
        if task_id in state.get("tasks", {}):
            del state["tasks"][task_id]
            _save_shared_state(state)

def update_task(task_id, new_category, new_sub_category, new_task_name, new_details, new_shared_category="개인용", new_start_date=None, new_end_date=None, new_is_recurring=False):
    """기존 스케줄의 내용 수정"""
    if st.session_state.get("firebase_inited"):
        db = st.session_state["db"]
        update_data = {
            "category": new_category,
            "sub_category": new_sub_category,
            "task_name": new_task_name,
            "details": new_details,
            "shared_category": new_shared_category,
            "is_recurring": new_is_recurring
        }
        if new_start_date: update_data["start_date"] = new_start_date
        if new_end_date: update_data["end_date"] = new_end_date
        db.collection("tasks").document(task_id).update(update_data)
    else:
        state = _load_shared_state()
        if task_id in state.get("tasks", {}):
            state["tasks"][task_id]["category"] = new_category
            state["tasks"][task_id]["sub_category"] = new_sub_category
            state["tasks"][task_id]["task_name"] = new_task_name
            state["tasks"][task_id]["details"] = new_details
            state["tasks"][task_id]["shared_category"] = new_shared_category
            state["tasks"][task_id]["is_recurring"] = new_is_recurring
            if new_start_date: state["tasks"][task_id]["start_date"] = new_start_date
            if new_end_date: state["tasks"][task_id]["end_date"] = new_end_date
            _save_shared_state(state)

def toggle_task_completion(task_id, date_str, is_completed):
    """특정 스케줄의 특정 날짜 완료 상태 토글"""
    if st.session_state.get("firebase_inited"):
        db = st.session_state["db"]
        task_ref = db.collection("tasks").document(task_id)
        task_doc = task_ref.get()
        if task_doc.exists:
            data = task_doc.to_dict()
            completed = data.get("completed_dates", {})
            if is_completed:
                completed[date_str] = True
            else:
                completed.pop(date_str, None)
            task_ref.update({"completed_dates": completed})
    else:
        state = _load_shared_state()
        if "tasks" in state and task_id in state["tasks"]:
            completed = state["tasks"][task_id].get("completed_dates", {})
            if is_completed:
                completed[date_str] = True
            else:
                completed.pop(date_str, None)
            state["tasks"][task_id]["completed_dates"] = completed
            _save_shared_state(state)

def update_task_delegation(task_id, date_str, delegated_to, status="pending"):
    """특정 스케줄의 특정 날짜에 대한 위임 상태 업데이트"""
    if st.session_state.get("firebase_inited"):
        db = st.session_state["db"]
        task_ref = db.collection("tasks").document(task_id)
        task_doc = task_ref.get()
        if task_doc.exists:
            data = task_doc.to_dict()
            delegations = data.get("delegations", {})
            if delegated_to:
                delegations[date_str] = {"delegated_to": delegated_to, "status": status}
            else:
                delegations.pop(date_str, None)
            task_ref.update({"delegations": delegations})
    else:
        state = _load_shared_state()
        if "tasks" in state and task_id in state["tasks"]:
            delegations = state["tasks"][task_id].get("delegations", {})
            if delegated_to:
                delegations[date_str] = {"delegated_to": delegated_to, "status": status}
            else:
                delegations.pop(date_str, None)
            state["tasks"][task_id]["delegations"] = delegations
            _save_shared_state(state)

# --- 방문자 특이사항 엑셀 룰 ---
def update_visitor_rules(rules_list):
    """[관리자/운영자] 엑셀 기반 동적 방문자 특이사항 및 할당 개수 규칙 저장"""
    state = _load_shared_state()
    state["visitor_rules"] = rules_list
    _save_shared_state(state)

def get_visitor_rules():
    """저장된 방문자 특이사항 규칙 조회"""
    state = _load_shared_state()
    return state.get("visitor_rules", [])

def get_user_info_by_barcode(barcode):
    """업로드된 회원 명부 기준 이용자 특성(인원, 주거, 필수물품 등) 반환"""
    state = _load_shared_state()
    users_data = state.get("user_directory", {})
    return users_data.get(barcode.strip().upper())

def update_user_directory(users_data):
    """업로드된 이용자 명단 전체 캐싱 (기존 데이터 덮어쓰기)"""
    state = _load_shared_state()
    state["user_directory"] = users_data
    _save_shared_state(state)

def update_barcode_rules_bulk(rules_dict):
    """업로드된 물품 바코드 룰 일괄 병합 (기존 유지 + 새 항목 덮어쓰기)"""
    state = _load_shared_state()
    if "barcode_rules" not in state:
        state["barcode_rules"] = {}
    
    # 딕셔너리 병합 (Merge)
    for k, v in rules_dict.items():
        state["barcode_rules"][k] = v
        
    _save_shared_state(state)

def get_fms_master():
    """저장된 FMS 마스터 재고 리스트 조회"""
    state = _load_shared_state()
    return state.get("fms_master", [])

def update_fms_master(fms_list):
    """FMS 마스터 재고 리스트 캐싱 (덮어쓰기)"""
    state = _load_shared_state()
    state["fms_master"] = fms_list
    _save_shared_state(state)

def get_geodream_theme():
    state = _load_shared_state()
    return state.get("geodream_theme", {
        "bg_color": "#D7E4D3",
        "tooltip_bg": "rgba(30, 42, 33, 0.95)",
        "tooltip_text": "#F0E6D2",
        "highlight_color": "#E6D8A7",
        "font_family": "'Noto Sans KR', sans-serif"
    })

def update_geodream_theme(theme_dict):
    state = _load_shared_state()
    state["geodream_theme"] = theme_dict
    _save_shared_state(state)

def get_admin_cards():
    state = _load_shared_state()
    default_cards = [
        {"id": "users", "icon": "👥", "title": "사용자 권한 관리", "desc": "가입된 사용자의 역할을 설정하고 계정을 영구 삭제합니다."},
        {"id": "space", "icon": "🏗️", "title": "공간 및 평면도 관리", "desc": "실사 구역을 텍스트로 정의하고, 평면도를 에디터로 디자인합니다."},
        {"id": "fms", "icon": "📈", "title": "FMS 기준재고 엑셀", "desc": "기준 재고 엑셀을 업로드하고 전산에 자동 동기화합니다."},
        {"id": "audit", "icon": "🔍", "title": "재고 실사 및 POS 로그", "desc": "누가 언제 재고를 조작했는지 Audit Trail을 확인합니다."},
        {"id": "portal", "icon": "🎨", "title": "메인 포털 디자인", "desc": "첫 화면의 안내 문구, 폰트 크기, 옵션을 설정합니다."},
        {"id": "sitemap", "icon": "🗺️", "title": "사이트맵 및 안내", "desc": "전체 서비스의 페이지별 안내 텍스트를 관리합니다."},
        {"id": "public_guide", "icon": "📱", "title": "퍼블릭 가이드 관리", "desc": "비회원용 단계별 이용 안내 콘텐츠를 작성합니다."},
        {"id": "fonts", "icon": "🔠", "title": "커스텀 폰트 매니저", "desc": "무료 폰트 파일(.ttf)을 서버에 직접 업로드합니다."},
        {"id": "geodream_theme", "icon": "🎨", "title": "그냥드림 데이터맵 테마", "desc": "은평구 데이터맵 UI의 색상과 폰트를 커스터마이징합니다."}
    ]
    return state.get("admin_cards", default_cards)

def update_admin_cards(cards_list):
    _check_permission(["admin"])
    state = _load_shared_state()
    state["admin_cards"] = cards_list
    _save_shared_state(state)

def get_user_card_order(user_id):
    if not user_id:
        return []
    state = _load_shared_state()
    return state.get("user_card_orders", {}).get(user_id, [])

def update_user_card_order(user_id, order_list):
    if not user_id:
        return
    _check_permission(["admin"])
    state = _load_shared_state()
    if "user_card_orders" not in state:
        state["user_card_orders"] = {}
    state["user_card_orders"][user_id] = order_list
    _save_shared_state(state)
