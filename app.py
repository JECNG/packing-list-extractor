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
    """
    all_products = []
    fields_template = template.get('fields', [])
    
    if not fields_template:
        return []
    
    # 템플릿의 첫 제품 기준 Y 위치 계산 (JavaScript 좌표계)
    first_product_top_js = max(f['bbox']['y0'] for f in fields_template)
    
    # 필드들의 상대 Y 위치 계산 (첫 제품 기준)
    field_offsets = {}
    for field_info in fields_template:
        field_name = field_info['field']
        bbox = field_info['bbox']
        # 첫 제품의 top에서의 오프셋 (JavaScript 좌표계, 위가 큰값)
        offset = first_product_top_js - bbox['y0']
        field_offsets[field_name] = {
            'offset': offset,
            'x0': min(bbox['x0'], bbox['x1']),
            'x1': max(bbox['x0'], bbox['x1']),
            'height': abs(bbox['y0'] - bbox['y1']),
            'type': field_info.get('type', 'text')
        }
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            page_height = page.height
            
            # 모든 문자 추출
            chars = page.chars
            if not chars:
                continue
            
            # Y 좌표 기준 정렬 (pdfplumber: top이 큰 값이 위)
            # JavaScript 좌표계로 변환: y_js = page_height - top
            chars_with_js_y = []
            for char in chars:
                y_js = page_height - char['top']  # JavaScript 좌표계로 변환
                chars_with_js_y.append({
                    'text': char['text'],
                    'x': char['x0'],
                    'y_js': y_js,
                    'top': char['top'],
                    'bottom': char['bottom'],
                    'x0': char['x0'],
                    'x1': char['x1']
                })
            
            # Y 좌표 기준 정렬 (위에서 아래로)
            chars_with_js_y.sort(key=lambda c: -c['y_js'])
            
            # 제품 행을 Y 좌표 기준으로 그룹화
            row_threshold = 15  # 행 간격 threshold (픽셀)
            product_rows = []
            current_row = []
            prev_y = None
            
            for char_data in chars_with_js_y:
                char_y = char_data['y_js']
                char_text = char_data['text'].strip()
                
                if not char_text:
                    continue
                
                # Y 위치가 크게 변하면 새 행 시작
                if prev_y is not None and abs(char_y - prev_y) > row_threshold:
                    if current_row:
                        product_rows.append(current_row)
                        current_row = []
                
                current_row.append(char_data)
                prev_y = char_y
            
            # 마지막 행 추가
            if current_row:
                product_rows.append(current_row)
            
            # 각 제품 행에서 필드별로 데이터 추출
            for row_chars in product_rows:
                if not row_chars:
                    continue
                
                # 행의 기준 Y 위치 (가장 위쪽 문자)
                row_base_y = max(c['y_js'] for c in row_chars)
                
                # 각 필드별로 Y 범위 계산 및 텍스트 수집
                product_data = {}
                for field_name, field_config in field_offsets.items():
                    # 필드의 Y 범위 계산 (행 기준 Y에서 오프셋 적용)
                    field_y0 = row_base_y - field_config['offset']  # 필드 상단
                    field_y1 = field_y0 - field_config['height']    # 필드 하단
                    
                    x0, x1 = field_config['x0'], field_config['x1']
                    field_texts = []
                    
                    # 필드 영역(X 범위 AND Y 범위) 내의 문자만 수집
                    for char_data in row_chars:
                        char_y = char_data['y_js']
                        char_x = char_data['x']
                        char_text = char_data['text'].strip()
                        
                        # X 범위와 Y 범위 모두 체크
                        if (x0 <= char_x <= x1) and (field_y1 <= char_y <= field_y0):
                            field_texts.append(char_text)
                    
                    # 필드 영역 내 텍스트가 있으면 합치기
                    if field_texts:
                        product_data[field_name] = ' '.join(field_texts).strip()
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

