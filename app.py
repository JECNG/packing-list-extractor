from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import pandas as pd
import numpy as np
import json
import tempfile
import os
from collections import defaultdict

app = Flask(__name__)
CORS(app)  # 프론트엔드에서 API 호출 허용

def parse_size_grid(field_chars, pattern=None):
    """
    사이즈 그리드 파싱: size 행과 qty 행을 X 좌표로 매핑
    
    Args:
        field_chars: [(y, x, text), ...] 형식의 문자 데이터
        pattern: 저장된 패턴 정보 (size_row_y, qty_row_y, size_cells, qty_cells)
        
    Returns:
        dict: {size: qty, ...} 형식의 딕셔너리 또는 None
    """
    if not field_chars:
        return None
    
    # Y 위치별로 그룹화 (위에서 아래로)
    y_groups = {}
    for char_y, char_x, char_text in field_chars:
        y_rounded = round(char_y)  # Y 좌표 반올림 (같은 행으로 그룹화)
        if y_rounded not in y_groups:
            y_groups[y_rounded] = []
        y_groups[y_rounded].append((char_x, char_text))
    
    # Y 위치로 정렬 (위에서 아래로, 큰 값부터)
    sorted_y_positions = sorted(y_groups.keys(), reverse=True)
    
    if len(sorted_y_positions) < 2:
        return None
    
    # 패턴이 있으면 저장된 Y 위치 사용
    if pattern and 'size_row_y' in pattern and 'qty_row_y' in pattern:
        size_row_y = pattern['size_row_y']
        qty_row_y = pattern['qty_row_y']
        
        # 저장된 Y 위치와 가장 가까운 실제 Y 위치 찾기
        size_row_y_actual = min(sorted_y_positions, key=lambda y: abs(y - size_row_y))
        qty_row_y_actual = min(sorted_y_positions, key=lambda y: abs(y - qty_row_y))
        
        if size_row_y_actual in y_groups and qty_row_y_actual in y_groups:
            # 저장된 셀 패턴 사용
            size_cells_template = pattern.get('size_cells', [])
            qty_cells_template = pattern.get('qty_cells', [])
            
            if size_cells_template and qty_cells_template:
                return parse_size_grid_with_pattern(
                    y_groups[size_row_y_actual], 
                    y_groups[qty_row_y_actual],
                    size_cells_template,
                    qty_cells_template
                )
    
    # 각 행에서 텍스트 블록 추출 (셀 단위)
    def extract_cells_from_row(row_chars):
        """한 행에서 셀 단위로 텍스트 추출"""
        if not row_chars:
            return []
        
        # X 좌표 순으로 정렬
        sorted_chars = sorted(row_chars, key=lambda c: c[0])
        
        cells = []
        current_cell = []
        prev_x = None
        cell_separation_threshold = 15  # 셀 간격 (픽셀) - 더 크게 설정
        
        for char_x, char_text in sorted_chars:
            # 새 셀 시작 조건: X 좌표 간격이 threshold보다 크면
            if prev_x is not None and abs(char_x - prev_x) > cell_separation_threshold:
                # 이전 셀 저장
                if current_cell:
                    cell_text = ''.join(c[1] for c in current_cell).strip()
                    if cell_text:
                        x_start = min(c[0] for c in current_cell)
                        x_end = max(c[0] for c in current_cell)
                        x_center = (x_start + x_end) / 2
                        cells.append((cell_text, x_center, x_start, x_end))
                    current_cell = []
            
            current_cell.append((char_x, char_text))
            prev_x = char_x
        
        # 마지막 셀 저장
        if current_cell:
            cell_text = ''.join(c[1] for c in current_cell).strip()
            if cell_text:
                x_start = min(c[0] for c in current_cell)
                x_end = max(c[0] for c in current_cell)
                x_center = (x_start + x_end) / 2
                cells.append((cell_text, x_center, x_start, x_end))
        
        return cells
    
    # 모든 행에서 셀 추출
    row_cells = {}
    for y_pos in sorted_y_positions:
        cells = extract_cells_from_row(y_groups[y_pos])
        if cells:
            row_cells[y_pos] = cells
    
    if len(row_cells) < 2:
        return None
    
    # size 행과 qty 행 찾기
    # 숫자만 있는 행은 qty 행, 사이즈 패턴이 있는 행은 size 행
    size_row = None
    qty_row = None
    
    for y_pos, cells in sorted(row_cells.items(), reverse=True):
        # 숫자만 있는지 확인
        all_numeric = True
        for cell_text, _, _, _ in cells:
            # 숫자 또는 숫자와 몇 가지 기호만 포함하는지 확인
            cleaned = cell_text.strip().replace('½', '').replace('.', '').replace(',', '')
            if not cleaned or not cleaned.replace('-', '').replace(' ', '').isdigit():
                all_numeric = False
                break
        
        if all_numeric and qty_row is None:
            # 숫자만 있는 첫 번째 행 = qty 행
            qty_row = (y_pos, cells)
        elif size_row is None:
            # 그 다음 행 = size 행
            size_row = (y_pos, cells)
    
    # size 행과 qty 행을 찾지 못한 경우, 첫 번째와 두 번째 행 사용
    if size_row is None or qty_row is None:
        sorted_rows = sorted(row_cells.items(), reverse=True)
        if len(sorted_rows) >= 2:
            size_row = (sorted_rows[0][0], sorted_rows[0][1])
            qty_row = (sorted_rows[1][0], sorted_rows[1][1])
        else:
            return None
    
    size_cells = size_row[1]  # [(text, x_center, x_start, x_end), ...]
    qty_cells = qty_row[1]
    
    # 각 사이즈에 대해 qty 매핑
    size_grid_dict = {}
    
    for size_text, size_x_center, size_x_start, size_x_end in size_cells:
        # 사이즈 셀 범위 내에 있는 qty 찾기
        matched_qty = None
        min_distance = float('inf')
        matched_qty_text = None
        
        for qty_text, qty_x_center, qty_x_start, qty_x_end in qty_cells:
            # qty 셀의 중앙이 사이즈 셀 범위 내에 있거나, 겹치는 경우
            if (size_x_start <= qty_x_center <= size_x_end) or \
               (qty_x_start <= size_x_center <= qty_x_end) or \
               (size_x_start <= qty_x_start <= size_x_end) or \
               (size_x_start <= qty_x_end <= size_x_end):
                # 매칭됨
                matched_qty = qty_text
                matched_qty_text = qty_text
                break
            else:
                # 거리 계산 (더 가까운 것으로)
                distance = min(
                    abs(qty_x_center - size_x_center),
                    abs(qty_x_start - size_x_center),
                    abs(qty_x_end - size_x_center)
                )
                if distance < min_distance:
                    min_distance = distance
                    matched_qty_text = qty_text
        
        # 수량 추출
        if matched_qty_text:
            try:
                # 숫자만 추출 (문자 제거)
                import re
                numbers = re.findall(r'\d+', matched_qty_text)
                if numbers:
                    qty_value = int(numbers[0])
                else:
                    qty_value = 0
            except (ValueError, IndexError):
                qty_value = 0
        else:
            qty_value = 0
        
        size_grid_dict[size_text] = qty_value
    
    return size_grid_dict if size_grid_dict else None

