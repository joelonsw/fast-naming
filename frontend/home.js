// Form submission handler
document.getElementById('contestForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const submitBtn = document.getElementById('submitBtn');
    const btnText = submitBtn.querySelector('.btn-text');
    const btnLoading = submitBtn.querySelector('.btn-loading');
    
    // Show loading state
    submitBtn.disabled = true;
    btnText.style.display = 'none';
    btnLoading.style.display = 'flex';
    
    // Hide any previous results or errors
    hideResult();
    hideError();
    
    try {
        // Get form data
        const formData = new FormData(e.target);
        const requestData = {
            contestTitle: formData.get('contestTitle'),
            contestContent: formData.get('contestContent'),
            contestHeldBy: formData.get('contestHeldBy'),
            contestType: formData.get('contestType'),
            contestHeldByType: formData.get('contestHeldByType'),
            contestCriteria: formData.get('contestCriteria') || null
        };
        
        // Validate required fields
        if (!requestData.contestTitle || !requestData.contestContent || 
            !requestData.contestHeldBy || !requestData.contestType || 
            !requestData.contestHeldByType) {
            throw new Error('필수 항목을 모두 입력해주세요.');
        }
        
        console.log('Submitting request:', requestData);
        
        // Make API call
        const response = await fetch('/name', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        });
        
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.detail || '요청 처리 중 오류가 발생했습니다.');
        }
        
        if (!result.success) {
            throw new Error(result.error || '작명 생성에 실패했습니다.');
        }
        
        // Show success result
        showResult(result);
        
    } catch (error) {
        console.error('Error:', error);
        showError(error.message);
    } finally {
        // Reset button state
        submitBtn.disabled = false;
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
    }
});

// Show result section
function showResult(result) {
    const resultSection = document.getElementById('resultSection');
    const resultFile = document.getElementById('resultFile');
    const totalSubmissions = document.getElementById('totalSubmissions');
    const generationTime = document.getElementById('generationTime');
    
    // Extract result number from file path
    const fileMatch = result.result_file.match(/result(\d+)\.json/);
    const resultNumber = fileMatch ? fileMatch[1] : 'unknown';
    
    resultFile.textContent = result.result_file;
    totalSubmissions.textContent = result.total_submissions;
    generationTime.textContent = new Date().toLocaleString('ko-KR');
    
    // Store result number for view button
    resultSection.dataset.resultNumber = resultNumber;
    
    resultSection.style.display = 'block';
    
    // Scroll to result section
    resultSection.scrollIntoView({ behavior: 'smooth' });
}

// Show error section
function showError(message) {
    const errorSection = document.getElementById('errorSection');
    const errorMessage = document.getElementById('errorMessage');
    
    errorMessage.textContent = message;
    errorSection.style.display = 'block';
    
    // Scroll to error section
    errorSection.scrollIntoView({ behavior: 'smooth' });
}

// Hide result section
function hideResult() {
    document.getElementById('resultSection').style.display = 'none';
}

// Hide error section
function hideError() {
    document.getElementById('errorSection').style.display = 'none';
}

// View result button handler
document.getElementById('viewResultBtn').addEventListener('click', function() {
    const resultSection = document.getElementById('resultSection');
    const resultNumber = resultSection.dataset.resultNumber;
    
    if (resultNumber) {
        window.open(`/result/${resultNumber}`, '_blank');
    }
});

// New request button handler
document.getElementById('newRequestBtn').addEventListener('click', function() {
    // Reset form
    document.getElementById('contestForm').reset();
    
    // Hide result and error sections
    hideResult();
    hideError();
    
    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
});

// Example fillers
function fillExample(type) {
    const form = document.getElementById('contestForm');
    
    if (type === 'naming') {
        form.contestTitle.value = '2024년 AI 스타트업 브랜드명 공모전';
        form.contestContent.value = 'AI 기술을 활용한 혁신적인 스타트업의 브랜드명을 공모합니다. 기술적 혁신성과 시장 친화성을 모두 갖춘 브랜드명을 제안해주세요.';
        form.contestHeldBy.value = '테크스타트업협회';
        form.contestType.value = '작명';
        form.contestHeldByType.value = '기업';
        form.contestCriteria.value = '창의성, 기억하기 쉬움, 브랜드 가치 전달';
    } else if (type === 'slogan') {
        form.contestTitle.value = '2025년 GBDC 혁신 슬로건 공모전';
        form.contestContent.value = '제시된 키워드 활용한 GBDC형 혁신 슬로건 제작 소통, 체감, 공정, 디지털, 변화, 실용, 지속가능, 협력, 투명, 공유, 지역상생 ·제시된 11개 키워드 중 2개 이상의 키워드를 활용하여, 슬로건을 제작한 후 신청 접수해주시기 바랍니다.';
        form.contestHeldBy.value = '경상북도개발공사';
        form.contestType.value = '슬로건';
        form.contestHeldByType.value = '공공기관';
        form.contestCriteria.value = '키워드 활용, 혁신성, 지역 특성 반영';
    }
    
    // Scroll to form
    form.scrollIntoView({ behavior: 'smooth' });
}

// Form validation
function validateForm() {
    const requiredFields = ['contestTitle', 'contestContent', 'contestHeldBy', 'contestType', 'contestHeldByType'];
    let isValid = true;
    
    requiredFields.forEach(fieldName => {
        const field = document.getElementById(fieldName);
        if (!field.value.trim()) {
            field.style.borderColor = '#dc3545';
            isValid = false;
        } else {
            field.style.borderColor = '#e9ecef';
        }
    });
    
    return isValid;
}

// Real-time validation
document.querySelectorAll('#contestForm input, #contestForm select, #contestForm textarea').forEach(field => {
    field.addEventListener('input', function() {
        if (this.value.trim()) {
            this.style.borderColor = '#e9ecef';
        } else {
            this.style.borderColor = '#dc3545';
        }
    });
    
    field.addEventListener('blur', function() {
        if (this.hasAttribute('required') && !this.value.trim()) {
            this.style.borderColor = '#dc3545';
        }
    });
});

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl+Enter to submit form
    if (e.ctrlKey && e.key === 'Enter') {
        const submitBtn = document.getElementById('submitBtn');
        if (!submitBtn.disabled) {
            submitBtn.click();
        }
    }
    
    // Escape to hide error/result
    if (e.key === 'Escape') {
        hideError();
        hideResult();
    }
});

// Auto-resize textarea
document.getElementById('contestContent').addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 200) + 'px';
});

// Initialize page
document.addEventListener('DOMContentLoaded', function() {
    // Focus on first input
    document.getElementById('contestTitle').focus();
    
    // Add some visual feedback for form interactions
    const form = document.getElementById('contestForm');
    form.addEventListener('change', function() {
        // Add subtle animation to form container
        const container = document.querySelector('.form-container');
        container.style.transform = 'scale(1.01)';
        setTimeout(() => {
            container.style.transform = 'scale(1)';
        }, 150);
    });
});
