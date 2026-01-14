from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import pdfplumber
import pandas as pd
import json
import os
import tempfile
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)  # CORS 활성화 (프론트엔드에서 API 호출 가능)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/extract', methods=['POST'])
def extract():
    """
    PDF 파일과 템플릿을 받아서 데이터 추출
    
    Request:
        - pdf: PDF 파일 (multipart/form-data)
        - template: JSON 문자열 (템플릿 정보)
        
    Template 구조:
        {
            "vendor": "업체명",
            "fields": [
                {
                    "field": "제품코드",
                    "bbox": {"x0": 100, "y0": 200, "x1": 300, "y1": 220, "page": 0},
                    "type": "text"  // 또는 "table"
                },
                {
                    "field": "사이즈그리드",
                    "bbox": {"x0": 50, "y0": 300, "x1": 500, "y1": 600, "page": 0},
                    "type": "table"
                }
            ]
        }
    """
    try:
        if 'pdf' not in request.files:
            return jsonify({'error': 'PDF 파일이 없습니다'}), 400
        
        pdf_file = request.files['pdf']
        template_str = request.form.get('template')
        
        if not template_str:
            return jsonify({'error': '템플릿이 없습니다'}), 400
        
        template = json.loads(template_str)
        
        # 임시 파일로 PDF 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            pdf_file.save(tmp_file.name)
            tmp_path = tmp_file.name
        
        try:
            extracted_data = {}
            
            with pdfplumber.open(tmp_path) as pdf:
                for field_info in template.get('fields', []):
                    field_name = field_info['field']
                    bbox = field_info['bbox']
                    field_type = field_info.get('type', 'text')  # 기본값: text
                    page_num = bbox['page']
                    
                    if page_num >= len(pdf.pages):
                        extracted_data[field_name] = None
                        continue
                    
                    page = pdf.pages[page_num]
                    
                    # PDF 좌표계: pdfplumber는 왼쪽 아래가 (0,0)
                    # bbox는 우리 시스템 기준이므로 변환 필요
                    crop_box = (
                        bbox['x0'],
                        page.height - bbox['y1'],  # y1을 pdfplumber 좌표로 변환
                        bbox['x1'],
                        page.height - bbox['y0']   # y0을 pdfplumber 좌표로 변환
                    )
                    
                    crop = page.crop(crop_box)
                    
                    if field_type == 'table':
                        # 테이블 추출 (사이즈 그리드 등)
                        tables = crop.extract_tables()
                        if tables and len(tables) > 0:
                            # 첫 번째 테이블 사용
                            df = pd.DataFrame(tables[0])
                            # 빈 셀을 0으로 채움 (문제3 해결)
                            df = df.fillna(0)
                            # 숫자로 변환 가능한 셀은 숫자로 변환
                            for col in df.columns:
                                df[col] = pd.to_numeric(df[col], errors='ignore')
                            
                            # 딕셔너리 리스트로 변환 (JSON 직렬화 가능)
                            extracted_data[field_name] = df.to_dict('records')
                        else:
                            extracted_data[field_name] = []
                    else:
                        # 일반 텍스트 추출
                        text = crop.extract_text()
                        extracted_data[field_name] = text.strip() if text else ''
            
            return jsonify({
                'success': True,
                'data': extracted_data
            })
            
        finally:
            # 임시 파일 삭제
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except json.JSONDecodeError as e:
        return jsonify({'error': f'템플릿 JSON 파싱 오류: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'추출 오류: {str(e)}'}), 500

if __name__ == '__main__':
    # 개발 모드: http://localhost:5000
    app.run(debug=True, port=5000)

