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
        const criteriaData = getCriteriaData();

        // Validate criteria total
        if (criteriaData.total !== 100 && criteriaData.total !== 0) {
            throw new Error(`평가 기준의 총점은 100이 되어야 합니다. (현재: ${criteriaData.total})`);
        }

        const requestData = {
            contestTitle: formData.get('contestTitle'),
            contestContent: formData.get('contestContent'),
            contestHeldBy: formData.get('contestHeldBy'),
            contestType: formData.get('contestType'),
            contestHeldByType: formData.get('contestHeldByType'),
            contestCriteria: Object.keys(criteriaData.criteria).length > 0 ? criteriaData.criteria : null
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
    
    // Clear criteria
    const criteriaContainer = document.getElementById('criteriaContainer');
    criteriaContainer.innerHTML = '';
    updateCriteriaTotal();

    // Hide result and error sections
    hideResult();
    hideError();
    
    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
});

// Example fillers
function fillExample(type) {
    const form = document.getElementById('contestForm');
    const criteriaContainer = document.getElementById('criteriaContainer');
    criteriaContainer.innerHTML = ''; // Clear existing criteria
    
    if (type === 'naming') {
        form.contestTitle.value = '여기어때 전용서체 네이밍 공모전';
        form.contestContent.value = '여기어때의 아이덴티티를 담은 새로운 글꼴의 이름을 지어주세요. 여행의 설렘과 즐거움을 담은 위트있는 이름이면 좋습니다.';
        form.contestHeldBy.value = '여기어때';
        form.contestType.value = '네이밍';
        form.contestHeldByType.value = '사기업';
        addCriteriaInput('창의성', 40);
        addCriteriaInput('주제 적합성', 30);
        addCriteriaInput('기억 용이성', 20);
        addCriteriaInput('대중성', 10);
    } else if (type === 'slogan') {
        form.contestTitle.value = '2025년 GBDC 혁신 슬로건 공모전';
        form.contestContent.value = '제시된 키워드 활용한 GBDC형 혁신 슬로건 제작 소통, 체감, 공정, 디지털, 변화, 실용, 지속가능, 협력, 투명, 공유, 지역상생 ·제시된 11개 키워드 중 2개 이상의 키워드를 활용하여, 슬로건을 제작한 후 신청 접수해주시기 바랍니다.';
        form.contestHeldBy.value = '경상북도개발공사';
        form.contestType.value = '슬로건';
        form.contestHeldByType.value = '공공기관';
        addCriteriaInput('주제 적합성', 40);
        addCriteriaInput('창의성', 30);
        addCriteriaInput('활용성', 20);
        addCriteriaInput('기억 용이성', 10);
    }
    
    updateCriteriaTotal();
    // Scroll to form
    form.scrollIntoView({ behavior: 'smooth' });
}

// --- Criteria Editor ---
function initializeCriteriaEditor() {
    const addCriteriaBtn = document.getElementById('addCriteriaBtn');
    const criteriaContainer = document.getElementById('criteriaContainer');

    addCriteriaBtn.addEventListener('click', () => addCriteriaInput());

    criteriaContainer.addEventListener('click', function(e) {
        if (e.target.classList.contains('remove-criteria-btn')) {
            e.target.closest('.criteria-item').remove();
            updateCriteriaTotal();
        }
    });

    criteriaContainer.addEventListener('input', function(e) {
        if (e.target.classList.contains('criteria-score')) {
            updateCriteriaTotal();
        }
    });
}

function addCriteriaInput(name = '', score = '') {
    const criteriaContainer = document.getElementById('criteriaContainer');
    const newItem = document.createElement('div');
    newItem.className = 'criteria-item';
    newItem.innerHTML = `
        <input type="text" class="criteria-name" placeholder="배점 기준" value="${name}">
        <input type="number" class="criteria-score" placeholder="점수" value="${score}" min="0" max="100">
        <button type="button" class="remove-criteria-btn">✖</button>
    `;
    criteriaContainer.appendChild(newItem);
}

function updateCriteriaTotal() {
    const totalScoreEl = document.getElementById('criteriaTotalScore');
    const scoreInputs = document.querySelectorAll('.criteria-score');
    let total = 0;
    scoreInputs.forEach(input => {
        total += parseInt(input.value) || 0;
    });
    totalScoreEl.textContent = total;
    if (total === 100 || total === 0) {
        totalScoreEl.parentElement.style.color = '#28a745'; // Green
    } else {
        totalScoreEl.parentElement.style.color = '#dc3545'; // Red
    }
}

function getCriteriaData() {
    const criteriaItems = document.querySelectorAll('.criteria-item');
    const criteria = {};
    let total = 0;
    let isValid = true;
    criteriaItems.forEach(item => {
        const name = item.querySelector('.criteria-name').value.trim();
        const score = parseInt(item.querySelector('.criteria-score').value) || 0;
        if (name && score > 0) {
            criteria[name] = score;
            total += score;
        } else if (name || score > 0) {
            // If one is filled but not the other
            isValid = false;
        }
    });
    if (!isValid) {
        throw new Error('평가 기준의 이름과 점수를 모두 입력해주세요.');
    }
    return { criteria, total };
}


// --- General Page Logic ---

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
    
    // Initialize criteria editor
    initializeCriteriaEditor();

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
