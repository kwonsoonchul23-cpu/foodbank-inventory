import streamlit as st
import pandas as pd
import os
import re
import json
import streamlit.components.v1 as components
from db import get_geodream_theme, update_geodream_theme, _load_shared_state, _save_shared_state

from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
MASTER_CSV = os.path.join(DATA_DIR, "geodream_master.csv")
DAILY_CSV  = os.path.join(DATA_DIR, "geodream_daily.csv")
HISTORY_JSON = os.path.join(DATA_DIR, "geodream_history.json")
MAP_CONFIG_KEY = "geodream_map_config"
MAP_COMPONENT_DIR = os.path.join(BASE_DIR, "components", "geodream_map")

def _load_history():
    if not os.path.exists(HISTORY_JSON): return []
    try:
        with open(HISTORY_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def _save_history(history):
    with open(HISTORY_JSON, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# 레퍼런스 이미지 복원: 은평구 16개 동 정밀 좌표 (1050x1100 캠버스)
# 진관동 상단 돌출부, 수색동 좌하단 분리부 포함
DEFAULT_DONGS = [
    {"id": "jingwan",   "name": "진관동",  "color": "#8A9A7E",
     "points": "480,55 500,20 520,10 560,15 575,35 570,60 555,80 580,100 620,110 680,125 730,155 780,170 830,180 850,200 860,280 840,340 810,370 780,360 730,350 690,340 660,330 620,310 580,305 550,295 520,280 490,275 465,250 445,215 440,175 450,140 460,105 470,75"},
    {"id": "bulgwang2", "name": "불광2동", "color": "#9A8AA0",
     "points": "520,280 550,295 580,305 620,310 660,330 690,340 700,370 680,395 650,390 610,380 575,370 540,365 510,355 490,340 485,315 495,290"},
    {"id": "galhyun1",  "name": "갈현1동", "color": "#A09880",
     "points": "350,245 380,225 420,210 440,175 445,215 465,250 490,275 495,290 485,315 475,330 445,340 415,335 395,320 365,295 345,275"},
    {"id": "bulgwang1", "name": "불광1동", "color": "#98A888",
     "points": "780,360 810,370 840,340 860,380 860,430 850,470 830,500 800,520 770,510 745,495 720,470 700,445 690,420 700,395 700,370 730,350"},
    {"id": "galhyun2",  "name": "갈현2동", "color": "#B0988A",
     "points": "310,305 345,275 365,295 395,320 415,335 420,365 400,390 375,395 345,380 320,365 305,340"},
    {"id": "daejo",     "name": "대조동",  "color": "#8898A8",
     "points": "445,340 475,330 490,340 510,355 540,365 575,370 610,380 650,390 640,415 620,435 590,445 560,440 535,430 510,420 490,410 465,395 445,380 430,365 420,365 415,335"},
    {"id": "nokbun",    "name": "녹번동",  "color": "#A88890",
     "points": "690,420 700,445 720,470 745,495 770,510 770,560 755,590 730,610 700,620 670,615 640,595 615,575 590,555 575,530 570,505 580,475 590,445 620,435 640,415 680,395"},
    {"id": "yeokchon",  "name": "역촌동",  "color": "#90A888",
     "points": "375,395 400,390 420,365 430,365 445,380 465,395 490,410 510,420 510,450 490,470 465,480 440,485 420,480 395,465 375,445 360,430 355,410"},
    {"id": "gusan",     "name": "구산동",  "color": "#A89098",
     "points": "240,360 270,330 310,305 305,340 320,365 345,380 330,410 310,430 285,440 260,430 235,410 225,385"},
    {"id": "sinsa1",    "name": "신사1동", "color": "#88A090",
     "points": "260,430 285,440 310,430 330,410 345,380 355,410 360,430 375,445 380,470 370,495 350,510 330,515 300,510 275,500 255,480 245,455"},
    {"id": "sinsa2",    "name": "신사2동", "color": "#A89888",
     "points": "200,490 225,480 245,455 255,480 275,500 300,510 310,535 295,555 275,570 250,575 220,565 200,545 185,520"},
    {"id": "eungam1",   "name": "응암1동", "color": "#88A098",
     "points": "510,420 535,430 560,440 590,445 580,475 570,505 575,530 590,555 580,580 560,595 535,600 510,595 490,585 470,575 455,555 440,535 430,510 420,480 440,485 465,480 490,470 510,450"},
    {"id": "eungam2",   "name": "응암2동", "color": "#988888",
     "points": "590,555 615,575 640,595 670,615 680,640 665,665 645,680 620,685 595,675 570,660 555,640 545,620 540,600 560,595 580,580"},
    {"id": "eungam3",   "name": "응암3동", "color": "#8898A8",
     "points": "455,555 470,575 490,585 510,595 535,600 540,600 545,620 555,640 545,665 525,680 500,690 475,685 455,670 440,650 430,625 425,600 430,575 440,555"},
    {"id": "jeungsan",  "name": "증산동",  "color": "#A0A888",
     "points": "300,510 330,515 350,510 370,495 380,470 395,465 420,480 430,510 440,535 455,555 440,555 430,575 425,600 430,625 420,645 400,665 375,670 350,660 325,645 300,625 280,600 270,580 275,570 295,555 310,535"},
    {"id": "susaek",    "name": "수색동",  "color": "#8890A0",
     "points": "185,520 200,545 220,565 240,585 245,610 230,645 210,670 180,685 155,680 125,665 105,645 90,620 85,590 90,560 100,535 120,510 145,500 165,505"},
]

def get_map_config():
    state = _load_shared_state()
    cfg = state.get(MAP_CONFIG_KEY, {})
    return {
        "dongs":        cfg.get("dongs", [d.copy() for d in DEFAULT_DONGS]),
        "bg_color":     cfg.get("bg_color",     "#2D3B2A"),
        "border_color": cfg.get("border_color", "#FFFFFF"),
        "hover_color":  cfg.get("hover_color",  "#E6D8A7"),
        "tooltip_bg":   cfg.get("tooltip_bg",   "rgba(20,30,20,0.95)"),
        "tooltip_text": cfg.get("tooltip_text", "#F0E6D2"),
        "font_family":  cfg.get("font_family",  "'Noto Sans KR', sans-serif"),
        "font_size":    cfg.get("font_size", 12),
        "merged_zones": cfg.get("merged_zones", {}),
    }

def save_map_config(cfg):
    state = _load_shared_state()
    state[MAP_CONFIG_KEY] = cfg
    _save_shared_state(state)

def clean_dong(addr):
    if not isinstance(addr, str): return None
    match = re.search(r'([가-힣]+[0-9]?동)', addr)
    if match: return match.group(1)
    return None

def load_data(path, columns):
    if not os.path.exists(path): return pd.DataFrame(columns=columns)
    return pd.read_csv(path)

def save_data(df, path):
    df.to_csv(path, index=False)

def parse_visitor_excel(file):
    try:
        xls = pd.ExcelFile(file)
        all_data = []
        for sheet in xls.sheet_names:
            df_raw = pd.read_excel(file, sheet_name=sheet, header=None, nrows=15).fillna("").astype(str)
            header_idx = -1
            for i in range(len(df_raw)):
                row_vals = df_raw.iloc[i].values
                if any("주소" in v for v in row_vals) and any("생년월일" in v for v in row_vals):
                    header_idx = i
                    break
            if header_idx == -1:
                continue
            df = pd.read_excel(file, sheet_name=sheet, skiprows=header_idx)
            addr_col  = [c for c in df.columns if "주소" in str(c)]
            date_col  = [c for c in df.columns if "방문일자" in str(c) or "일자" in str(c)]
            birth_col = [c for c in df.columns if "생년월일" in str(c)]
            visit_type_col = [c for c in df.columns if "방문구분" in str(c)]
            if not addr_col or not date_col:
                continue
            df = df.dropna(subset=[addr_col[0], date_col[-1]])
            df["dong"] = df[addr_col[0]].apply(clean_dong)
            def parse_korean_date(d_str):
                if pd.isna(d_str): return None
                s = str(d_str)
                m = re.search(r'(\d+)월\s*(\d+)일', s)
                if m:
                    curr_year = datetime.now().year
                    return f"{curr_year}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
                try:
                    return pd.to_datetime(s).strftime("%Y-%m-%d")
                except:
                    return None
            df["date"] = df[date_col[-1]].apply(parse_korean_date)
            df = df.dropna(subset=["dong", "date"])
            df["birthdate"]  = df[birth_col[0]] if birth_col else ""
            df["visit_type"] = df[visit_type_col[0]] if visit_type_col else "알수없음"
            all_data.append(df)
            
        if not all_data:
            return None, "엑셀 파일의 모든 시트에서 '주소' 또는 '생년월일' 컬럼을 찾을 수 없습니다."
        
        df_combined = pd.concat(all_data, ignore_index=True)
        df_grouped = df_combined.groupby(["date", "dong", "visit_type"]).size().reset_index(name="count")
        return df_grouped, None
    except Exception as e:
        return None, f"이용자 대장 파싱 오류: {str(e)}"

def parse_daily_excel(file):
    try:
        xls = pd.ExcelFile(file)
        all_records = []
        for sheet in xls.sheet_names:
            df_raw = pd.read_excel(file, sheet_name=sheet, header=None).fillna("")
            year_month_str = ""
            for i in range(min(15, len(df_raw))):
                val = str(df_raw.iloc[i, 0]) if len(df_raw.columns) > 0 else ""
                if "년" in val and "월" in val:
                    year_month_str = val
                    break
            match = re.search(r"(\d+)년\s*(\d+)월", year_month_str)
            if not match: continue
            year, month = int(match.group(1)), int(match.group(2))
            start_idx = -1
            for i in range(min(20, len(df_raw))):
                if len(df_raw.columns) > 0 and str(df_raw.iloc[i, 0]).strip() == "일":
                    start_idx = i + 1
                    break
            if start_idx == -1: continue
            inventory_col_idx = -1
            for j in range(len(df_raw.columns)):
                if "재고량" in str(df_raw.iloc[start_idx-2, j]) or "재고량" in str(df_raw.iloc[start_idx-1, j]):
                    inventory_col_idx = j
                    break
            for i in range(start_idx, len(df_raw)):
                day_str = str(df_raw.iloc[i, 0]).strip()
                if day_str.isdigit():
                    day = int(day_str)
                    visitors = str(df_raw.iloc[i, 2]).strip()
                    visitors = int(visitors) if visitors.isdigit() else 0
                    inventory = 0
                    if inventory_col_idx != -1:
                        inv_val = str(df_raw.iloc[i, inventory_col_idx]).strip()
                        if inv_val.isdigit(): inventory = int(inv_val)
                    date_str = f"{year}-{month:02d}-{day:02d}"
                    all_records.append({"date": date_str, "total_visitors": visitors, "inventory": inventory})
        if not all_records: return None, "모든 시트에서 연도/월 정보나 데이터를 추출할 수 없습니다."
        return pd.DataFrame(all_records), None
    except Exception as e:
        return None, f"일일보고 파싱 오류: {str(e)}"

def merge_data(existing_df, new_df, date_col="date"):
    new_dates = new_df[date_col].unique()
    conflict_details = []
    for d in new_dates:
        old_subset = existing_df[existing_df[date_col] == d]
        new_subset = new_df[new_df[date_col] == d]
        if "count" in new_df.columns:
            old_val = old_subset["count"].sum() if not old_subset.empty else 0
            new_val = new_subset["count"].sum()
        else:
            old_val = old_subset["total_visitors"].sum() if not old_subset.empty else 0
            new_val = new_subset["total_visitors"].sum()
        if old_val > 0 and old_val != new_val:
            conflict_details.append(f"- **{d}**: 기존 누적({old_val}명) vs 업로드({new_val}명)")
    return conflict_details, new_dates

# build_svg_map_html is removed as it's now handled by the frontend component.


def render_geodream_page():
    st.title("🗺️ 그냥드림 데이터 센터")
    st.markdown("엑셀 파일을 업로드하면 데이터를 누적하고 은평구 이용자 분포를 시각화합니다.")

    # 저장 성공 후 메시지 표시
    if st.session_state.get("geodream_upload_success"):
        st.success("✅ 엑셀 데이터가 성공적으로 누적(반영)되었습니다!", icon="🎉")
        st.session_state["geodream_upload_success"] = False

    master_df = load_data(MASTER_CSV, ["date", "dong", "count", "visit_type"])
    daily_df  = load_data(DAILY_CSV,  ["date", "total_visitors"])
    cfg = get_map_config()

    with st.expander("📁 엑셀 파일 업로드 (이용자 관리대장 / 일일 보고)", expanded=master_df.empty and daily_df.empty):
        st.info(
            "💡 **어떤 파일이 어디에 반영되나요?**\n"
            "- **이용자 관리대장** (주소 포함): 은평구 **지도 위 동네별 인원수**에 반영됩니다.\n"
            "- **일일 보고** (누적 통계): 페이지 하단의 **일일 현황 꺾은선 차트**에 반영됩니다."
        )
        uploaded_files = st.file_uploader(
            "파일을 선택하거나 끌어다 놓으세요 (여러 개 가능)",
            type=["xlsx", "xls"], accept_multiple_files=True
        )
        if uploaded_files:
            all_conflicts, parsed_master, parsed_daily = [], None, None
            new_master_dates, new_daily_dates = [], []
            for file in uploaded_files:
                df_raw = pd.read_excel(file, nrows=15).fillna("").astype(str)
                is_daily = any("일일" in col or "방문 누계" in col for col in df_raw.columns) or \
                           any("일일" in str(v) or "방문 누계" in str(v) for v in df_raw.values.flatten())
                if is_daily:
                    st.info(f"📄 **{file.name}** → 일일 보고 파일로 인식")
                    new_df, err = parse_daily_excel(file)
                    if err: st.error(err)
                    else:
                        conflicts, dates = merge_data(daily_df, new_df)
                        all_conflicts.extend([f"[일일보고] {c}" for c in conflicts])
                        parsed_daily, new_daily_dates = new_df, dates
                else:
                    st.info(f"📄 **{file.name}** → 이용자 관리대장 파일로 인식")
                    new_df, err = parse_visitor_excel(file)
                    if err: st.error(err)
                    else:
                        conflicts, dates = merge_data(master_df, new_df)
                        all_conflicts.extend([f"[관리대장] {c}" for c in conflicts])
                        parsed_master, new_master_dates = new_df, dates

            def _commit_changes(is_conflict=False):
                from datetime import datetime
                history = _load_history()
                record = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "files": [f.name for f in uploaded_files],
                    "conflicts": all_conflicts if is_conflict else ["차이점 없음 (순수 추가)"]
                }
                history.insert(0, record)
                _save_history(history[:50])

                nonlocal master_df, daily_df
                if parsed_master is not None:
                    master_df = master_df[~master_df["date"].isin(new_master_dates)]
                    master_df = pd.concat([master_df, parsed_master], ignore_index=True)
                    save_data(master_df, MASTER_CSV)
                if parsed_daily is not None:
                    daily_df = daily_df[~daily_df["date"].isin(new_daily_dates)]
                    daily_df = pd.concat([daily_df, parsed_daily], ignore_index=True)
                    save_data(daily_df, DAILY_CSV)
                st.session_state["geodream_upload_success"] = True
                st.rerun()

            if all_conflicts:
                st.warning("⚠️ 기존 데이터와 인원 수가 다른 날짜가 있습니다!")
                for c in all_conflicts: st.markdown(c)
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("🚨 새 파일로 변경사항 기록하며 병합", type="primary"):
                        _commit_changes(is_conflict=True)
                with c2:
                    if st.button("❌ 취소"): st.info("업로드 취소됨")
            elif parsed_master is not None or parsed_daily is not None:
                if st.button("✅ 검증 완료 — 데이터 누적하기", type="primary"):
                    _commit_changes(is_conflict=False)
                    
        history_data = _load_history()
        if history_data:
            st.write("---")
            st.subheader("📜 데이터 변경 이력")
            for h in history_data:
                with st.expander(f"[{h['timestamp']}] {', '.join(h['files'])}"):
                    for c in h['conflicts']:
                        st.write(c)

    st.divider()

    count_by_dong, dong_trends, dong_breakdown = {}, {}, {}
    if not master_df.empty:
        agg = master_df.groupby("dong")["count"].sum()
        count_by_dong = agg.to_dict()
        for dong, grp in master_df.groupby("dong"):
            tr = grp.groupby("date")["count"].sum().reset_index().sort_values("date")
            dong_trends[dong] = tr.to_dict("records")
            if "visit_type" in grp.columns:
                brk = grp.groupby("visit_type")["count"].sum().reset_index()
                dong_breakdown[dong] = brk.to_dict("records")

    # 통폐합 반영
    merged = cfg.get("merged_zones", {})
    for target_name, source_names in merged.items():
        total = count_by_dong.get(target_name, 0)
        for src in source_names:
            total += count_by_dong.pop(src, 0)
        if total:
            count_by_dong[target_name] = total

    st.divider()
    
    if "geo_font_size" not in st.session_state:
        st.session_state["geo_font_size"] = cfg["font_size"]
        
    def update_font_size():
        cfg["font_size"] = st.session_state["geo_font_size"]
        save_map_config(cfg)
        
    font_size = st.slider("🔎 지도 라벨 글자 크기 조절", min_value=8, max_value=24, step=1, key="geo_font_size", on_change=update_font_size)
    
    # 날짜 선택기 기능
    if not master_df.empty:
        all_dates = sorted(master_df["date"].unique(), reverse=True)
        date_option = st.selectbox(
            "📅 특정 날짜 분포 보기 (선택 안 하면 전체 누적)",
            options=["전체 누적 (필터 없음)"] + list(all_dates),
            index=0
        )
        if date_option != "전체 누적 (필터 없음)":
            selected_df = master_df[master_df["date"] == date_option]
            agg = selected_df.groupby("dong")["count"].sum()
            count_by_dong = agg.to_dict()
            dong_trends = {}
            for dong, grp in selected_df.groupby("dong"):
                dong_trends[dong] = [{"date": date_option, "count": int(grp["count"].sum())}]
    
    districts_data = []
    for d in cfg["dongs"]:
        dong_name = d["name"]
        cnt = count_by_dong.get(dong_name, 0)
        districts_data.append({
            "id": f"d-{d['id']}",
            "name": dong_name,
            "count": cnt,
            "color": d.get("color", "#1e3514"),
            "trend": dong_trends.get(dong_name, []),
            "breakdown": dong_breakdown.get(dong_name, [])
        })

    # components.html 방식: index.html 읽고 데이터 주입
    html_path = os.path.join(MAP_COMPONENT_DIR, "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        map_html = f.read()

    # districts_data를 JSON으로 직렬화하여 JS 초기화 코드 주입
    init_script = f"""
    <script>
    (function() {{
      const INIT_DATA = {json.dumps(districts_data, ensure_ascii=False)};
      // district 초기화
      INIT_DATA.forEach(function(d) {{
        var el = document.getElementById(d.id);
        if (el) {{
          el.dataset.name = d.name;
          el.dataset.count = d.count;
          el.dataset.trend = JSON.stringify(d.trend || []);
          el.dataset.breakdown = JSON.stringify(d.breakdown || []);
        }}
        districts[d.id] = d;
      }});
      if (typeof refreshMap === 'function') refreshMap();
    }})();
    </script>
    """
    map_html = map_html.replace("</body>", init_script + "</body>")

    components.html(map_html, height=820, scrolling=False)

    if not daily_df.empty:
        st.divider()
        st.subheader("📈 일일 방문자 및 재고 추이")
        daily_df["date"] = pd.to_datetime(daily_df["date"])
        daily_df = daily_df.sort_values("date")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**👥 일별 방문자**")
            st.line_chart(daily_df.set_index("date")["total_visitors"])
        with col2:
            if "inventory" in daily_df.columns:
                st.markdown("**📦 일별 재고량**")
                st.line_chart(daily_df.set_index("date")["inventory"], color="#ff6b6b")
        c1, c2, c3 = st.columns(3)
        c1.metric("총 방문자", f"{daily_df['total_visitors'].sum()}명")
        c2.metric("일 평균",   f"{daily_df['total_visitors'].mean():.1f}명")
        c3.metric("운영 일수", f"{len(daily_df)}일")

    st.divider()
    with st.expander("🔀 구역 통폐합 설정 (데이터 병합)"):
        st.caption("여러 동을 하나로 묶어 지도에 합산하여 표시합니다.")
        updated_dongs = cfg["dongs"]
        dong_names = [d["name"] for d in updated_dongs]
        existing_merged = cfg.get("merged_zones", {})
        new_merged = {}
        with st.form("merge_form"):
            num_m = st.number_input("통폐합 규칙 수", min_value=0, max_value=8,
                                    value=len(existing_merged), step=1)
            items = list(existing_merged.items())
            for k in range(int(num_m)):
                c1m, c2m = st.columns([2, 4])
                def_t = items[k][0] if k < len(items) else ""
                def_s = items[k][1] if k < len(items) else []
                tgt = c1m.text_input(f"대표 이름 #{k+1}", value=def_t, key=f"mt_{k}")
                src = c2m.multiselect(f"포함할 구역 #{k+1}", dong_names,
                                      default=[s for s in def_s if s in dong_names],
                                      key=f"ms_{k}")
                if tgt:
                    new_merged[tgt] = src

            if st.form_submit_button("💾 통폐합 규칙 저장", type="primary"):
                cfg["merged_zones"] = new_merged
                save_map_config(cfg)
                st.success("✅ 구역 통폐합 설정이 저장되었습니다!")
                st.rerun()

if __name__ == "__main__":
    render_geodream_page()