def parse_size_grid_with_pattern(size_row_chars, qty_row_chars, size_cells_template, qty_cells_template):
    """
    저장된 패턴을 사용하여 사이즈 그리드 파싱
    
    Args:
        size_row_chars: size 행의 문자 데이터 [(x, text), ...]
        qty_row_chars: qty 행의 문자 데이터 [(x, text), ...]
        size_cells_template: 저장된 size 셀 패턴 [{'text': ..., 'xCenter': ..., ...}, ...]
        qty_cells_template: 저장된 qty 셀 패턴 [{'text': ..., 'xCenter': ..., ...}, ...]
        
    Returns:
        dict: {size: qty, ...} 형식의 딕셔너리 또는 None
    """
    # 실제 셀 추출
    def extract_cells(row_chars):
        sorted_chars = sorted(row_chars, key=lambda c: c[0])
        cells = []
        current_cell = []
        prev_x = None
        threshold = 15
        
        for char_x, char_text in sorted_chars:
            if prev_x is not None and abs(char_x - prev_x) > threshold:
                if current_cell:
                    text = ''.join(c[1] for c in current_cell).strip()
                    if text:
                        x_start = min(c[0] for c in current_cell)
                        x_end = max(c[0] for c in current_cell)
                        x_center = (x_start + x_end) / 2
                        cells.append({'text': text, 'xCenter': x_center, 'xStart': x_start, 'xEnd': x_end})
                    current_cell = []
            current_cell.append((char_x, char_text))
            prev_x = char_x
        
        if current_cell:
            text = ''.join(c[1] for c in current_cell).strip()
            if text:
                x_start = min(c[0] for c in current_cell)
                x_end = max(c[0] for c in current_cell)
                x_center = (x_start + x_end) / 2
                cells.append({'text': text, 'xCenter': x_center, 'xStart': x_start, 'xEnd': x_end})
        
        return cells
    
    size_cells = extract_cells(size_row_chars)
    qty_cells = extract_cells(qty_row_chars)
    
    # 템플릿 셀과 실제 셀 매핑
    size_grid_dict = {}
    
    for size_cell_template in size_cells_template:
        template_x_center = size_cell_template.get('xCenter', 0)
        template_size_text = size_cell_template.get('text', '')
        
        # 가장 가까운 실제 size 셀 찾기
        matched_size_cell = None
        min_distance = float('inf')
        
        for size_cell in size_cells:
            distance = abs(size_cell['xCenter'] - template_x_center)
            if distance < min_distance:
                min_distance = distance
                matched_size_cell = size_cell
        
        if matched_size_cell:
            size_text = matched_size_cell['text']
            
            # 해당 size 셀과 매칭되는 qty 찾기
            matched_qty = None
            min_qty_distance = float('inf')
            
            for qty_cell_template in qty_cells_template:
                if abs(qty_cell_template.get('xCenter', 0) - template_x_center) < 20:  # 같은 열
                    # 실제 qty 셀 찾기
                    for qty_cell in qty_cells:
                        qty_distance = abs(qty_cell['xCenter'] - qty_cell_template.get('xCenter', 0))
                        if qty_distance < min_qty_distance:
                            min_qty_distance = qty_distance
                            matched_qty = qty_cell['text']
            
            # 수량 추출
            if matched_qty:
                import re
                numbers = re.findall(r'\d+', matched_qty)
                qty_value = int(numbers[0]) if numbers else 0
            else:
                qty_value = 0
            
            size_grid_dict[size_text] = qty_value
    
    return size_grid_dict if size_grid_dict else None

