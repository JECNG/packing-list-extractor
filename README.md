# 패킹리스트 템플릿 기반 추출기

업체별 PDF 템플릿을 만들어서 자동으로 데이터를 추출하는 도구입니다.

## 주요 특징

- **템플릿 기반 Zonal Extraction**: 사용자가 직접 필드 영역을 지정하여 업체별 양식 다양성 문제 해결
- **테이블 구조 보존**: Python 백엔드(pdfplumber)로 사이즈 그리드 같은 테이블 데이터의 행/열 구조 유지
- **빈 셀 자동 처리**: 테이블의 빈 셀을 0으로 자동 채움 (문제3 해결)
- **클라이언트 사이드 UI**: PDF.js로 브라우저에서 PDF 미리보기 및 템플릿 편집

## 기능

1. **템플릿 만들기**
   - PDF 미리보기
   - 필드 버튼으로 영역 선택 (제품코드, 브랜드, 사이즈 그리드 등)
   - 드래그로 영역 지정
   - 업체별 템플릿 저장 (localStorage)

2. **데이터 추출**
   - 저장된 템플릿으로 자동 추출
   - Python 백엔드로 테이블 구조 보존
   - Excel 다운로드

## 설치 및 실행

### 1. Python 백엔드 설정

```bash
# 가상환경 생성 (선택사항)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 라이브러리 설치
pip install -r requirements.txt

# 백엔드 서버 실행
python app.py
```

백엔드 서버가 `http://localhost:5000`에서 실행됩니다.

### 2. 프론트엔드 실행

#### 방법 1: 로컬 파일 (개발용)
- `index.html`을 브라우저에서 직접 열기

#### 방법 2: GitHub Pages (프로덕션)
- GitHub Pages에 배포 (아래 참조)
- ⚠️ 주의: GitHub Pages는 정적 사이트만 지원하므로 Python 백엔드가 필요하면 다른 호스팅 필요

## 사용 방법

1. **Python 백엔드 실행** (`python app.py`)

2. **템플릿 만들기**:
   - `index.html`을 브라우저에서 열기
   - "템플릿 만들기" 탭 선택
   - PDF 파일 업로드
   - 필드 버튼 클릭 (예: "제품코드", "사이즈그리드")
   - PDF에서 해당 영역 드래그로 선택
   - 업체명 입력 후 "템플릿 저장"

3. **데이터 추출**:
   - "데이터 추출" 탭 선택
   - 업체 선택
   - 새 PDF 파일 업로드
   - "데이터 추출" 클릭
   - 결과 확인 및 Excel 다운로드

## 기술 스택

- **Frontend**: HTML, JavaScript
- **PDF 렌더링**: PDF.js (브라우저)
- **PDF 파싱**: pdfplumber (Python 백엔드)
- **테이블 처리**: pandas (빈 셀 → 0 변환)
- **Excel 생성**: SheetJS (xlsx.js)
- **백엔드**: Flask + Flask-CORS
- **저장소**: localStorage (템플릿)

## 아키텍처

### 프론트엔드 (JavaScript)
- PDF.js로 PDF 미리보기 및 템플릿 편집
- bbox(바운딩 박스) 좌표 캡처 및 localStorage 저장
- 템플릿 데이터를 백엔드 API로 전송

### 백엔드 (Python Flask)
- `/extract` API: PDF 파일 + 템플릿 정보 받기
- pdfplumber로 bbox 영역 크롭 및 추출
- 텍스트 필드: `crop.extract_text()`
- 테이블 필드: `crop.extract_tables()` → pandas DataFrame → 빈 셀 0으로 채움
- JSON 응답 반환

## 문제 해결

### 문제1: 업체별 양식 다양성
✅ **해결**: 템플릿 기반 zonal extraction. 각 업체별로 bbox 영역만 지정하면 됨.

### 문제2: 제품코드 변동성
✅ **해결**: bbox 기반 추출로 코드 형식에 관계없이 영역만 지정하면 자동 추출.

### 문제3: 사이즈 그리드 빈 셀 누락
✅ **해결**: Python 백엔드에서 `pandas.fillna(0)`로 빈 셀을 0으로 채움. 테이블 구조 보존.

## GitHub Pages 배포

### 1. GitHub에 업로드

```bash
git remote add origin https://github.com/JECNG/packing-list-extractor.git
git branch -M main
git add .
git commit -m "Initial commit"
git push -u origin main
```

### 2. GitHub Pages 활성화

1. GitHub 저장소 → **Settings**
2. 왼쪽 메뉴에서 **Pages** 선택
3. Source: `Deploy from a branch`
4. Branch: `main` / `/ (root)`
5. **Save**

그러면 `https://YOUR_USERNAME.github.io/packing-list-extractor/` 에서 접속 가능합니다!

⚠️ **주의**: GitHub Pages는 정적 파일만 호스팅하므로 Python 백엔드는 별도 서버 필요 (예: Heroku, Railway, Render 등)

## 개발 로드맵

- [x] 기본 템플릿 편집기 (bbox 드래그)
- [x] Python 백엔드 추가 (테이블 처리)
- [ ] 필드 타입 지정 UI (text/table 선택)
- [ ] bbox 정밀도 강화 (resize/move 버튼)
- [ ] 에러 핸들링 강화
- [ ] 템플릿 내보내기/가져오기 (JSON 파일)

## 참고

- 템플릿은 브라우저 localStorage에 저장됩니다
- Python 백엔드는 로컬에서 실행 필요 (`python app.py`)
- 테이블 필드는 `type: "table"`로 지정하면 구조 보존 (기본값: `type: "text"`)
