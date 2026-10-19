import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
import hashlib

def init_firebase():
    """Firebase Admin SDK 초기화. 실패 시 더미(Mock) 모드로 동작."""
    if "firebase_inited" not in st.session_state or not st.session_state["firebase_inited"]:
        # 이미 파이어베이스가 연결되어 있는지 확인 (중복 실행 방지 에러 해결)
        if not firebase_admin._apps:
            try:
                # 1. 클라우드 환경(st.secrets 금고)에 열쇠가 있는 경우
                if "FIREBASE_KEY" in st.secrets:
                    key_val = st.secrets["FIREBASE_KEY"]
                    key_dict = json.loads(key_val) if isinstance(key_val, str) else dict(key_val)
                    cred = credentials.Certificate(key_dict)
                # 2. 로컬 컴퓨터(내 PC) 환경인 경우
                else:
                    # 기존에 쓰시던 json 파일 이름을 정확히 넣어주세요
                    key_file = "firebase_key.json"
                    key_path = os.path.join(os.path.dirname(__file__), key_file) if os.path.exists(os.path.join(os.path.dirname(__file__), key_file)) else key_file
                    cred = credentials.Certificate(key_path)

                firebase_admin.initialize_app(cred)
                st.session_state["firebase_inited"] = True
                st.session_state["db"] = firestore.client()
            except Exception as e:
                st.session_state["firebase_inited"] = False
                # 기본 관리자 계정이 없으면 shared_state.json에 초기화
                from db import _load_shared_state
                state = _load_shared_state()
                if "users" not in state or not state["users"]:
                    state["users"] = {}
                    _create_mock_user_in_state(state, "admin", "admin123", "관리자", ["admin"])
                    _create_mock_user_in_state(state, "operator", "op123", "현장운영", ["operator"])
                    _create_mock_user_in_state(state, "inventory", "inv123", "재고관리", ["inventory"])
                    from db import _save_shared_state
                    _save_shared_state(state)
                print(f"Firebase Init Error: {e}. Running in Mock Mode (JSON).")
        else:
            st.session_state["firebase_inited"] = True
            st.session_state["db"] = firestore.client()

def _hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def _create_mock_user_in_state(state, user_id, password, name, role):
    state["users"][user_id] = {
        "user_id": user_id,
        "password": _hash_password(password),
        "name": name,
        "role": role
    }

def login_user(user_id, password):
    """사용자 로그인 검증"""
    hashed_pw = _hash_password(password)
    
    if st.session_state.get("firebase_inited"):
        db = st.session_state["db"]
        user_ref = db.collection("users").document(user_id).get()
        if user_ref.exists:
            user_data = user_ref.to_dict()
            if user_data.get("password") == hashed_pw:
                return user_data
    else:
        # Mock DB
        from db import _load_shared_state
        state = _load_shared_state()
        user_data = state.get("users", {}).get(user_id)
        if user_data and user_data.get("password") == hashed_pw:
            return user_data
    return None

def signup_user(user_id, password, name):
    """자유 가입 (기본적으로 'user' 권한 부여, 관리자가 나중에 수정 가능)"""
    hashed_pw = _hash_password(password)
    new_user = {
        "user_id": user_id,
        "password": hashed_pw,
        "name": name,
        "role": ["user"] # 다중 권한을 위해 리스트 구조로 변경
    }
    
    if st.session_state.get("firebase_inited"):
        db = st.session_state["db"]
        user_ref = db.collection("users").document(user_id)
        if user_ref.get().exists:
            return False # 이미 존재함
        user_ref.set(new_user)
        return True
    else:
        from db import _load_shared_state, _save_shared_state
        state = _load_shared_state()
        if "users" not in state:
            state["users"] = {}
        if user_id in state["users"]:
            return False
        state["users"][user_id] = new_user
        _save_shared_state(state)
        return True
