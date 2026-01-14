// PDF.js 설정
if (typeof pdfjsLib !== 'undefined') {
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
} else {
    // PDF.js가 로드되기를 기다림
    window.addEventListener('load', () => {
        if (typeof pdfjsLib !== 'undefined') {
            pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
        }
    });
}

// 전역 변수
let currentTab = 'editor';
let templates = JSON.parse(localStorage.getItem('templates') || '{}');
let currentPdfDoc = null;
let currentPage = null;
let currentViewport = null;
let currentPageRealViewport = null;  // scale=1.0인 실제 PDF 좌표계
let currentPageNum = 1;
let selectedField = null;
let highlights = [];

// 필드 정의 및 색상
const DEFAULT_FIELDS = [
    { name: 'code', label: '제품코드', color: '#667eea' },
    { name: 'brand', label: '브랜드', color: '#f093fb' },
    { name: 'season', label: '시즌', color: '#4facfe' },
    { name: 'description', label: '상품명', color: '#43e97b' },
    { name: 'color', label: '컬러', color: '#fa709a' },
    { name: 'price', label: '가격', color: '#fee140' },
    { name: 'origin', label: '원산지', color: '#30cfd0' },
    { name: 'size_grid', label: '사이즈 그리드', color: '#ff6b6b' }
];

let customFields = JSON.parse(localStorage.getItem('customFields') || '[]');
let fieldDefinitions = [...DEFAULT_FIELDS, ...customFields.map(f => ({ name: f.name, label: f.label, color: f.color }))];

// Undo/Redo 히스토리
let undoStack = [];
let redoStack = [];

// 백엔드 API URL (Render 배포 후 여기에 URL 입력)
const API_URL = 'https://packing-list-extractor-api.onrender.com';

// 탭 전환
function showTab(tabName) {
    currentTab = tabName;
    
    // 탭 버튼 활성화
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');
    
    // 탭 내용 표시
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(tabName + '-tab').classList.add('active');
    
    // 탭별 콘텐츠 로드
    if (tabName === 'editor') {
        loadEditorTab();
    } else if (tabName === 'extractor') {
        loadExtractorTab();
    }
}

