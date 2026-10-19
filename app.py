import streamlit as st
import streamlit as st

# --- 여기서부터 복사해서 붙여넣으세요 ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if not st.session_state["password_correct"]:
        st.warning("🔒 테스트 기간 전용 접속 페이지입니다.")
        pwd = st.text_input("비밀번호를 입력하세요", type="password")
        if pwd == "a023541377!": # 이 부분을 원하는 비밀번호로 변경하세요
            st.session_state["password_correct"] = True
            st.rerun()
        elif pwd:
            st.error("비밀번호가 일치하지 않습니다.")
        return False
    return True

if not check_password():
    st.stop() # 비밀번호를 맞추기 전까지 아래 코드는 숨겨집니다.
# --- 여기까지 ---



from auth import init_firebase, login_user, signup_user
from db import get_sitemap_config

st.set_page_config(page_title="푸드뱅크 ERP", layout="wide", initial_sidebar_state="expanded")

# Firebase 초기화
init_firebase()

if "user_id" not in st.session_state:
    st.session_state["user_id"] = None
    st.session_state["role"] = None
    st.session_state["name"] = None

# 다크/라이트 테마 토글 버튼 (CSS 주입)
if "theme" not in st.session_state:
    st.session_state["theme"] = "Light"

def toggle_theme():
    st.session_state["theme"] = "Dark" if st.session_state["theme"] == "Light" else "Light"

st.sidebar.button(f"🎨 현재 테마: {st.session_state['theme']} (클릭하여 변경)", on_click=toggle_theme)

@st.dialog("🗺️ 사이트맵 및 페이지 이용 안내")
def show_sitemap():
    sitemap = get_sitemap_config()
    st.write(sitemap.get("description", ""))
    st.divider()
    for page in sitemap.get("pages", []):
        st.markdown(f"**📌 {page.get('name', '')}**")
        st.info(page.get("purpose", ""))

if st.sidebar.button("🗺️ 사이트맵 (이용 안내)"):
    show_sitemap()

if st.session_state["theme"] == "Dark":
    st.markdown("""
        <style>
            .stApp {
                background-color: #121212;
                color: #FFFFFF;
            }
        </style>
    """, unsafe_allow_html=True)
    
def logout():
    st.session_state["user_id"] = None
    st.session_state["role"] = None
    st.session_state["name"] = None
    st.rerun()

