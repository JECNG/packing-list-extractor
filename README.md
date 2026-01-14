# 패킹리스트 템플릿 기반 추출기

업체별 PDF 템플릿을 만들어서 자동으로 데이터를 추출하는 도구입니다.

## 주요 특징

- **템플릿 기반 Zonal Extraction**: 사용자가 직접 필드 영역을 지정하여 업체별 양식 다양성 문제 해결
- **100% 클라이언트 사이드**: PDF.js로 브라우저에서 직접 텍스트 추출 (백엔드 불필요)
- **GitHub Pages 배포 가능**: 정적 파일만으로 완전히 동작
- **localStorage 템플릿 저장**: 브라우저에 템플릿 저장

## 기능

1. **템플릿 만들기**
   - PDF 미리보기
   - 필드 버튼으로 영역 선택 (제품코드, 브랜드, 사이즈 그리드 등)
   - 드래그로 영역 지정
   - 업체별 템플릿 저장

2. **데이터 추출**
   - 저장된 템플릿으로 자동 추출
   - PDF.js로 브라우저에서 직접 텍스트 추출
   - Excel 다운로드

## 사용 방법

1. **템플릿 만들기**:
   - `index.html`을 브라우저에서 열기
   - "템플릿 만들기" 탭 선택
   - PDF 파일 업로드
   - 필드 버튼 클릭 (예: "제품코드", "사이즈그리드")
   - PDF에서 해당 영역 드래그로 선택
   - 업체명 입력 후 "템플릿 저장"

2. **데이터 추출**:
   - "데이터 추출" 탭 선택
   - 업체 선택
   - 새 PDF 파일 업로드
   - "데이터 추출" 클릭
   - 결과 확인 및 Excel 다운로드

## 기술 스택

- **Frontend**: HTML, JavaScript
- **PDF 렌더링/추출**: PDF.js (브라우저)
- **Excel 생성**: SheetJS (xlsx.js)
- **저장소**: localStorage (템플릿)

## 아키텍처

### 클라이언트 사이드 전용
- PDF.js로 PDF 미리보기 및 텍스트 추출
- bbox(바운딩 박스) 좌표 캡처 및 localStorage 저장
- 모든 처리가 브라우저에서 완료 (서버 불필요)

## 문제 해결

### 문제1: 업체별 양식 다양성
✅ **해결**: 템플릿 기반 zonal extraction. 각 업체별로 bbox 영역만 지정하면 됨.

### 문제2: 제품코드 변동성
✅ **해결**: bbox 기반 추출로 코드 형식에 관계없이 영역만 지정하면 자동 추출.

### 문제3: 사이즈 그리드 빈 셀 누락
⚠️ **현재**: PDF.js의 `getTextContent()`로 텍스트 추출. 테이블 구조는 단순 텍스트로 추출됨.
- 향후 개선: 좌표 기반 테이블 파싱 또는 Python 백엔드 추가 가능

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

✅ **백엔드 불필요**: GitHub Pages에 바로 배포 가능 (정적 파일만)

## 개발

```bash
# 로컬에서 테스트
# index.html을 브라우저에서 직접 열기 (파일:// 프로토콜)
# 또는 로컬 서버 사용:
python -m http.server 8000
# http://localhost:8000 접속
```

## 참고

- 템플릿은 브라우저 localStorage에 저장됩니다
- PDF.js의 `getTextContent()` API를 사용하여 브라우저에서 직접 텍스트 추출
- GitHub Pages에 배포 가능 (정적 사이트)
- 백엔드 서버 불필요 (모든 처리가 브라우저에서 완료)