// 템플릿 에디터 탭 로드
function loadEditorTab() {
    updateFieldDefinitions();
    const content = document.getElementById('editor-content');
    
    // 필드 버튼 HTML 생성
    const fieldButtonsHtml = fieldDefinitions.map(field => 
        `<button class="field-btn" data-field="${field.name}" onclick="selectField('${field.name}')" style="border-left: 4px solid ${field.color};">
            ${field.label}
        </button>`
    ).join('');
    
    content.innerHTML = `
        <div style="display: grid; grid-template-columns: minmax(0, 1fr) 350px; gap: 20px;">
            <!-- PDF 뷰어 영역 -->
            <div>
                <div style="background: #f9f9f9; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                    <input type="file" id="pdf-upload" accept=".pdf" style="margin-bottom: 10px;">
                    <div style="margin-top: 10px; display: flex; align-items: center; gap: 10px;">
                        <button onclick="prevPage()" style="padding: 8px 15px;">이전 페이지</button>
                        <span id="page-info">페이지: 1</span>
                        <button onclick="nextPage()" style="padding: 8px 15px;">다음 페이지</button>
                        <div style="margin-left: auto; display: flex; gap: 5px;">
                            <button onclick="undoAction()" title="되돌리기 (Ctrl+Z)" style="padding: 8px 12px; background: #6c757d; color: white; border: none; border-radius: 4px; cursor: pointer;">↶</button>
                            <button onclick="redoAction()" title="다시하기 (Ctrl+Y)" style="padding: 8px 12px; background: #6c757d; color: white; border: none; border-radius: 4px; cursor: pointer;">↷</button>
                            <button onclick="removeSelectedFieldHighlight()" title="선택 필드 제거" style="padding: 8px 12px; background: #dc3545; color: white; border: none; border-radius: 4px; cursor: pointer;">✕</button>
                        </div>
                    </div>
                </div>
                <div id="pdf-viewer" style="border: 2px solid #ddd; border-radius: 8px; position: relative; background: white; min-height: 800px; max-width: 100%; overflow: auto;">
                    <div style="text-align: center; padding: 200px; color: #999;">
                        PDF 파일을 업로드하세요
                    </div>
                </div>
            </div>
            
            <!-- 필드 선택 영역 -->
            <div style="min-width: 350px; max-width: 350px;">
                <h3 style="margin-bottom: 20px;">필드 선택</h3>
                <div id="field-buttons-container" style="display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px; max-height: 300px; overflow-y: auto;">
                    ${fieldButtonsHtml}
                </div>
                
                <div style="margin-top: 20px; padding: 15px; background: #f9f9f9; border-radius: 8px;">
                    <h4 style="margin-bottom: 10px; font-size: 14px;">템플릿 관리</h4>
                    <div style="display: flex; gap: 5px; margin-bottom: 15px;">
                        <button onclick="exportTemplates()" style="flex: 1; padding: 8px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px;">내보내기</button>
                        <label style="flex: 1; padding: 8px; background: #17a2b8; color: white; border-radius: 4px; cursor: pointer; text-align: center; font-size: 12px;">
                            가져오기
                            <input type="file" accept=".json" onchange="importTemplates(event)" style="display: none;">
                        </label>
                    </div>
                </div>
                
                <div style="margin-top: 20px; padding: 20px; background: #f9f9f9; border-radius: 8px;">
                    <h4 style="margin-bottom: 15px;">템플릿 정보</h4>
                    <input type="text" id="vendor-name" placeholder="업체명 입력" style="width: 100%; padding: 10px; margin-bottom: 15px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box;">
                    <button onclick="saveTemplate()" style="width: 100%; padding: 12px; background: #667eea; color: white; border: none; border-radius: 5px; font-weight: 600; cursor: pointer;">
                        템플릿 저장
                    </button>
                </div>
                
                <div id="template-preview" style="margin-top: 20px; padding: 15px; background: #f0f0f0; border-radius: 8px; font-size: 12px;">
                    <strong>선택된 영역:</strong>
                    <div id="selected-areas"></div>
                </div>
            </div>
        </div>
    `;
    
    // PDF 업로드 이벤트
    document.getElementById('pdf-upload').addEventListener('change', handlePdfUpload);
    
    // 필드 버튼 스타일
    const style = document.createElement('style');
    style.textContent = `
        .field-btn {
            padding: 12px;
            background: white;
            border: 2px solid #ddd;
            border-radius: 5px;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.2s;
        }
        .field-btn:hover {
            background: #f0f0f0;
        }
        .field-btn.active {
            background: #667eea;
            color: white;
            border-color: #667eea;
            border-left-width: 4px !important;
        }
        .highlight-rect {
            position: absolute;
            border: 3px solid #ff6b6b;
            background: rgba(255, 107, 107, 0.2);
            pointer-events: none;
            z-index: 10;
        }
        .highlight-rect::after {
            content: attr(data-label);
            position: absolute;
            top: -20px;
            left: 0;
            background: var(--label-color, #ff6b6b);
            color: white;
            padding: 2px 8px;
            font-size: 12px;
            border-radius: 3px;
            white-space: nowrap;
        }
        .temp-rect {
            position: absolute;
            border: 2px dashed #667eea;
            background: rgba(102, 126, 234, 0.1);
            pointer-events: none;
            z-index: 5;
        }
    `;
    if (!document.getElementById('field-btn-style')) {
        style.id = 'field-btn-style';
        document.head.appendChild(style);
    }
}

// 데이터 추출 탭 로드
function loadExtractorTab() {
    const vendorList = Object.keys(templates);
    
    const content = document.getElementById('extractor-content');
    content.innerHTML = `
        <div style="max-width: 800px; margin: 0 auto;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h3 style="margin: 0;">데이터 추출</h3>
                <div style="display: flex; gap: 5px;">
                    <button onclick="exportTemplates()" style="padding: 8px 12px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px;">템플릿 내보내기</button>
                    <label style="padding: 8px 12px; background: #17a2b8; color: white; border-radius: 4px; cursor: pointer; text-align: center; font-size: 12px;">
                        템플릿 가져오기
                        <input type="file" accept=".json" onchange="importTemplates(event)" style="display: none;">
                    </label>
                </div>
            </div>
            
            <div style="background: #f9f9f9; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                <label style="display: block; margin-bottom: 10px; font-weight: 600;">업체 선택</label>
                <div style="display: flex; gap: 5px; margin-bottom: 20px;">
                    <select id="vendor-select" style="flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
                        <option value="">업체를 선택하세요</option>
                        ${vendorList.map(v => `<option value="${v}">${v}</option>`).join('')}
                    </select>
                    ${vendorList.length > 0 ? `<button onclick="deleteTemplate(document.getElementById('vendor-select').value)" style="padding: 10px 15px; background: #dc3545; color: white; border: none; border-radius: 5px; cursor: pointer;" title="선택된 템플릿 삭제">삭제</button>` : ''}
                </div>
                
                <label style="display: block; margin-bottom: 10px; font-weight: 600;">PDF 파일 업로드</label>
                <input type="file" id="extract-pdf" accept=".pdf" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; margin-bottom: 20px;">
                
                <button onclick="extractData()" style="width: 100%; padding: 12px; background: #667eea; color: white; border: none; border-radius: 5px; font-weight: 600; cursor: pointer;">
                    데이터 추출
                </button>
            </div>
            
            <div id="extract-result" style="margin-top: 20px;"></div>
        </div>
    `;
}

