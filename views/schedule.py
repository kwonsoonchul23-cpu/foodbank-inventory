import streamlit as st
import datetime
import calendar
import streamlit.components.v1 as components
from db import add_task, get_tasks, delete_task, toggle_task_completion, load_template_tasks, update_task, get_all_users_info, update_task_delegation, get_holidays

@st.dialog("일정 대체자 지정")
def delegate_task_dialog(task):
    st.write(f"**{task['task_name']}** 일정 대체")
    st.write("휴가, 공휴일 등으로 인해 본인이 수행할 수 없는 특정 일자를 지정하여 다른 사람에게 위임합니다.")
    
    del_date = st.date_input("대체할 날짜", value=datetime.date.today())
    all_users = get_all_users_info()
    my_id = st.session_state.get("user_id")
    
    # 노출 허락된 다른 사용자만 필터링
    other_users = [u for u in all_users if u["id"] != my_id and u.get("is_visible", True)]
    
    if not other_users:
        st.warning("대체 가능한 다른 사용자(프로필 공개)가 없습니다.")
        return
        
    # 프로필을 보기 좋게 선택할 수 있도록 format_func 사용
    user_options = {u["id"]: f"{u['name']} ({u['id']})" for u in other_users}
    del_user_id = st.selectbox("대체자 선택", list(user_options.keys()), format_func=lambda x: user_options[x])
    
    selected_user = next((u for u in other_users if u["id"] == del_user_id), None)
    if selected_user and selected_user.get("profile_image"):
        st.image(selected_user["profile_image"], width=50)
    
    if st.button("대체 지정하기", type="primary"):
        update_task_delegation(task["task_id"], str(del_date), del_user_id, status="pending")
        st.success(f"{del_date} 일정을 {user_options[del_user_id]}님에게 위임 요청했습니다!")
        st.rerun()

@st.dialog("스케줄 추가/수정")
def edit_task_dialog(task=None, user_id=None):
    role_map = {
        "개인용": "개인용 (공유 안 함)",
        "전체 공유": "전체 공유 (모두에게)",
        "operator": "현장운영 (operator) 공유",
        "inventory": "재고관리 (inventory) 공유",
        "schedule": "스케줄 관리자 공유",
        "admin": "총괄 관리자 공유"
    }
    inverse_map = {v: k for k, v in role_map.items()}
    
    is_edit = task is not None
    st.write(f"**{'스케줄 수정' if is_edit else '새 스케줄 추가'}**")
    
    cat_val = task.get("category", "") if is_edit else ""
    sub_val = task.get("sub_category", "") if is_edit else ""
    name_val = task.get("task_name", "") if is_edit else ""
    det_val = task.get("details", "") if is_edit else ""
    is_rec_val = task.get("is_recurring", False) if is_edit else False
    
    today = datetime.date.today()
    if is_edit and task.get("start_date"):
        try:
            start_val = datetime.datetime.strptime(task["start_date"], "%Y-%m-%d").date()
        except: start_val = today
    else: start_val = today
    
    if is_edit and task.get("end_date"):
        try:
            end_val = datetime.datetime.strptime(task["end_date"], "%Y-%m-%d").date()
        except: end_val = start_val
    else: end_val = start_val
    
    col1, col2 = st.columns(2)
    with col1:
        new_cat = st.text_input("상위 분류 (프로젝트명)", value=cat_val)
        new_start = st.date_input("시작일", value=start_val)
    with col2:
        new_sub = st.text_input("하위 분류 (태그/단계)", value=sub_val)
        new_end = st.date_input("종료일 (반복 시 인수인계 등 종료 시점)", value=end_val)
        
    new_name = st.text_input("스케줄명 (필수)", value=name_val)
    new_det = st.text_input("상세 설명", value=det_val)
    
    current_shared = task.get("shared_category", "전체 공유") if is_edit else "전체 공유"
    if current_shared not in role_map:
        role_map[current_shared] = f"기타 ({current_shared})"
        inverse_map[f"기타 ({current_shared})"] = current_shared
        
    new_shared_label = st.selectbox("공유 범위", list(role_map.values()), index=list(role_map.keys()).index(current_shared))
    new_is_recurring = st.checkbox("꾸준히 진행 (반복 스케줄)", value=is_rec_val, help="시작일부터 종료일까지 휴무일을 제외하고 매일 타임라인에 유지됩니다.")
    
    if st.button("저장하기" if is_edit else "추가하기", type="primary"):
        if new_name.strip() and new_cat.strip():
            new_shared = inverse_map[new_shared_label]
            if is_edit:
                update_task(task["task_id"], new_cat.strip(), new_sub.strip(), new_name.strip(), new_det.strip(), new_shared, str(new_start), str(new_end), new_is_recurring)
                st.success("수정되었습니다!")
            else:
                add_task(user_id, new_cat.strip(), new_sub.strip(), new_name.strip(), new_det.strip(), new_shared, str(new_start), str(new_end), new_is_recurring)
                st.success("추가되었습니다!")
            st.rerun()
        else:
            st.error("상위 분류와 스케줄명은 필수입니다.")