def extract_with_y_scan(pdf_path, template):
    """
    Y축 스캔 방식으로 반복 제품 추출
    필드 영역(X 범위 AND Y 범위) 내의 텍스트만 정확히 수집
    """
    all_products = []
    fields_template = template.get('fields', [])
    
    if not fields_template: 
        return []
    
    # 템플릿의 첫 제품 기준 Y 위치 계산 (JavaScript 좌표계, 위가 큰값)
    first_product_top_js = max(f['bbox']['y0'] for f in fields_template)
    
    # 필드 정보 저장 (템플릿 기준, 패턴 포함)
    field_configs = {}
    for field_info in fields_template:
        field_name = field_info['field']
        bbox = field_info['bbox']
        # 첫 제품의 top에서의 오프셋 (JavaScript 좌표계)
        offset = first_product_top_js - bbox['y0']
        field_configs[field_name] = {
            'offset': offset,
            'x0': min(bbox['x0'], bbox['x1']),
            'x1': max(bbox['x0'], bbox['x1']),
            'y0_template': bbox['y0'],  # 템플릿에서의 Y 위치
            'y1_template': bbox['y1'],
            'height': abs(bbox['y0'] - bbox['y1']),
            'type': field_info.get('type', 'text'),
            'pattern': field_info.get('pattern')  # 텍스트 패턴 저장
        }
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            page_height = page.height
            
            # 모든 문자 추출 및 JavaScript 좌표계로 변환
            chars = page.chars
            if not chars:
                continue
            
            chars_with_js_y = []
            for char in chars:
                # pdfplumber의 top은 PDF 좌표계에서 위쪽 값 (큰 값)
                # 템플릿의 y0, y1도 같은 좌표계를 사용하므로 변환 불필요
                chars_with_js_y.append({
                    'text': char['text'],
                    'x': char['x0'],
                    'y': char['top']  # PDF 좌표계 그대로 사용 (위가 큰 값)
                })
            
            # Y 좌표 기준 정렬 (위에서 아래로, 큰 값부터)
            chars_with_js_y.sort(key=lambda c: -c['y'])
            
            # 제품 행 찾기: 템플릿의 첫 제품 기준 Y 위치와 정확히 일치하는 패턴 찾기
            product_row_y_positions = []
            y_tolerance = 2  # Y 위치 허용 오차 (픽셀) - 더 엄격하게
            row_spacing_threshold = 30  # 제품 행 간 최소 간격 (픽셀) - 더 크게
            
            # 템플릿의 첫 제품 기준 Y 위치 주변에서만 제품 행 찾기
            # 실제 제품 행은 첫 제품 기준 Y 위치와 유사한 위치여야 함
            template_y_range = (first_product_top_js - 5, first_product_top_js + 5)  # 첫 제품 Y ±5픽셀
            
            # 각 Y 위치에서 제품 행 패턴 확인 (템플릿 Y 위치와 유사한 위치만)
            unique_y_positions = sorted(set(round(c['y'] / y_tolerance) * y_tolerance for c in chars_with_js_y), reverse=True)
            
            for test_y in unique_y_positions:
                # 이미 추가된 제품 행과 너무 가까우면 스킵
                if product_row_y_positions and min(abs(test_y - py) for py in product_row_y_positions) < row_spacing_threshold:
                    continue
                
                # 이 Y 위치가 제품 행인지 확인 (패턴 매칭 사용)
                all_fields_matched = True
                matched_fields_count = 0
                
                for field_name, field_config in field_configs.items():
                    # 이 제품 행에서 필드의 예상 Y 위치 계산
                    expected_field_y0 = test_y - field_config['offset']
                    expected_field_y1 = expected_field_y0 - field_config['height']
                    
                    x0, x1 = field_config['x0'], field_config['x1']
                    
                    # 필드 영역(X AND Y) 내의 텍스트 추출
                    field_chars = []
                    for char_data in chars_with_js_y:
                        char_y = char_data['y']
                        char_x = char_data['x']
                        if (x0 <= char_x <= x1) and (expected_field_y1 <= char_y <= expected_field_y0):
                            field_chars.append(char_data)
                    
                    if not field_chars:
                        all_fields_matched = False
                        break
                    
                    # 텍스트 추출
                    field_text = ''.join(c['text'] for c in sorted(field_chars, key=lambda c: (c['y'], c['x']))).strip()
                    
                    # 패턴 매칭 (패턴이 있으면 사용)
                    pattern = field_config.get('pattern')
                    if pattern:
                        if field_config['type'] == 'table' and field_name == 'size_grid':
                            # 사이즈 그리드는 별도 처리 (나중에)
                            matched_fields_count += 1
                        else:
                            # 일반 텍스트 필드: 정규식 패턴 매칭
                            import re
                            regex_str = pattern.get('regex')
                            if regex_str:
                                # 정규식 문자열을 컴파일
                                try:
                                    pattern_obj = re.compile(regex_str)
                                    if pattern_obj.search(field_text):
                                        matched_fields_count += 1
                                    else:
                                        # 패턴 불일치 시에도 텍스트가 있으면 매칭으로 간주 (유연성)
                                        if field_text:
                                            matched_fields_count += 1
                                except:
                                    # 정규식 오류 시 텍스트만 확인
                                    if field_text:
                                        matched_fields_count += 1
                            else:
                                # 패턴이 없으면 텍스트만 확인
                                if field_text:
                                    matched_fields_count += 1
                    else:
                        # 패턴이 없으면 텍스트만 확인
                        if field_text:
                            matched_fields_count += 1
                
                # 모든 필드가 매칭되고, 적어도 3개 이상의 필드가 있어야 제품 행으로 인식
                if all_fields_matched and matched_fields_count >= min(3, len(field_configs)):
                    product_row_y_positions.append(test_y)
            
            # 제품 행별로 데이터 추출
            for product_base_y in sorted(product_row_y_positions, reverse=True):
                product_data = {}
                
                for field_name, field_config in field_configs.items():
                    # 이 제품 행에서 필드의 Y 위치 계산
                    field_y0 = product_base_y - field_config['offset']
                    field_y1 = field_y0 - field_config['height']
                    
                    x0, x1 = field_config['x0'], field_config['x1']
                    
                    # 필드 영역(X 범위 AND Y 범위) 내의 문자만 수집
                    field_chars = []
                    for char_data in chars_with_js_y:
                        char_y = char_data['y']  # PDF 좌표계 (위가 큰 값)
                        char_x = char_data['x']
                        char_text = char_data['text'].strip()
                        
                        if not char_text:
                            continue
                        
                        # X 범위와 Y 범위 모두 정확히 체크
                        # field_y0가 위쪽 (큰 값), field_y1이 아래쪽 (작은 값)
                        if (x0 <= char_x <= x1) and (field_y1 <= char_y <= field_y0):
                            field_chars.append((char_y, char_x, char_text))
                    
                    # 사이즈 그리드 특별 처리
                    if field_name == 'size_grid' and field_config['type'] == 'table':
                        pattern = field_config.get('pattern')
                        product_data[field_name] = parse_size_grid(field_chars, pattern)
                    else:
                        # 텍스트 추출: 같은 Y 위치의 문자들을 X 좌표 순으로 정렬하여 합치기
                        if field_chars:
                            # Y 위치별로 그룹화
                            y_groups = {}
                            for char_y, char_x, char_text in field_chars:
                                y_rounded = round(char_y)  # Y 좌표 반올림
                                if y_rounded not in y_groups:
                                    y_groups[y_rounded] = []
                                y_groups[y_rounded].append((char_x, char_text))
                            
                            # 각 Y 그룹을 처리
                            text_lines = []
                            for y_pos in sorted(y_groups.keys(), reverse=True):
                                chars_in_line = y_groups[y_pos]
                                chars_in_line.sort(key=lambda c: c[0])  # X 좌표 순 정렬
                                
                                # 문자들을 합쳐서 단어 만들기
                                line_text = ''.join(c[1] for c in chars_in_line).strip()
                                if line_text:
                                    text_lines.append(line_text)
                            
                            # 여러 줄을 공백으로 합치기
                            product_data[field_name] = ' '.join(text_lines).strip() if text_lines else None
                        else:
                            product_data[field_name] = None
                
                # 모든 필드가 채워진 경우에만 제품으로 추가
                if all(v for v in product_data.values() if v):
                    all_products.append(product_data)
        
        return all_products