// PDF 업로드 처리
async function handlePdfUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    const viewer = document.getElementById('pdf-viewer');
    if (!viewer) return;
    
    viewer.innerHTML = '<div style="text-align: center; padding: 100px; color: #999;">PDF 로딩 중...</div>';
    
    try {
        const arrayBuffer = await file.arrayBuffer();
        currentPdfDoc = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
        currentPageNum = 1;
        highlights = [];
        await renderPage(currentPageNum);
    } catch (error) {
        console.error('PDF 로딩 오류:', error);
        viewer.innerHTML = `<div style="text-align: center; padding: 100px; color: red;">PDF 로딩 오류: ${error.message}</div>`;
    }
}

// PDF 페이지 렌더링
async function renderPage(pageNum) {
    if (!currentPdfDoc) {
        console.error('PDF 문서가 없습니다');
        return;
    }
    
    const viewer = document.getElementById('pdf-viewer');
    if (!viewer) {
        console.error('PDF 뷰어 요소를 찾을 수 없습니다');
        return;
    }
    
    try {
        currentPage = await currentPdfDoc.getPage(pageNum);
        currentViewport = currentPage.getViewport({ scale: 1.5 });  // 렌더링용
        currentPageRealViewport = currentPage.getViewport({ scale: 1.0 });  // 실제 PDF 좌표계 (bbox 저장용)
        
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        canvas.height = currentViewport.height;
        canvas.width = currentViewport.width;
        
        viewer.innerHTML = '';
        viewer.style.position = 'relative';
        viewer.appendChild(canvas);
        
        await currentPage.render({
            canvasContext: context,
            viewport: currentViewport
        }).promise;
        
        const pageInfo = document.getElementById('page-info');
        if (pageInfo) {
            pageInfo.textContent = `페이지: ${pageNum} / ${currentPdfDoc.numPages}`;
        }
        
        // 클릭 이벤트 추가
        setupPdfInteraction(canvas);
        
        // 기존 하이라이트 다시 그리기
        setTimeout(() => renderHighlights(), 100);
    } catch (error) {
        console.error('PDF 렌더링 오류:', error);
        viewer.innerHTML = `<div style="text-align: center; padding: 100px; color: red;">PDF 렌더링 오류: ${error.message}</div>`;
    }
}

// PDF 상호작용 설정 (드래그 선택) - viewport 변환 보정
let isDrawing = false;
let startX, startY, tempRect = null;

