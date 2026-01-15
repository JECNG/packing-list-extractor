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
    
    # 필드 정보 저장 (템플릿 기준)
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
            'type': field_info.get('type', 'text')
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
                y_js = page_height - char['top']  # JavaScript 좌표계 (위가 큰 값)
                chars_with_js_y.append({
                    'text': char['text'],
                    'x': char['x0'],
                    'y_js': y_js
                })
            
            # Y 좌표 기준 정렬 (위에서 아래로)
            chars_with_js_y.sort(key=lambda c: -c['y_js'])
            
            # 제품 행 찾기: 템플릿의 첫 제품 기준 Y 위치와 유사한 위치 찾기
            product_row_y_positions = []
            y_tolerance = 3  # Y 위치 허용 오차 (픽셀)
            row_spacing_threshold = 20  # 제품 행 간 최소 간격 (픽셀)
            
            # 각 Y 위치에서 제품 행 패턴 확인
            unique_y_positions = sorted(set(round(c['y_js'] / y_tolerance) * y_tolerance for c in chars_with_js_y), reverse=True)
            
            for test_y in unique_y_positions:
                # 이미 추가된 제품 행과 너무 가까우면 스킵
                if product_row_y_positions and min(abs(test_y - py) for py in product_row_y_positions) < row_spacing_threshold:
                    continue
                
                # 이 Y 위치가 제품 행인지 확인 (각 필드 영역에 텍스트가 있는지 체크)
                matched_fields = 0
                for field_name, field_config in field_configs.items():
                    # 이 제품 행에서 필드의 예상 Y 위치 계산
                    expected_field_y0 = test_y - field_config['offset']
                    expected_field_y1 = expected_field_y0 - field_config['height']
                    
                    x0, x1 = field_config['x0'], field_config['x1']
                    # 필드 영역(X AND Y) 내에 텍스트가 있는지 확인
                    for char_data in chars_with_js_y:
                        char_y = char_data['y_js']
                        char_x = char_data['x']
                        if (x0 <= char_x <= x1) and (expected_field_y1 <= char_y <= expected_field_y0):
                            matched_fields += 1
                            break
                
                # 필드의 절반 이상이 매칭되면 제품 행으로 인식
                if matched_fields >= len(field_configs) * 0.5:
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
                        char_y = char_data['y_js']
                        char_x = char_data['x']
                        char_text = char_data['text'].strip()
                        
                        if not char_text:
                            continue
                        
                        # X 범위와 Y 범위 모두 정확히 체크
                        if (x0 <= char_x <= x1) and (field_y1 <= char_y <= field_y0):
                            field_chars.append((char_y, char_x, char_text))
                    
                    # Y 위치로 정렬 후 텍스트 합치기
                    if field_chars:
                        field_chars.sort(key=lambda c: (-c[0], c[1]))  # Y 큰값 먼저, 그 다음 X
                        product_data[field_name] = ' '.join(c[2] for c in field_chars).strip()
                    else:
                        product_data[field_name] = None
                
                # 빈 제품이 아니면 추가
                if any(v for v in product_data.values() if v):
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

