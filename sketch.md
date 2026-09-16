import streamlit as st

st.set_page_config(layout="wide")
st.title("📦 재고 파악 시스템 - 공간별 평면도 대시보드")

# 세 개의 공간을 탭으로 분리
tab1, tab2, tab3 = st.tabs(["🛒 장소 1: 진열대", "🏢 장소 2: 지하 창고", "🅿️ 장소 3: 주차장"])

# 공통 스타일 (CSS)
style = """
<style>
    .space-container { font-family: 'Arial', sans-serif; padding: 20px; background-color: #f8f9fa; border-radius: 10px; border: 2px solid #dee2e6; }
    .grid-container { display: grid; gap: 15px; position: relative; padding: 10px; background: white; border-radius: 8px; border: 1px dashed #ced4da; }
    .zone { background-color: #e9ecef; border: 2px solid #adb5bd; border-radius: 6px; padding: 15px; text-align: center; font-weight: bold; font-size: 14px; color: #495057; display: flex; align-items: center; justify-content: center; }
    .door { background-color: #ffe3e3; border-color: #ffa8a8; color: #e03131; }
    .pallet { background-color: #e3faf2; border-color: #96f2d7; color: #0ca678; }
    .office { background-color: #edf2ff; border-color: #bac8ff; color: #3b5bdb; }
    .storage { background-color: #fff4e6; border-color: #ffd8a8; color: #d9480f; }
    .arrow { font-size: 20px; color: #dee2e6; text-align: center; align-self: center; justify-self: center; }
</style>
"""

with tab1:
    st.subheader("장소 1: 진열대 동선 도면")
    # 진열대 HTML 구조
    html_display = style + """
    <div class='space-container'>
        <div class='grid-container' style='grid-template-columns: repeat(7, 1fr); grid-template-rows: repeat(4, auto);'>
            <div class='zone'>진열매대 C</div>
            <div class='arrow'>◀━━</div>
            <div class='zone'>서비스 매대 B</div>
            <div class='arrow'>◀━━</div>
            <div class='zone'>서비스 매대 A</div>
            <div class='arrow'>◀━━</div>
            <div class='zone'>진열매대 B</div>
            
            <div class='arrow'>┃<br>▼</div>
            <div colspan='5'></div>
            <div class='zone storage'>재고 A</div>
            
            <div class='zone'>진열매대 D</div>
            <div colspan='5'></div>
            <div class='zone'>진열매대 A</div>
            
            <div class='arrow'>┃<br>▼</div>
            <div colspan='6'></div>
            
            <div class='zone'>진열매대 E</div>
            <div colspan='6'></div>
            
            <div class='arrow'>┃<br>▼</div>
            <div colspan='6'></div>
            
            <div class='zone door'>🚪 퇴실구</div>
            <div class='arrow'>━━➔</div>
            <div class='zone'>서비스 매대 C</div>
            <div class='arrow'>━━➔</div>
            <div class='zone door' style='grid-column: span 3;'>🚪 출입구</div>
        </div>
    </div>
    """
    st.components.v1.html(html_display, height=500)

with tab2:
    st.subheader("장소 2: 지하 창고 레이아웃")
    # 지하 창고 HTML 구조
    html_warehouse = style + """
    <div class='space-container'>
        <div class='grid-container' style='grid-template-columns: repeat(6, 1fr);'>
            <div class='zone pallet'>파렛트 E</div>
            <div class='arrow'>━━➔</div>
            <div class='zone pallet'>파렛트 D</div>
            <div class='zone office'>사무용 A</div>
            <div class='zone office'>사무용 B</div>
            <div class='zone office'>사무용 C</div>
            
            <div class='arrow'>▲<br>┃</div>
            <div></div>
            <div class='arrow'>┃<br>▼</div>
            <div class='zone door'>🚪 출입구</div>
            <div colspan='2'></div>
            
            <div class='zone pallet'>파렛트 C</div>
            <div></div>
            <div class='arrow'>┃<br>▼</div>
            <div class='zone door'>🚪 퇴실구</div>
            <div class='zone office' style='grid-column: span 2;'>사무용 D</div>
            
            <div class='arrow'>▲<br>┃</div>
            <div></div>
            <div class='arrow'>┃<br>▼</div>
            <div colspan='3'></div>
            
            <div class='zone pallet'>파렛트 A</div>
            <div class='arrow'>━━➔</div>
            <div class='zone pallet'>파렛트 B</div>
            <div class='zone storage' style='grid-column: span 2;'>❄️ 냉장 창고</div>
            <div class='zone storage'>🔥 냉동 창고</div>
            
            <div class='zone door' style='grid-column: span 2; margin-top: 15px;'>🚪 메인 출입구</div>
            <div class='zone door' style='grid-column: span 2; margin-top: 15px;'>🚪 메인 퇴실구</div>
        </div>
    </div>
    """
    st.components.v1.html(html_warehouse, height=550)

with tab3:
    st.subheader("장소 3: 주차장 배치도")
    # 주차장 HTML 구조
    html_parking = style + """
    <div class='space-container'>
        <div class='grid-container' style='grid-template-columns: repeat(3, 1fr); padding: 40px 10px;'>
            <div class='zone' style='height: 150px; background-color: #fff9db; border-color: #fab005; color: #f08c00;'>🚚 탑차 (구식)</div>
            <div class='zone' style='height: 150px; background-color: #e8f5e9; border-color: #4caf50; color: #2e7d32;'>🚗 승용차</div>
            <div class='zone' style='height: 150px; background-color: #e3f2fd; border-color: #2196f3; color: #1565c0;'>🚛 탑차 (신식)</div>
        </div>
    </div>
    """
    st.components.v1.html(html_parking, height=300)