function setupPdfInteraction(canvas) {
    const viewer = document.getElementById('pdf-viewer');
    if (!viewer || !canvas) return;
    
    viewer.addEventListener('mousedown', (e) => {
        if (!selectedField) {
            alert('먼저 필드를 선택해주세요 (예: 제품코드 버튼 클릭)');
            return;
        }
        
        if (e.target.tagName !== 'CANVAS') return;
        
        const rect = canvas.getBoundingClientRect();
        startX = e.clientX - rect.left;
        startY = e.clientY - rect.top;
        isDrawing = true;
        
        // 임시 사각형 생성
        tempRect = document.createElement('div');
        tempRect.className = 'temp-rect';
        viewer.appendChild(tempRect);
    });
    
    viewer.addEventListener('mousemove', (e) => {
        if (!isDrawing || !tempRect) return;
        
        const rect = canvas.getBoundingClientRect();
        const currentX = e.clientX - rect.left;
        const currentY = e.clientY - rect.top;
        
        const left = Math.min(startX, currentX);
        const top = Math.min(startY, currentY);
        const width = Math.abs(currentX - startX);
        const height = Math.abs(currentY - startY);
        
        tempRect.style.left = left + 'px';
        tempRect.style.top = top + 'px';
        tempRect.style.width = width + 'px';
        tempRect.style.height = height + 'px';
    });
    
    viewer.addEventListener('mouseup', (e) => {
        if (!isDrawing || !tempRect) return;
        
        const rect = canvas.getBoundingClientRect();
        const endX = e.clientX - rect.left;
        const endY = e.clientY - rect.top;
        
        const width = Math.abs(endX - startX);
        const height = Math.abs(endY - startY);
        
        if (width > 10 && height > 10) {
            // 캔버스 좌표를 실제 PDF 좌표계로 변환 (scale=1.0 viewport 사용)
            // PDF 좌표계: 왼쪽 아래가 (0,0), Y축이 위로
            const pdfX0 = (Math.min(startX, endX) / canvas.width) * currentPageRealViewport.width;
            const pdfY0 = currentPageRealViewport.height - ((Math.min(startY, endY) / canvas.height) * currentPageRealViewport.height);
            const pdfX1 = (Math.max(startX, endX) / canvas.width) * currentPageRealViewport.width;
            const pdfY1 = currentPageRealViewport.height - ((Math.max(startY, endY) / canvas.height) * currentPageRealViewport.height);
            
            const bbox = {
                x0: pdfX0,
                y0: pdfY0,
                x1: pdfX1,
                y1: pdfY1,
                page: currentPageNum - 1  // 0-based
            };
            
            addHighlight(selectedField, bbox);
        }
        
        // 임시 사각형 제거
        if (tempRect) {
            tempRect.remove();
            tempRect = null;
        }
        isDrawing = false;
    });
}

