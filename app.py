from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import pandas as pd
import json
import tempfile
import os

app = Flask(__name__)
CORS(app)  # 프론트엔드에서 API 호출 허용

@app.route('/extract', methods=['POST'])
def extract():
    """
    PDF 파일과 bbox 정보를 받아서 데이터 추출
    
    Request:
        - pdf: PDF 파일 (multipart/form-data)
        - template: JSON 문자열 (템플릿 정보)
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
                    field_type = field_info.get('type', 'text')
                    page_num = bbox['page']
                    
                    if page_num >= len(pdf.pages):
                        extracted_data[field_name] = None
                        continue
                    
                    page = pdf.pages[page_num]
                    
                    # PDF 좌표계 변환 (pdfplumber는 왼쪽 아래가 (0,0))
                    # JavaScript bbox: y0=위(큰값), y1=아래(작은값)
                    # pdfplumber crop: (x0, y0_bottom, x1, y1_top)
                    y_bottom = page.height - bbox['y0']  # JavaScript y0 (위) -> pdfplumber y0 (아래)
                    y_top = page.height - bbox['y1']     # JavaScript y1 (아래) -> pdfplumber y1 (위)
                    crop_box = (
                        min(bbox['x0'], bbox['x1']),
                        min(y_bottom, y_top),
                        max(bbox['x0'], bbox['x1']),
                        max(y_bottom, y_top)
                    )
                    
                    crop = page.crop(crop_box)
                    
                    if field_type == 'table' or field_name == 'size_grid':
                        # 테이블 추출
                        tables = crop.extract_tables()
                        if tables and len(tables) > 0:
                            df = pd.DataFrame(tables[0])
                            df = df.fillna(0)  # 빈 셀을 0으로 채움
                            # 숫자 변환 가능한 셀은 숫자로
                            for col in df.columns:
                                df[col] = pd.to_numeric(df[col], errors='ignore')
                            extracted_data[field_name] = df.to_dict('records')
                        else:
                            extracted_data[field_name] = []
                    else:
                        # 텍스트 추출
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
        return jsonify({'error': f'추출 오류: {str(e)}'}), 500

@app.route('/health', methods=['GET'])
def health():
    """헬스 체크 엔드포인트"""
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=True)

