import pandas as pd
import io
import openpyxl
from openpyxl.formula.translate import Translator
import re
def extract_stats(file, expected_count):
    try:
        df = pd.read_excel(file, header=None)
        last_row = df.iloc[-1].values
        
        nums = []
        for val in last_row:
            if pd.notnull(val) and isinstance(val, (int, float)):
                nums.append(val)
        
        if len(nums) >= expected_count:
            return nums[-expected_count:]
        else:
            return nums + [0] * (expected_count - len(nums))
    except Exception as e:
        print(f"Error extracting stats: {e}")
        return [0] * expected_count

def _set_cell_value(ws, row_idx, col_idx, val):
    try:
        cell = ws.cell(row=row_idx, column=col_idx)
        import openpyxl.cell.cell
        if not isinstance(cell, openpyxl.cell.cell.MergedCell):
            cell.value = val
    except AttributeError:
        pass

def process_morning_excel(raw_files):
    if not isinstance(raw_files, list):
        raw_files = [raw_files]
        
    main_file = None
    template_file = None
    provision_file = None  # 제공현황 파일 (물품 제공 내역 시트 데이터)
    stats_files = {
        "기부자_일": None, "기부자_월": None, "기부자_년": None,
        "이용자_일": None, "이용자_월": None, "이용자_년": None
    }
    
    for file in raw_files:
        fname = file.name if hasattr(file, 'name') else str(file)
        if "일일마감일지" in fname and not fname.startswith("~$"):
            template_file = file
        elif "기부자" in fname and "일" in fname:
            stats_files["기부자_일"] = file
        elif "기부자" in fname and "월" in fname:
            stats_files["기부자_월"] = file
        elif "기부자" in fname and "년" in fname:
            stats_files["기부자_년"] = file
        elif "이용자" in fname and "일" in fname:
            stats_files["이용자_일"] = file
        elif "이용자" in fname and "월" in fname:
            stats_files["이용자_월"] = file
        elif "이용자" in fname and "년" in fname:
            stats_files["이용자_년"] = file
        elif "제공현황" in fname:
            # 제공현황은 main_file이 아닌 별도의 provision_file로 분류
            provision_file = file
        elif "grd_" in fname or ("공유" in fname and "서류" in fname) or ("아침_서류" in fname) or "하단" in fname:
            main_file = file
    
    # 분류 제외 대상: 이미 역할이 부여된 파일 목록
    classified_files = set(f for f in [template_file, main_file, provision_file] if f is not None)
    classified_files.update(f for f in stats_files.values() if f is not None)
            
    # Fallback identify
    if not template_file:
        for file in raw_files:
            fname = file.name if hasattr(file, 'name') else str(file)
            if file not in classified_files and not fname.startswith("~$"):
                template_file = file
                classified_files.add(file)
                break
                
    if not main_file:
        for file in raw_files:
            fname = file.name if hasattr(file, 'name') else str(file)
            if file not in classified_files and not fname.startswith("~$"):
                main_file = file
                classified_files.add(file)
                break

    if not main_file:
        raise ValueError("메인 FMS 원본 엑셀 파일(예: grd_tbOm... 또는 하단내용.xlsx)을 찾을 수 없습니다.")
    if not template_file:
        raise ValueError("일일마감일지 템플릿 파일([공유]06.19 일일마감일지.xlsx 등)을 찾을 수 없습니다. 템플릿도 같이 업로드해주세요.")

    day_gibu = extract_stats(stats_files["기부자_일"], 4) if stats_files["기부자_일"] else [0]*4
    month_gibu = extract_stats(stats_files["기부자_월"], 4) if stats_files["기부자_월"] else [0]*4
    year_gibu = extract_stats(stats_files["기부자_년"], 4) if stats_files["기부자_년"] else [0]*4
    
    day_use = extract_stats(stats_files["이용자_일"], 5) if stats_files["이용자_일"] else [0]*5
    month_use = extract_stats(stats_files["이용자_월"], 5) if stats_files["이용자_월"] else [0]*5
    year_use = extract_stats(stats_files["이용자_년"], 5) if stats_files["이용자_년"] else [0]*5

    # 템플릿 로드 (수식 보존)
    wb = openpyxl.load_workbook(template_file, data_only=False)
    ws = wb["Sheet1"] if "Sheet1" in wb.sheetnames else wb.active

    # 상단 통계 매핑
    mapping = {
        8: day_gibu + day_use,
        10: month_gibu + month_use,
        12: year_gibu + year_use
    }
    
    for row_idx, data_list in mapping.items():
        for col_offset, val in enumerate(data_list):
            _set_cell_value(ws, row_idx, 3 + col_offset, val)

    # 제공현황 데이터를 '물품 제공 내역' 시트에 복사
    if provision_file and '물품 제공 내역' in wb.sheetnames:
        try:
            df_prov = pd.read_excel(provision_file, header=None)
            ws_prov = wb['물품 제공 내역']
            for r_idx, row in enumerate(df_prov.values):
                for c_idx, val in enumerate(row):
                    if pd.notnull(val):
                        _set_cell_value(ws_prov, r_idx + 1, c_idx + 1, val)
        except Exception as e:
            print(f"제공현황 시트 복사 중 오류 (무시): {e}")

    # 원장 데이터 처리
    df_raw = pd.read_excel(main_file, header=None)
    
    # 보안: 메모리 레벨에서 전체 데이터프레임의 민감정보(주민번호, 연락처) 즉시 마스킹
    def mask_sensitive_pii(val):
        if not isinstance(val, str):
            return val
        # 연락처 마스킹 (010-1234-5678 -> 010-****-5678)
        val = re.sub(r'(\d{2,3})[-.]?(\d{3,4})[-.]?(\d{4})', r'\1-****-\3', val)
        # 주민번호/외국인등록번호 마스킹 (800101-1234567 -> 800101-*******)
        val = re.sub(r'(\d{6})[-.]?(\d{7})', r'\1-*******', val)
        return val
        
    # Pandas 2.1.0 이상에서는 applymap이 제거되고 map으로 대체되었습니다.
    if hasattr(df_raw, 'map'):
        df_raw = df_raw.map(mask_sensitive_pii)
    else:
        df_raw = df_raw.applymap(mask_sensitive_pii)
    
    df_data = df_raw.iloc[3:].copy() if len(df_raw) > 3 else pd.DataFrame()
    # 빈 행 완벽 차단 로직 (문자열 변환 후 양쪽 공백 제거, 빈 값/nan/합계 제외)
    if not df_data.empty:
        df_data = df_data[df_data[0].astype(str).str.strip() != ""]
        df_data = df_data[df_data[0].astype(str).str.strip().str.lower() != "nan"]
        df_data = df_data[~df_data[0].astype(str).str.contains("합계")]
    
    start_row = 17

    def safe_date(val):
        if pd.isnull(val): return ""
        try:
            # datetime 객체는 그대로 유지 (엑셀 날짜 서식 보존)
            dt = pd.to_datetime(val)
            return dt.to_pydatetime()
        except Exception:
            return str(val).strip()

    for idx, row in enumerate(df_data.values):
        donor = row[0]
        date = safe_date(row[1])
        item_name = row[2]
        expiry = safe_date(row[3])
        
        in_qty = pd.to_numeric(row[4], errors='coerce')
        in_qty = in_qty if pd.notnull(in_qty) else 0
        in_amt = pd.to_numeric(row[5], errors='coerce')
        in_amt = in_amt if pd.notnull(in_amt) else 0
        
        out_qty = pd.to_numeric(row[6], errors='coerce')
        out_qty = out_qty if pd.notnull(out_qty) else 0
        out_amt = pd.to_numeric(row[7], errors='coerce')
        out_amt = out_amt if pd.notnull(out_amt) else 0
        
        disp_qty = pd.to_numeric(row[8], errors='coerce')
        disp_qty = disp_qty if pd.notnull(disp_qty) else 0
        disp_amt = pd.to_numeric(row[9], errors='coerce')
        disp_amt = disp_amt if pd.notnull(disp_amt) else 0
        
        inv_qty = pd.to_numeric(row[10], errors='coerce')
        inv_qty = inv_qty if pd.notnull(inv_qty) else 0
        inv_amt = pd.to_numeric(row[11], errors='coerce')
        inv_amt = inv_amt if pd.notnull(inv_amt) else 0
        
        yesterday_qty = inv_qty - in_qty + out_qty + disp_qty
        yesterday_amt = inv_amt - in_amt + out_amt + disp_amt
        
        recv_type = "기부"
        if "푸드마켓" in str(donor) or "재단" in str(donor):
            recv_type = "자체(구입)"
        elif "산업" in str(donor) or "주식회사" in str(donor) or "협의회" in str(donor):
            recv_type = "광역"
            
            
        prov_type = "이용자"
        if "학교" in str(donor) or "도서관" in str(donor) or "교회" in str(donor):
            prov_type = "시설"
            
        r_idx = start_row + idx
        
        def _set_all(c_idx, val):
            _set_cell_value(ws, r_idx, c_idx, val)

        _set_all(1, idx + 1)
        _set_all(2, donor)
        _set_all(3, date)
        _set_all(4, item_name)
        _set_all(5, expiry)
        _set_all(6, "개")
        
        # 수식 열(G, H, O, P)은 템플릿 원본 수식을 철저히 보호하기 위해 파이썬에서 덮어쓰지 않음
        _set_all(9, in_qty)
        _set_all(10, in_amt)
        _set_all(11, out_qty)
        _set_all(12, out_amt)
        _set_all(13, inv_qty)
        _set_all(14, inv_amt)


    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()