// 필드 선택
function selectField(fieldName) {
    selectedField = fieldName;
    document.querySelectorAll('.field-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    const btn = document.querySelector(`[data-field="${fieldName}"]`);
    if (btn) {
        btn.classList.add('active');
        const field = fieldDefinitions.find(f => f.name === fieldName);
        if (field) {
            btn.style.borderLeftColor = field.color;
        }
    }
}

// 하이라이트 추가
function addHighlight(fieldName, bbox) {
    saveFieldStateToUndo();
    // 중복 제거 (같은 필드가 이미 있으면 교체)
    highlights = highlights.filter(h => !(h.field === fieldName && h.bbox.page === bbox.page));
    highlights.push({ field: fieldName, bbox: bbox });
    renderHighlights();
    updateTemplatePreview();
}

// 하이라이트 렌더링
function renderHighlights() {
    const viewer = document.getElementById('pdf-viewer');
    const canvas = viewer.querySelector('canvas');
    if (!canvas || !currentViewport) return;
    
    // 기존 하이라이트 제거
    viewer.querySelectorAll('.highlight-rect').forEach(el => el.remove());
    
    highlights.forEach(h => {
        if (h.bbox.page === currentPageNum - 1) {
            const rect = document.createElement('div');
            rect.className = 'highlight-rect';
            
            // 필드 색상 가져오기
            const fieldColor = getFieldColor(h.field);
            const fieldLabel = fieldDefinitions.find(f => f.name === h.field)?.label || h.field;
            
            // PDF 좌표를 캔버스 좌표로 변환 (역변환)
            // bbox는 scale=1.0 viewport 기준이므로, currentPageRealViewport를 사용해야 함
            const canvasX0 = (h.bbox.x0 / currentPageRealViewport.width) * canvas.width;
            const canvasY0 = canvas.height - ((h.bbox.y0 / currentPageRealViewport.height) * canvas.height);
            const canvasX1 = (h.bbox.x1 / currentPageRealViewport.width) * canvas.width;
            const canvasY1 = canvas.height - ((h.bbox.y1 / currentPageRealViewport.height) * canvas.height);
            
            rect.style.left = Math.min(canvasX0, canvasX1) + 'px';
            rect.style.top = Math.min(canvasY0, canvasY1) + 'px';
            rect.style.width = Math.abs(canvasX1 - canvasX0) + 'px';
            rect.style.height = Math.abs(canvasY1 - canvasY0) + 'px';
            rect.style.borderColor = fieldColor;
            rect.style.backgroundColor = hexToRgba(fieldColor, 0.2);
            rect.style.setProperty('--label-color', fieldColor);
            rect.setAttribute('data-label', fieldLabel);
            rect.setAttribute('data-field', h.field);
            
            viewer.appendChild(rect);
        }
    });
}

// 템플릿 미리보기 업데이트
function updateTemplatePreview() {
    const preview = document.getElementById('selected-areas');
    if (!preview) return;
    
    preview.innerHTML = highlights.map(h => 
        `<div>${h.field}: 페이지 ${h.bbox.page + 1}</div>`
    ).join('');
}

// 페이지 네비게이션
function prevPage() {
    if (currentPageNum > 1) {
        currentPageNum--;
        renderPage(currentPageNum);
    }
}

async function nextPage() {
    if (currentPdfDoc && currentPageNum < currentPdfDoc.numPages) {
        currentPageNum++;
        await renderPage(currentPageNum);
    }
}

// 템플릿 저장
function saveTemplate() {
    const vendorName = document.getElementById('vendor-name').value.trim();
    if (!vendorName) {
        alert('업체명을 입력해주세요.');
        return;
    }
    
    if (highlights.length === 0) {
        alert('필드를 선택해주세요.');
        return;
    }
    
    templates[vendorName] = {
        fields: highlights.map(h => ({
            field: h.field,
            bbox: h.bbox,
            type: h.field === 'size_grid' ? 'table' : 'text'  // 사이즈 그리드는 테이블로 처리
        }))
    };
    
    localStorage.setItem('templates', JSON.stringify(templates));
    alert(`템플릿 "${vendorName}"이 저장되었습니다!`);
    
    // 초기화
    highlights = [];
    selectedField = null;
    document.getElementById('vendor-name').value = '';
    document.querySelectorAll('.field-btn').forEach(btn => btn.classList.remove('active'));
    updateTemplatePreview();
    renderHighlights();
}

// PDF.js로 텍스트 추출 (bbox 영역)
async function extractTextFromBbox(pdfDoc, pageNum, bbox) {
    const page = await pdfDoc.getPage(pageNum);
    const textContent = await page.getTextContent();
    
    // bbox 영역 내의 텍스트 필터링
    const items = textContent.items.filter(item => {
        const transform = item.transform;
        const x = transform[4];  // X 좌표
        const y = transform[5];  // Y 좌표 (PDF 좌표계)
        
        // PDF 좌표계에서 bbox 확인 (y는 위에서 아래로)
        return x >= bbox.x0 && x <= bbox.x1 && 
               y >= bbox.y1 && y <= bbox.y0;  // y는 반대 (위가 큰 값)
    });
    
    return items.map(item => item.str).join(' ').trim();
}

// 데이터 추출 (백엔드 API 사용)
async function extractData() {
    const vendorName = document.getElementById('vendor-select').value;
    const fileInput = document.getElementById('extract-pdf');
    
    if (!vendorName) {
        alert('업체를 선택해주세요.');
        return;
    }
    
    if (!fileInput.files[0]) {
        alert('PDF 파일을 업로드해주세요.');
        return;
    }
    
    const template = templates[vendorName];
    if (!template || !template.fields) {
        alert('템플릿을 찾을 수 없습니다.');
        return;
    }
    
    const resultDiv = document.getElementById('extract-result');
    resultDiv.innerHTML = '<p>추출 중...</p>';
    
    try {
        const file = fileInput.files[0];
        
        // FormData 생성
        const formData = new FormData();
        formData.append('pdf', file);
        
        // 템플릿 정보 추가
        const templateData = {
            vendor: vendorName,
            pattern_extraction: true,  // Y축 스캔 방식 활성화
            fields: template.fields.map(f => ({
                field: f.field,
                bbox: f.bbox,
                type: f.type || (f.field === 'size_grid' ? 'table' : 'text')
            }))
        };
        formData.append('template', JSON.stringify(templateData));
        
        // 백엔드 API 호출
        const apiUrl = API_URL !== 'YOUR_RENDER_API_URL_HERE' ? API_URL : 'http://localhost:5000';
        const response = await fetch(`${apiUrl}/extract`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || '추출 실패');
        }
        
        const result = await response.json();
        const extractedData = result.data;
        
        // 결과 표시
        resultDiv.innerHTML = `
            <div style="background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                <h4>추출 결과</h4>
                <pre style="background: #f5f5f5; padding: 15px; border-radius: 5px; overflow-x: auto; max-height: 400px; overflow-y: auto;">${JSON.stringify(extractedData, null, 2)}</pre>
                <button onclick="downloadExcel(${JSON.stringify(extractedData).replace(/"/g, '&quot;')})" style="margin-top: 15px; padding: 10px 20px; background: #667eea; color: white; border: none; border-radius: 5px; cursor: pointer;">
                    Excel 다운로드
                </button>
            </div>
        `;
    } catch (error) {
        console.error('추출 오류:', error);
        resultDiv.innerHTML = `
            <div style="background: #fee; padding: 20px; border-radius: 8px; border: 1px solid #fcc;">
                <h4 style="color: #c00;">오류 발생</h4>
                <p style="color: #c00;">${error.message}</p>
                <p style="color: #666; font-size: 0.9em; margin-top: 10px;">
                    백엔드 서버가 실행 중인지 확인하세요.
                </p>
            </div>
        `;
    }
}