# ----------------- 미인증 포털 화면 -----------------
if not st.session_state["user_id"]:
    if "portal_view" not in st.session_state:
        st.session_state["portal_view"] = "main"
    if "guide_step" not in st.session_state:
        st.session_state["guide_step"] = 0

    if st.session_state["portal_view"] == "main":
        import time
        from db import get_portal_config
        
        portal_config = get_portal_config()
        options = portal_config.get("options", [])
        
        def on_portal_change():
            selected = st.session_state.get("portal_radio")
            if selected:
                time.sleep(0.4)
                st.session_state["portal_view"] = selected
                st.session_state["guide_step"] = 0
                st.session_state["portal_radio"] = None

        # 동적 CSS 생성
        num_options = len(options) if len(options) > 0 else 1
        slider_width_pct = 100 / num_options
        slider_icon = portal_config.get("slider_icon", "✏️")
        subtitle_size = portal_config.get("subtitle_size", 24)
        slider_width_pc = portal_config.get("slider_width_pc", 600)
        slider_width_mobile_pct = portal_config.get("slider_width_mobile_pct", 95)
        slider_font_size = portal_config.get("slider_font_size", 1.2)
        
        dynamic_css = f"""
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
        
        .portal-wrapper {{
            font-family: 'Pretendard', sans-serif;
            word-break: keep-all;
            text-align: center;
        }}
        
        .portal-subtitle {{
            color: #7f8c8d;
            font-size: {subtitle_size}px;
            margin-bottom: 50px;
            margin-top: 30px;
            font-weight: 700;
        }}
        
        div[role="radiogroup"] {{
            display: flex !important;
            flex-direction: row !important;
            background: #f1f5f9 !important;
            border-radius: 50px !important;
            padding: 5px !important;
            position: relative !important;
            margin: 0 auto 50px auto !important;
            width: {slider_width_pc}px !important;
            max-width: 98vw !important;
            box-shadow: inset 0 2px 10px rgba(0,0,0,0.05);
        }}
        
        @media (max-width: 768px) {{
            div[role="radiogroup"] {{
                width: {slider_width_mobile_pct}vw !important;
            }}
        }}
        
        div[role="radiogroup"]::before {{
            content: "" !important;
            position: absolute !important;
            top: 5px !important;
            left: 5px !important;
            width: calc({slider_width_pct}% - {10 / num_options}px) !important;
            height: calc(100% - 10px) !important;
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%) !important;
            border-radius: 50px !important;
            box-shadow: 0 10px 25px rgba(0, 198, 255, 0.4) !important;
            transition: all 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
            z-index: 1 !important;
        }}
        """
        
        # 각 옵션 위치별 슬라이더 이동 위치 CSS 동적 추가
        for i in range(1, num_options + 1):
            dynamic_css += f"""
        div[role="radiogroup"]:has(label:nth-child({i}) input:checked)::before {{
            transform: translateX(calc(100% * {i-1} + {(i-1) * 2}px)) !important;
        }}
        """
        
        dynamic_css += """
        div[role="radiogroup"] > label {
            flex: 1 !important;
            text-align: center !important;
            justify-content: center !important;
            padding: 20px 0 !important;
            z-index: 2 !important;
            cursor: pointer !important;
            margin: 0 !important;
        }
        
        div[role="radiogroup"] > label p {
            font-weight: 700 !important;
            color: #7f8c8d !important;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
            margin: 0 !important;
            font-size: {slider_font_size}rem !important;
        }}

        div[role="radiogroup"] > label:has(input:checked) p {
            color: #ffffff !important;
            transform: scale(1.25) !important;
            text-shadow: 0 2px 10px rgba(0,0,0,0.2) !important;
            z-index: 3 !important;
        }

        div[role="radiogroup"] > label > div:first-child {
            display: none !important;
        }
        """

        st.markdown(f"<style>{dynamic_css}</style>", unsafe_allow_html=True)
        
        st.markdown("<br><br>", unsafe_allow_html=True)
        col_img1, col_img2, col_img3 = st.columns([1, 2, 1])
        with col_img2:
            try:
                st.image(portal_config.get("gif_path", "basic/hello.gif"), use_container_width=True)
            except Exception:
                pass 

        subtitle = portal_config.get("subtitle", "이용하실 서비스를 선택해주세요")
        st.markdown(f"""
        <div class="portal-wrapper">
            <p class="portal-subtitle">{subtitle}</p>
        </div>
        """, unsafe_allow_html=True)
        
        if options:
            st.radio(
                "서비스 선택",
                options=options,
                index=None,
                key="portal_radio",
                label_visibility="collapsed",
                on_change=on_portal_change
            )
        else:
            st.warning("등록된 이용자 선택지가 없습니다. 관리자 모드에서 추가해주세요.")
        
        st.markdown("<br><hr>", unsafe_allow_html=True)
        with st.expander("💼 관리자 및 직원 로그인"):
            tab1, tab2 = st.tabs(["🔑 로그인", "📝 회원가입"])
            with tab1:
                with st.form("login_form"):
                    user_id = st.text_input("아이디")
                    password = st.text_input("비밀번호", type="password")
                    if st.form_submit_button("로그인"):
                        user_data = login_user(user_id, password)
                        if user_data:
                            st.session_state["user_id"] = user_data["user_id"]
                            st.session_state["name"] = user_data["name"]
                            st.session_state["role"] = user_data["role"]
                            st.success(f"{user_data['name']}님 환영합니다!")
                            st.rerun()
                        else:
                            st.error("아이디 또는 비밀번호 불일치")
            with tab2:
                with st.form("signup_form"):
                    new_id = st.text_input("새 아이디")
                    new_pw = st.text_input("비밀번호", type="password")
                    new_name = st.text_input("이름")
                    if st.form_submit_button("가입하기"):
                        if signup_user(new_id, new_pw, new_name):
                            st.success("가입 완료!")
                        else:
                            st.error("이미 존재하는 아이디입니다.")

    elif st.session_state["portal_view"] != "main":
        from db import get_public_guides, get_portal_config, get_category_styles
        import os, base64
        
        guides = get_public_guides()
        portal_config = get_portal_config()
        category_styles = get_category_styles()
        
        current_cat = st.session_state["portal_view"]
        current_guide = guides.get(current_cat, [])
        
        cat_style = category_styles.get(current_cat, {
            "font_family": "Pretendard (기본)",
            "title_color": "#2196F3",
            "title_size": 24,
            "content_color": "#2c3e50",
            "content_size": 18
        })
        
        font_family_css = "'Pretendard', sans-serif"
        custom_font_css = ""
        if cat_style["font_family"] != "Pretendard (기본)":
            font_path = os.path.join("basic/fonts", cat_style["font_family"])
            if os.path.exists(font_path):
                with open(font_path, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode()
                ext = os.path.splitext(font_path)[1].lower()
                mime = "font/woff2" if ext == ".woff2" else "font/woff" if ext == ".woff" else "font/ttf"
                custom_font_css = f"""
                @font-face {{
                    font-family: 'CustomCategoryFont';
                    src: url(data:{mime};base64,{encoded});
                }}
                """
                font_family_css = "'CustomCategoryFont', sans-serif"
        
        if st.button("⬅️ 처음으로 돌아가기"):
            st.session_state["portal_view"] = "main"
            st.rerun()
            
        st.markdown(f"""
        <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
        {custom_font_css}
        
        .guide-container {{
            font-family: {font_family_css};
            word-break: keep-all; /* 단어 단위로 줄바꿈 */
            overflow-wrap: break-word;
            white-space: pre-wrap; /* 엔터 띄어쓰기 반영 */
        }}
        
        .guide-card {{
            background: #ffffff;
            border-radius: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.08);
            padding: 30px;
            font-size: {cat_style['content_size']}px;
            line-height: 1.6;
            letter-spacing: -0.5px;
            color: {cat_style['content_color']};
            margin-top: 15px;
            border: 1px solid rgba(0,0,0,0.03);
        }}
        
        .guide-title {{
            text-align: center;
            color: {cat_style['title_color']};
            font-size: {cat_style['title_size']}px;
            font-weight: 700;
        }}
        
        @media screen and (max-width: 768px) {{
            .guide-card {{
                padding: 20px;
                font-size: {max(14, cat_style['content_size'] - 2)}px;
                word-break: normal;
            }}
            .guide-title {{
                font-size: {max(18, cat_style['title_size'] - 4)}px;
            }}
        }}
        </style>
        """, unsafe_allow_html=True)
        
        step_idx = st.session_state["guide_step"]
        if not current_guide:
            st.warning("아직 이 이용자를 위해 준비된 안내 내용이 없습니다. 관리자에게 문의해주세요.")
        elif step_idx < len(current_guide):
            step_data = current_guide[step_idx]
            
            # Progress bar
            progress = (step_idx + 1) / len(current_guide)
            st.progress(progress)
            st.markdown(f"<div class='guide-container'><p style='text-align: right; color: #7f8c8d;'><b>{step_idx + 1} / {len(current_guide)} 단계</b></p></div>", unsafe_allow_html=True)
            
            st.markdown(f"<div class='guide-container'><h2 class='guide-title'>{step_data.get('title', '')}</h2></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='guide-container guide-card'>\n\n{step_data.get('content', '')}\n\n</div>", unsafe_allow_html=True)
            
            media_url = step_data.get("media_url", "")
            if media_url:
                st.markdown("<br>", unsafe_allow_html=True)
                if "youtube.com" in media_url or "youtu.be" in media_url:
                    st.video(media_url, autoplay=True, loop=True, muted=True)
                elif media_url.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                    st.image(media_url, use_column_width=True)
                else:
                    st.markdown(f"🔗 [참고 링크 열기]({media_url})")
            
            st.markdown("<br><br>", unsafe_allow_html=True)
            if st.button("✅ 완료했습니다 (다음 단계로)", use_container_width=True, type="primary"):
                st.session_state["guide_step"] += 1
                st.rerun()
        else:
            st.success("🎉 모든 단계를 완료하셨습니다!")
            st.balloons()
            if st.button("🔄 다시 시작하기", use_container_width=True):
                st.session_state["guide_step"] = 0
                st.rerun()

    st.stop()

# ----------------- 로그인 후 라우팅 -----------------
user_disp_name = st.session_state.get('name') or '사용자'
st.sidebar.write(f"👤 **{user_disp_name}**님")
st.sidebar.write(f"*(권한: {st.session_state['role']})*")
if st.sidebar.button("로그아웃"):
    logout()

# 페이지 라우팅 정의 (Streamlit >= 1.36.0 의 st.navigation 활용)
pages = []
roles = st.session_state["role"]

# 이전 단일 문자열 권한과의 호환성 처리
if isinstance(roles, str):
    roles = [roles]
if not roles:
    roles = ["user"]

if "admin" in roles:
    st.sidebar.markdown("---")
    st.sidebar.markdown("**관리자 전용**")
    pages.append(st.Page("views/admin.py", title="관리자 대시보드", icon="⚙️"))
    pages.append(st.Page("views/geodream.py", title="그냥드림 데이터맵", icon="🗺️"))
    pages.append(st.Page("views/operator.py", title="현장운영 (웹 POS)", icon="🛒"))
    pages.append(st.Page("views/inventory.py", title="재고관리 실사", icon="📱"))
else:
    # 각 권한별 페이지 추가 (중복 권한 허용)
    if "operator" in roles:
        pages.append(st.Page("views/operator.py", title="현장운영 (웹 POS)", icon="🛒"))
    if "inventory" in roles:
        pages.append(st.Page("views/inventory.py", title="재고관리 실사", icon="📱"))

# 모든 로그인 사용자 공통 페이지 (개인 스케줄 및 프로필)
pages.append(st.Page("views/schedule.py", title="내 스케줄 & 할 일", icon="🗓️"))
pages.append(st.Page("views/profile.py", title="프로필 & 휴일 관리", icon="👤"))
if not pages:
    # 권한 미부여 상태
    st.warning("아직 시스템 접근 권한(현장운영/재고관리)을 부여받지 못했습니다. 관리자에게 문의하세요.")
    st.stop()

pg = st.navigation(pages)
pg.run()