def build_gantt_html(tasks, year, month, show_past_dates=False):
    num_days = calendar.monthrange(year, month)[1]
    today = datetime.date.today()
    month_start = datetime.date(year, month, 1)
    month_end = datetime.date(year, month, num_days)
    
    chart_start_date = month_start
    if not show_past_dates and year == today.year and month == today.month:
        chart_start_date = max(month_start, today)
        
    visible_days = (month_end - chart_start_date).days + 1
    
    # If the entire month is in the past and we hide past dates, show a message instead of an empty chart.
    if visible_days <= 0:
        return "<div style='padding:20px; text-align:center; color:#888;'>이 달의 모든 일정이 지났습니다. 지난 일정 보기를 켜주세요.</div>"
    holidays = get_holidays()
    
    # CSS & HTML Header
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
    body {{ font-family: 'Noto Sans KR', sans-serif; background: #fff; margin:0; padding:0; }}
    .gantt-wrapper {{ display: flex; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
    .left-panel {{ width: 250px; background: #fafafa; border-right: 1px solid #e0e0e0; flex-shrink: 0; }}
    .right-panel {{ flex-grow: 1; overflow-x: auto; background: #fff; }}
    .header-row {{ display: flex; height: 50px; border-bottom: 1px solid #e0e0e0; background: #f4f5f7; }}
    .header-cell {{ flex: 1; min-width: 35px; text-align: center; font-size: 11px; color: #5e6c84; font-weight: bold; border-right: 1px dotted #ebecf0; padding-top: 8px; line-height:1.2; }}
    .header-cell span {{ font-size: 16px; color: #172b4d; display:block; }}
    .header-cell.weekend {{ background: #fafbfc; color: #ff5630; }}
    .task-row {{ display: flex; height: 40px; border-bottom: 1px solid #f4f5f7; align-items: center; position: relative; transition: background 0.2s; }}
    .task-row:hover {{ background: #f4f5f7; }}
    .left-cell {{ padding: 0 15px; font-size: 13px; font-weight: 600; color: #172b4d; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .sub-cat {{ font-size: 11px; color: #5e6c84; margin-left: 5px; font-weight: normal; }}
    .grid-bg {{ display: flex; position: absolute; top:0; left:0; right:0; bottom:0; z-index: 1; pointer-events: none; }}
    .grid-col {{ flex: 1; min-width: 35px; border-right: 1px dotted #ebecf0; }}
    .bar-container {{ position: absolute; top:0; left:0; right:0; bottom:0; z-index: 2; padding: 6px 0; display:flex; align-items:center; }}
    .gantt-bar {{ position: relative; height: 28px; border-radius: 14px; display: flex; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); cursor: pointer; transition: transform 0.2s; }}
    .gantt-bar:hover {{ transform: scaleY(1.05); filter: brightness(1.1); }}
    .gantt-segment {{ flex: 1; height: 100%; border-right: 1px solid rgba(255,255,255,0.2); transition: background 0.2s; }}
    .gantt-segment:last-child {{ border-right: none; }}
    .gantt-segment.done {{ background: #b3bac5 !important; }}
    .gantt-segment.holiday {{ background: transparent !important; border-right: none; opacity: 0; }}
    .gantt-label {{ position: absolute; left: 10px; top: 0; bottom: 0; display: flex; align-items: center; color: white; font-size: 11px; font-weight: bold; white-space: nowrap; pointer-events: none; text-shadow: 0 1px 2px rgba(0,0,0,0.3); }}
    
    /* Colors based on shared status or random */
    .bg-blue .gantt-segment {{ background: #0052cc; }}
    .bg-green .gantt-segment {{ background: #36b37e; }}
    .bg-purple .gantt-segment {{ background: #6554c0; }}
    .bg-yellow .gantt-segment {{ background: #ffab00; }}
    .bg-red .gantt-segment {{ background: #ff5630; }}
    .bg-yellow .gantt-label {{ color: #172b4d !important; text-shadow: none; }}
    </style>
    </head>
    <body>
    <div class="gantt-wrapper">
      <div class="left-panel">
        <div class="header-row" style="align-items:center; padding-left:15px; font-size:14px; font-weight:bold; color:#172b4d;">Tasks / Projects</div>
    """
    
    # Process tasks to build rows
    rows_html = ""
    left_html = ""
    
    color_classes = ["bg-blue", "bg-green", "bg-purple", "bg-yellow", "bg-red"]
    
    for i, t in enumerate(tasks):
        name = t.get("task_name", "Untitled")
        cat = t.get("category", "")
        shared = t.get("shared_category", "")
        start_str = t.get("start_date")
        end_str = t.get("end_date")
        
        # default to today if missing
        try: start_d = datetime.datetime.strptime(start_str, "%Y-%m-%d").date() if start_str else datetime.date.today()
        except: start_d = datetime.date.today()
        
        try: end_d = datetime.datetime.strptime(end_str, "%Y-%m-%d").date() if end_str else start_d
        except: end_d = start_d
        
        is_recurring = t.get("is_recurring", False)
        
        # Calculate offset and width in % for the current month
        # If task is completely outside this month, skip
        if end_d < month_start or start_d > month_end:
            continue
            
        eff_start = max(start_d, chart_start_date)
        eff_end = min(end_d, month_end)
        
        # If task is entirely before the visible window, skip
        if eff_start > eff_end:
            continue
        
        start_idx = (eff_start - chart_start_date).days
        duration = (eff_end - eff_start).days + 1
        
        left_pct = (start_idx / visible_days) * 100
        width_pct = (duration / visible_days) * 100
        
        color_cls = color_classes[i % len(color_classes)]
        if shared == "전체 공유": color_cls = "bg-green"
        elif shared == "개인용": color_cls = "bg-blue"
        
        left_html += f"""
        <div class="task-row">
            <div class="left-cell">{name} <span class="sub-cat">{cat}</span></div>
        </div>
        """
        
        rows_html += f"""
        <div class="task-row">
            <div class="grid-bg">
        """
        for d in range(visible_days):
            rows_html += f'<div class="grid-col"></div>'
            
        # Build segments for each day of the duration
        segments_html = ""
        completed_dates = t.get("completed_dates", {})
        
        # We iterate from eff_start to eff_end
        current_date = eff_start
        while current_date <= eff_end:
            c_str = current_date.strftime("%Y-%m-%d")
            
            # Check if holiday
            if c_str in holidays:
                segments_html += f'<div class="gantt-segment holiday" title="{c_str} (휴일)"></div>'
            else:
                is_done = completed_dates.get(c_str, False)
                done_cls = "done" if is_done else ""
                segments_html += f'<div class="gantt-segment {done_cls}" title="{c_str} {"(완료)" if is_done else "(미완료)"}"></div>'
                
            current_date += datetime.timedelta(days=1)
            
        rows_html += f"""
            </div>
            <div class="bar-container">
                <div class="gantt-bar {color_cls}" style="margin-left: {left_pct}%; width: {width_pct}%;">
                    {segments_html}
                    <div class="gantt-label">{name}</div>
                </div>
            </div>
        </div>
        """

    html += left_html
    html += """
      </div>
      <div class="right-panel">
        <div class="header-row" style="min-width: max-content;">
    """
    
    for d in range(visible_days):
        dt = chart_start_date + datetime.timedelta(days=d)
        wd = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][dt.weekday()]
        is_wknd = "weekend" if dt.weekday() >= 5 else ""
        html += f'<div class="header-cell {is_wknd}"><span>{dt.day}</span>{wd}</div>'
        
    html += """
        </div>
        <div style="min-width: max-content;">
    """
    html += rows_html
    html += """
        </div>
      </div>
    </div>
    </body>
    </html>
    """
    return html

@st.dialog("새로운 업무 위임 알림")
def accept_delegation_dialog(pending_list, user_id):
    st.warning("다른 구성원으로부터 다음과 같은 업무가 위임되었습니다.")
    for p in pending_list:
        t = p["task"]
        date = p["date"]
        st.info(f"📅 **{date}** : {t['task_name']} (위임자: {t.get('user_id', '알 수 없음')})")
        
    if st.button("모두 수락하고 내 일정에 추가", type="primary"):
        for p in pending_list:
            update_task_delegation(p["task"]["task_id"], p["date"], user_id, status="accepted")
        st.success("수락 완료되었습니다. 오늘의 할 일에 표기됩니다.")
        st.rerun()

def render_schedule_page():
    st.title("🗓️ 팀 스케줄 & 타임라인")
    st.markdown("개인 할 일과 공유된 프로젝트 일정을 간트 차트(Gantt) 형태로 한눈에 확인하세요.")
    
    user_id = st.session_state.get("user_id")
    current_roles = st.session_state.get("role", [])
    if isinstance(current_roles, str):
        current_roles = [current_roles]
        
    if not user_id:
        st.error("로그인이 필요합니다.")
        return

    today = datetime.date.today()
    today_str = today.strftime("%Y-%m-%d")
    
    # 1. Fetch all tasks to check for pending delegations for this user
    all_tasks = get_tasks(user_id, current_roles) # get_tasks returns tasks shared with me OR owned by me
    # Wait, if someone delegated a private task to me, I won't see it if it's not shared.
    # To fix this, db.py get_tasks should ideally return tasks delegated to me.
    # But for now, we scan tasks we can see.
    pending_delegations = []
    for t in all_tasks:
        for date_str, d_info in t.get("delegations", {}).items():
            if d_info.get("delegated_to") == user_id and d_info.get("status") == "pending":
                # only show pending if it's today or future
                if date_str >= today_str:
                    pending_delegations.append({"task": t, "date": date_str})
                    
    if pending_delegations:
        accept_delegation_dialog(pending_delegations, user_id)
        
    tasks = all_tasks

    # Top Action Bar
    c1, c2, c3 = st.columns([0.6, 0.2, 0.2])
    with c1:
        st.subheader(f"📅 {today.year}년 {today.month}월 타임라인")
    with c2:
        if st.button("➕ 새 스케줄 추가", use_container_width=True, type="primary"):
            edit_task_dialog(user_id=user_id)
    with c3:
        if st.button("📝 샘플 템플릿 로드", use_container_width=True):
            load_template_tasks(user_id)
            st.rerun()

    # Toggle for past dates
    show_past = st.toggle("지난 일정 함께 보기", value=False, help="이미 지나간 날짜의 스케줄도 타임라인에 표시합니다.")

    # Render Gantt Chart
    if tasks:
        html_gantt = build_gantt_html(tasks, today.year, today.month, show_past_dates=show_past)
        components.html(html_gantt, height=400, scrolling=True)
    else:
        st.info("등록된 스케줄이 없습니다. '새 스케줄 추가' 버튼을 눌러 일정을 등록해보세요.")

    st.divider()

    # Bottom layout: Today's Todo vs Task Management
    col_left, col_right = st.columns([0.4, 0.6])
    
    with col_left:
        st.subheader("✅ 오늘의 할 일 (Checklist)")
        st.markdown(f"**{today_str}** 기준 완료 체크")
        
        holidays = get_holidays()
        
        # Filter tasks active today
        today_tasks = []
        if today_str not in holidays:
            for t in tasks:
                s_str = t.get("start_date")
                e_str = t.get("end_date")
                is_recurring = t.get("is_recurring", False)
                try: s_d = datetime.datetime.strptime(s_str, "%Y-%m-%d").date() if s_str else today
                except: s_d = today
                try: e_d = datetime.datetime.strptime(e_str, "%Y-%m-%d").date() if e_str else s_d
                except: e_d = s_d
                
                is_active_today = (s_d <= today <= e_d)
                
                # Check delegation override for today
                del_info = t.get("delegations", {}).get(today_str)
                is_mine = (t.get("user_id") == user_id)
                
                # If delegated to me and accepted, it is active for me regardless of normal date bounds
                if del_info and del_info.get("delegated_to") == user_id and del_info.get("status") == "accepted":
                    today_tasks.append(t)
                    continue
                    
                # If it's my task but I delegated it to someone else (and they accepted/pending), I don't do it today
                if del_info and is_mine:
                    continue
                
                # Otherwise, if it's active today and I own it or it's shared
                if is_active_today:
                    today_tasks.append(t)
                    
        if not today_tasks:
            if today_str in holidays:
                st.info("오늘은 휴무일/공휴일입니다. 즐거운 하루 되세요!")
            else:
                st.info("오늘 진행 중인 일정이 없습니다.")
        else:
            for task in today_tasks:
                task_id = task["task_id"]
                is_completed = task.get("completed_dates", {}).get(today_str, False)
                chk_key = f"chk_gantt_{task_id}_{today_str}"
                
                def on_change(t_id=task_id, k=chk_key):
                    toggle_task_completion(t_id, today_str, st.session_state[k])
                    
                shared_lbl = "👥" if task.get("shared_category", "개인용") != "개인용" else ""
                st.checkbox(f"{shared_lbl} {task['task_name']}", value=is_completed, key=chk_key, on_change=on_change)
                if task.get("details"):
                    st.caption(f"↳ {task['details']}")

    with col_right:
        st.subheader("⚙️ 스케줄 관리 (수정/삭제)")
        if not tasks:
            st.write("목록이 없습니다.")
        else:
            for t in tasks:
                s_str = t.get("start_date", "N/A")
                e_str = t.get("end_date", "N/A")
                cat_str = f"[{t.get('category','')}]"
                shared_lbl = f" <span style='color:blue;'>[{t.get('shared_category', '개인용')}]</span>" if t.get("shared_category", "개인용") != "개인용" else ""
                
                c_n, c_e, c_d, c_del = st.columns([0.55, 0.15, 0.15, 0.15])
                with c_n:
                    st.markdown(f"**{t['task_name']}** <span style='font-size:12px;color:gray;'>{s_str}~{e_str}</span>{shared_lbl}", unsafe_allow_html=True)
                with c_e:
                    if st.button("✏️", key=f"edit_btn_{t['task_id']}", help="수정", use_container_width=True):
                        edit_task_dialog(task=t)
                with c_d:
                    if st.button("🗑️", key=f"del_btn_{t['task_id']}", help="삭제", use_container_width=True):
                        delete_task(t['task_id'])
                        st.rerun()
                with c_del:
                    if st.button("👤", key=f"delegate_btn_{t['task_id']}", help="대체자 지정", use_container_width=True):
                        delegate_task_dialog(t)

if __name__ == "__main__":
    render_schedule_page()