// 필드 색상 가져오기
function getFieldColor(fieldName) {
    const field = fieldDefinitions.find(f => f.name === fieldName);
    return field ? field.color : '#667eea';
}

// Hex 색상을 rgba로 변환
function hexToRgba(hex, alpha = 0.2) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

// 필드 정의 업데이트
function updateFieldDefinitions() {
    customFields = JSON.parse(localStorage.getItem('customFields') || '[]');
    fieldDefinitions = [...DEFAULT_FIELDS, ...customFields.map(f => ({ name: f.name, label: f.label, color: f.color }))];
}

// Undo 히스토리에 현재 상태 저장
function saveFieldStateToUndo() {
    undoStack.push(JSON.parse(JSON.stringify(highlights)));
    redoStack = []; // Redo 스택 초기화
    if (undoStack.length > 50) undoStack.shift(); // 최대 50개 유지
}

// Undo (되돌리기)
function undoAction() {
    if (undoStack.length === 0) return;
    redoStack.push(JSON.parse(JSON.stringify(highlights)));
    highlights = undoStack.pop();
    renderHighlights();
    updateTemplatePreview();
}

// Redo (다시하기)
function redoAction() {
    if (redoStack.length === 0) return;
    undoStack.push(JSON.parse(JSON.stringify(highlights)));
    highlights = redoStack.pop();
    renderHighlights();
    updateTemplatePreview();
}

// 선택된 필드의 하이라이트 제거 (필드 선택 취소)
function removeSelectedFieldHighlight() {
    if (!selectedField) return;
    highlights = highlights.filter(h => h.field !== selectedField || h.bbox.page !== currentPageNum - 1);
    saveFieldStateToUndo();
    renderHighlights();
    updateTemplatePreview();
}

// 템플릿 내보내기
function exportTemplates() {
    const dataStr = JSON.stringify(templates, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'templates.json';
    link.click();
    URL.revokeObjectURL(url);
}

// 템플릿 가져오기
function importTemplates(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = function(e) {
        try {
            const imported = JSON.parse(e.target.result);
            templates = { ...templates, ...imported };
            localStorage.setItem('templates', JSON.stringify(templates));
            alert('템플릿을 가져왔습니다!');
            if (currentTab === 'extractor') loadExtractorTab();
            event.target.value = ''; // 파일 입력 초기화
        } catch (error) {
            alert('템플릿 파일 형식이 올바르지 않습니다.');
        }
    };
    reader.readAsText(file);
}

// 템플릿 제거
function deleteTemplate(vendorName) {
    if (!vendorName) {
        alert('삭제할 템플릿을 선택해주세요.');
        return;
    }
    if (!confirm(`"${vendorName}" 템플릿을 삭제하시겠습니까?`)) return;
    delete templates[vendorName];
    localStorage.setItem('templates', JSON.stringify(templates));
    if (currentTab === 'extractor') loadExtractorTab();
    alert('템플릿이 삭제되었습니다.');
}

// Excel 다운로드
function downloadExcel(data) {
    const ws = XLSX.utils.json_to_sheet([data]);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Sheet1");
    XLSX.writeFile(wb, "extracted_data.xlsx");
}

// 키보드 단축키
document.addEventListener('keydown', (e) => {
    if (e.ctrlKey || e.metaKey) {
        if (e.key === 'z' && !e.shiftKey) {
            e.preventDefault();
            undoAction();
        } else if (e.key === 'y' || (e.key === 'z' && e.shiftKey)) {
            e.preventDefault();
            redoAction();
        }
    }
});

// 초기화
document.addEventListener('DOMContentLoaded', () => {
    loadEditorTab();
});
