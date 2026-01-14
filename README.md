# 패킹리스트 템플릿 기반 추출기

업체별 PDF 템플릿을 만들어서 자동으로 데이터를 추출하는 도구입니다.

## 기능

1. **템플릿 만들기**
   - PDF 미리보기
   - 필드 버튼으로 영역 선택 (제품코드, 브랜드, 사이즈 그리드 등)
   - 드래그로 영역 지정
   - 업체별 템플릿 저장

2. **데이터 추출**
   - 저장된 템플릿으로 자동 추출
   - Excel 다운로드

## 사용 방법

1. `index.html`을 브라우저에서 열기
2. "템플릿 만들기" 탭에서:
   - PDF 파일 업로드
   - 필드 버튼 클릭 (예: "제품코드")
   - PDF에서 해당 영역 드래그
   - 업체명 입력 후 "템플릿 저장"
3. "데이터 추출" 탭에서:
   - 업체 선택
   - 새 PDF 업로드
   - "데이터 추출" 클릭

## 기술 스택

- **Frontend**: HTML, JavaScript
- **PDF 렌더링**: PDF.js
- **Excel 생성**: SheetJS (xlsx.js)
- **저장소**: localStorage (템플릿)

## GitHub Pages 배포

### 1. GitHub에 업로드

Git 저장소가 이미 초기화되어 있습니다. 다음 명령어로 업로드하세요:

```bash
# GitHub에서 새 저장소 생성 후:
git remote add origin https://github.com/YOUR_USERNAME/packing-list-extractor.git
git branch -M main
git add .
git commit -m "Initial commit: 패킹리스트 템플릿 기반 추출기"
git push -u origin main
```

### 2. GitHub Pages 활성화

1. GitHub 저장소 → **Settings**
2. 왼쪽 메뉴에서 **Pages** 선택
3. Source: `Deploy from a branch`
4. Branch: `main` / `/ (root)`
5. **Save**

그러면 `https://YOUR_USERNAME.github.io/packing-list-extractor/` 에서 접속 가능합니다!

## 참고

- 템플릿은 브라우저 localStorage에 저장됩니다
- PDF.js의 `getTextContent()` API를 사용하여 브라우저에서 직접 텍스트 추출 가능
- GitHub Pages에 배포 가능 (정적 사이트)

## 개발

```bash
# 로컬에서 테스트
# index.html을 브라우저에서 직접 열기 (파일:// 프로토콜)
# 또는 로컬 서버 사용:
python -m http.server 8000
# http://localhost:8000 접속
```

## 라이선스

MIT
