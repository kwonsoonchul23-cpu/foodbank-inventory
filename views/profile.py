import streamlit as st
from db import get_all_users_info, update_user_profile, get_holidays, update_holidays
import datetime

def render_profile_page():
    st.title("👤 프로필 및 휴일 관리")
    st.markdown("대체자 지정 시 사용할 프로필 사진과 이름을 설정하고, 전사적인 휴일/휴가를 관리합니다.")
    
    user_id = st.session_state.get("user_id")
    if not user_id:
        st.error("로그인이 필요합니다.")
        return

    # 1. 내 프로필 설정
    st.header("내 프로필 설정")
    all_users = get_all_users_info()
    my_info = next((u for u in all_users if u["id"] == user_id), None)
    
    if my_info:
        with st.form("my_profile_form"):
            col1, col2 = st.columns([1, 3])
            with col1:
                if my_info.get("profile_image"):
                    st.image(my_info["profile_image"], width=100)
                else:
                    st.markdown("**(사진 없음)**")
                new_img_url = st.text_input("프로필 이미지 URL", value=my_info.get("profile_image", ""))
            with col2:
                new_name = st.text_input("표시 이름", value=my_info.get("name", user_id))
            
            # 일반 유저는 자신의 노출 여부를 바꾸지 못하게 할 수도 있지만 일단 유지 (is_visible)
            # 관리자만 강제 변경 가능하게 처리
            submit_profile = st.form_submit_button("프로필 저장", type="primary")
            if submit_profile:
                update_user_profile(user_id, new_name, my_info.get("is_visible", True), new_img_url)
                st.success("프로필이 업데이트되었습니다.")
                st.rerun()
                
    st.divider()
    
    # 2. 관리자 권한 - 전체 사용자 프로필 및 노출 여부 관리
    roles = st.session_state.get("role", [])
    is_admin = "admin" in roles if isinstance(roles, list) else roles == "admin"
    
    if is_admin:
        st.header("🛡️ [관리자 전용] 사용자 프로필 관리")
        st.caption("대체자 목록에 표시될 사용자 리스트와 노출 여부를 관리합니다.")
        
        for u in all_users:
            with st.container():
                c1, c2, c3 = st.columns([1, 2, 1])
                with c1:
                    if u.get("profile_image"):
                        st.image(u["profile_image"], width=50)
                    else:
                        st.markdown("*(No Image)*")
                with c2:
                    st.markdown(f"**{u['name']}** (`{u['id']}`)")
                with c3:
                    chk_key = f"visible_{u['id']}"
                    def toggle_visible(target_id=u['id'], name=u['name'], img=u.get('profile_image', ''), key=chk_key):
                        update_user_profile(target_id, name, st.session_state[key], img)
                    
                    st.checkbox("대체자 목록에 노출", value=u.get("is_visible", True), key=chk_key, on_change=toggle_visible)
            st.divider()

    # 3. 휴무/공휴일 (스케줄 제외 일자) 관리
    st.header("🏖️ 휴무 및 공휴일 (스케줄 제외) 관리")
    st.caption("이곳에 등록된 날짜는 반복 스케줄(Gantt)의 가로 바가 그려지지 않습니다.")
    
    current_holidays = get_holidays()
    
    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        new_holiday = st.date_input("휴무일/공휴일 지정", value=datetime.date.today())
    with col_h2:
        st.write("") # 띄어쓰기
        st.write("")
        if st.button("추가하기"):
            h_str = new_holiday.strftime("%Y-%m-%d")
            if h_str not in current_holidays:
                current_holidays.append(h_str)
                update_holidays(sorted(current_holidays))
                st.success(f"{h_str}이(가) 휴무일로 추가되었습니다.")
                st.rerun()
            else:
                st.warning("이미 등록된 날짜입니다.")
                
    if current_holidays:
        st.subheader("등록된 휴무일 목록")
        for h in current_holidays:
            col_d1, col_d2 = st.columns([3, 1])
            col_d1.write(f"📅 **{h}**")
            if col_d2.button("삭제", key=f"del_h_{h}"):
                current_holidays.remove(h)
                update_holidays(current_holidays)
                st.rerun()

render_profile_page()
