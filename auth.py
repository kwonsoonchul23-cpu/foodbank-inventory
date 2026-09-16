import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import hashlib

def init_firebase():
    """Firebase Admin SDK 초기화. 실패 시 더미(Mock) 모드로 동작."""
    if "firebase_inited" not in st.session_state:
        if not firebase_admin._apps:
            try:
                # secrets.toml에서 firebase 키값 가져오기
                firebase_secrets = dict(st.secrets["firebase"])
                # 더미 키인 경우 의도적으로 실패 유도
                if firebase_secrets.get("project_id") == "your-project-id":
                    raise ValueError("Firebase 키가 기본값(your-project-id)입니다. 실제 키로 변경해주세요.")
                
                cred = credentials.Certificate(firebase_secrets)
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