@app.route('/extract', methods=['POST'])
def extract():
    """
    PDF 파일과 bbox 정보를 받아서 데이터 추출
    Y축 스캔 모드 또는 단일 위치 추출 모드 지원
    
    Request:
        - pdf: PDF 파일 (multipart/form-data)
        - template: JSON 문자열 (템플릿 정보)
          - pattern_extraction: true면 Y축 스캔, false면 단일 위치 추출
    """
    try:
        if 'pdf' not in request.files:
            return jsonify({'error': 'PDF 파일이 없습니다'}), 400
        
        pdf_file = request.files['pdf']
        template_str = request.form.get('template')
        
        if not template_str:
            return jsonify({'error': '템플릿이 없습니다'}), 400
        
        template = json.loads(template_str)
        use_pattern_extraction = template.get('pattern_extraction', False)
        
        # 임시 파일로 PDF 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            pdf_file.save(tmp_file.name)
            tmp_path = tmp_file.name
        
        try:
            if use_pattern_extraction:
                # Y축 스캔 방식
                products = extract_with_y_scan(tmp_path, template)
                
                # 필드별 배열로 변환
                extracted_data = {}
                for field_info in template.get('fields', []):
                    field_name = field_info['field']
                    extracted_data[field_name] = [p.get(field_name) for p in products]
                
                return jsonify({'success': True, 'data': extracted_data, 'products': products})
            else:
                # 기존 방식 (단일 위치 추출)
                extracted_data = {}
                
                with pdfplumber.open(tmp_path) as pdf:
                    for field_info in template.get('fields', []):
                        field_name = field_info['field']
                        bbox = field_info['bbox']
                        field_type = field_info.get('type', 'text')
                        page_num = bbox['page']
                        
                        if page_num >= len(pdf.pages):
                            extracted_data[field_name] = None
                            continue
                        
                        page = pdf.pages[page_num]
                        
                        # PDF 좌표계 변환
                        x_left = min(bbox['x0'], bbox['x1'])
                        x_right = max(bbox['x0'], bbox['x1'])
                        y_bottom = page.height - bbox['y0']
                        y_top = page.height - bbox['y1']
                        crop_box = (x_left, y_bottom, x_right, y_top)
                        
                        crop = page.crop(crop_box)
                        
                        if field_type == 'table' or field_name == 'size_grid':
                            tables = crop.extract_tables()
                            if tables and len(tables) > 0:
                                df = pd.DataFrame(tables[0])
                                df = df.fillna('')
                                for col in df.columns:
                                    try:
                                        numeric_series = pd.to_numeric(df[col], errors='coerce')
                                        df[col] = numeric_series.where(pd.notna(numeric_series), df[col])
                                    except:
                                        pass
                                records = df.to_dict('records')
                                for record in records:
                                    for key, value in record.items():
                                        if pd.isna(value) or (isinstance(value, (float, int)) and np.isnan(value)):
                                            record[key] = None
                                extracted_data[field_name] = records
                            else:
                                extracted_data[field_name] = []
                        else:
                            text = crop.extract_text()
                            extracted_data[field_name] = text.strip() if text else ''
                
                return jsonify({'success': True, 'data': extracted_data})
            
        finally:
            # 임시 파일 삭제
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except json.JSONDecodeError as e:
        return jsonify({'error': f'템플릿 JSON 파싱 오류: {str(e)}'}), 400
    except Exception as e:
        import traceback
        return jsonify({'error': f'추출 오류: {str(e)}\n{traceback.format_exc()}'}), 500

@app.route('/health', methods=['GET'])
def health():
    """헬스 체크 엔드포인트"""
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=True)

