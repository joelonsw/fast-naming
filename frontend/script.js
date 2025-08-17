// Global variables
let resultData = null;
let allSubmissions = [];

// Get result number from URL
function getResultNumber() {
    const path = window.location.pathname;
    const match = path.match(/\/result\/([\w_]+)/); // Adjusted to handle refined names like 0028_refined_01
    return match ? match[1] : '1';
}

// Load result data
async function loadResultData() {
    const resultNumber = getResultNumber();
    try {
        const response = await fetch(`/api/result/${resultNumber}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        resultData = await response.json();
        allSubmissions = resultData.submissions || [];
        displayData();
    } catch (error) {
        console.error('Error loading data:', error);
        showError(`데이터를 불러오는데 실패했습니다: ${error.message}`);
    }
}

// Display all data
function displayData() {
    if (!resultData) return;
    
    hideLoading();
    showContent();
    
    displayContestInfo();
    displayStatistics();
    displayProviderDistribution();
    displayModelDistribution();
    displaySubmissions();
    displayExamples();
    setupFilters();
}

// Display contest information
function displayContestInfo() {
    const contestData = resultData.contest_data;
    
    document.getElementById('contestTitle').textContent = contestData.contestTitle || 'N/A';
    document.getElementById('contestHeldBy').textContent = contestData.contestHeldBy || 'N/A';
    document.getElementById('contestType').textContent = contestData.contestType || 'N/A';
    document.getElementById('contestHeldByType').textContent = contestData.contestHeldByType || 'N/A';
    document.getElementById('contestContent').textContent = contestData.contestContent || 'N/A';
}

// Display statistics
function displayStatistics() {
    const totalSubmissions = resultData.total_submissions || allSubmissions.length;
    
    document.getElementById('totalSubmissions').textContent = totalSubmissions;
    document.getElementById('totalModels').textContent = Object.keys(resultData.statistics?.model_distribution || {}).length;
    document.getElementById('totalProviders').textContent = Object.keys(resultData.statistics?.provider_distribution || {}).length;
}

// Display provider distribution
function displayProviderDistribution() {
    const providerDist = resultData.statistics?.provider_distribution || {};
    const container = document.getElementById('providerChart');
    
    container.innerHTML = '';
    
    Object.entries(providerDist).forEach(([provider, count]) => {
        const item = document.createElement('div');
        item.className = 'chart-item';
        item.innerHTML = `
            <div class="name">${getProviderDisplayName(provider)}</div>
            <div class="count">${count}</div>
        `;
        container.appendChild(item);
    });
}

// Display model distribution
function displayModelDistribution() {
    const modelDist = resultData.statistics?.model_distribution || {};
    const container = document.getElementById('modelChart');
    
    container.innerHTML = '';
    
    Object.entries(modelDist).forEach(([model, count]) => {
        const item = document.createElement('div');
        item.className = 'chart-item';
        item.innerHTML = `
            <div class="name">${getModelDisplayName(model)}</div>
            <div class="count">${count}</div>
        `;
        container.appendChild(item);
    });
}

// Display submissions
function displaySubmissions() {
    const container = document.getElementById('submissionsGrid');
    container.innerHTML = '';
    
    allSubmissions.forEach((submission, index) => {
        const card = document.createElement('div');
        card.className = 'submission-card';
        card.dataset.provider = submission.provider || '';
        card.dataset.model = submission.model || '';
        card.dataset.submission = submission.submission || '';
        
        const submissionText = submission.submission || 'N/A';
        const submissionDesc = submission.description || 'N/A';

        // **FIX**: Store index instead of stringified JSON
        card.innerHTML = `
            <div class="submission-select">
                <input type="checkbox" class="refine-checkbox" data-index="${index}">
            </div>
            <div class="submission-content">
                <div class="submission-text">${submissionText}</div>
                <div class="submission-description">${submissionDesc}</div>
                <div class="submission-meta">
                    <span class="provider-badge">${getProviderDisplayName(submission.provider || 'unknown')}</span>
                    <span class="model-badge">${getModelDisplayName(submission.model || 'unknown')}</span>
                </div>
            </div>
        `;
        
        container.appendChild(card);
    });
}

// Display examples
function displayExamples() {
    const examples = resultData.successful_examples_used || [];
    const container = document.getElementById('examplesGrid');
    
    container.innerHTML = '';
    
    examples.forEach(example => {
        const card = document.createElement('div');
        card.className = 'example-card';
        
        card.innerHTML = `
            <div class="example-title">${example.contestTitle || 'N/A'}</div>
            <div class="example-winner">${example.contestWinner || 'N/A'}</div>
            <div class="example-strength">${example.strength || 'N/A'}</div>
        `;
        
        container.appendChild(card);
    });
}

// Setup filters
function setupFilters() {
    const providers = [...new Set(allSubmissions.map(s => s.provider).filter(Boolean))];
    const models = [...new Set(allSubmissions.map(s => s.model).filter(Boolean))];
    
    const providerFilter = document.getElementById('providerFilter');
    const modelFilter = document.getElementById('modelFilter');
    
    providerFilter.innerHTML = '<option value="">모든 제공자</option>';
    modelFilter.innerHTML = '<option value="">모든 모델</option>';

    providers.forEach(provider => {
        const option = document.createElement('option');
        option.value = provider;
        option.textContent = getProviderDisplayName(provider);
        providerFilter.appendChild(option);
    });
    
    models.forEach(model => {
        const option = document.createElement('option');
        option.value = model;
        option.textContent = getModelDisplayName(model);
        modelFilter.appendChild(option);
    });
}

// Filter submissions
function filterSubmissions() {
    const providerFilter = document.getElementById('providerFilter').value;
    const modelFilter = document.getElementById('modelFilter').value;
    const searchInput = document.getElementById('searchInput').value.toLowerCase();
    
    const cards = document.querySelectorAll('.submission-card');
    
    cards.forEach(card => {
        const provider = card.dataset.provider;
        const model = card.dataset.model;
        const submission = card.dataset.submission.toLowerCase();
        
        const providerMatch = !providerFilter || provider === providerFilter;
        const modelMatch = !modelFilter || model === modelFilter;
        const searchMatch = !searchInput || submission.includes(searchInput);
        
        if (providerMatch && modelMatch && searchMatch) {
            card.classList.remove('hidden');
        } else {
            card.classList.add('hidden');
        }
    });
}

// Helper functions
function getProviderDisplayName(provider) {
    const names = {
        'groq': 'Groq',
        'github': 'GitHub AI',
        'gemini': 'Google Gemini',
        'together': 'Together AI'
    };
    return names[provider] || provider;
}

function getModelDisplayName(model) {
    const shortNames = {
        'openai/gpt-oss-120b': 'GPT-OSS-120B',
        'llama-3.3-70b-versatile': 'Llama-3.3-70B',
        'gemma2-9b-it': 'Gemma2-9B',
        'qwen/qwen3-32b': 'Qwen3-32B',
        'microsoft/Phi-4': 'Phi-4',
        'gemini-2.5-flash': 'Gemini-2.5-Flash'
    };
    return shortNames[model] || model;
}

// UI helper functions
function hideLoading() {
    document.getElementById('loading').style.display = 'none';
}

function showContent() {
    document.getElementById('content').style.display = 'block';
}

function showError(message) {
    hideLoading();
    document.getElementById('errorMessage').textContent = message;
    document.getElementById('error').style.display = 'block';
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    loadResultData();
    initializeEvaluation();
    initializeRefinement(); // Initialize the new refinement feature
});

// Initialize evaluation functionality
function initializeEvaluation() {
    const evaluateButton = document.getElementById('evaluateButton');
    if (evaluateButton) {
        evaluateButton.addEventListener('click', handleEvaluationClick);
    }
}

// Initialize refinement functionality
function initializeRefinement() {
    const refineButton = document.getElementById('refineButton');
    if (refineButton) {
        refineButton.addEventListener('click', handleRefineClick);
    }
}

// Handle refinement button click
async function handleRefineClick() {
    const resultNumber = getResultNumber();
    const refineButton = document.getElementById('refineButton');
    const refineStatus = document.getElementById('refineStatus');

    // **FIX**: Select by class and get data-index
    const selectedCheckboxes = document.querySelectorAll('.refine-checkbox:checked');
    if (selectedCheckboxes.length === 0) {
        alert('개선할 아이디어를 하나 이상 선택해주세요.');
        return;
    }

    // **FIX**: Retrieve full submission object from allSubmissions array using the index
    const selected_submissions = Array.from(selectedCheckboxes).map(cb => {
        const index = parseInt(cb.dataset.index, 10);
        return allSubmissions[index];
    });

    const refinement_instruction = document.getElementById('refinementInstruction').value || '선택한 아이디어들의 장점을 조합하고 발전시켜주세요.';

    refineStatus.textContent = '✨ AI가 아이디어를 개선하고 있습니다...';
    refineStatus.style.color = '#007bff';
    refineButton.disabled = true;
    refineButton.textContent = '개선 중...';

    try {
        const response = await fetch('/api/refine', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                result_number: parseInt(resultNumber), // Ensure it's a number
                selected_submissions,
                refinement_instruction
            }),
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        refineStatus.textContent = '✅ 개선이 완료되었습니다! 새로운 결과 페이지로 이동합니다.';
        refineStatus.style.color = '#28a745';

        const newFileIdentifier = result.new_result_file.split('/').pop().replace('result', '').replace('.json', '');
        window.location.href = `/result/${newFileIdentifier}`;

    } catch (error) {
        console.error('Refinement failed:', error);
        refineStatus.textContent = `❌ 개선 실패: ${error.message}`;
        refineStatus.style.color = '#dc3545';
    } finally {
        refineButton.disabled = false;
        refineButton.textContent = '✨ 선택한 아이디어로 개선하기';
    }
}

// Handle evaluation button click
async function handleEvaluationClick() {
    const resultNumber = getResultNumber();
    const evaluateButton = document.getElementById('evaluateButton');
    const evaluationStatus = document.getElementById('evaluationStatus');
    const evaluationResultDiv = document.getElementById('evaluationResult');

    evaluationStatus.textContent = '🤖 AI 채점을 시작합니다...';
    evaluationStatus.style.color = '#007bff';
    evaluationResultDiv.innerHTML = '';
    evaluateButton.disabled = true;
    evaluateButton.textContent = '채점 중...';

    try {
        const response = await fetch('/evaluate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ result_number: parseInt(resultNumber) }),
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        evaluationStatus.textContent = '✅ 채점이 완료되었습니다! 결과를 불러옵니다...';
        evaluationStatus.style.color = '#28a745';

        await loadAndDisplayScores(resultNumber);

    } catch (error) {
        console.error('Evaluation failed:', error);
        evaluationStatus.textContent = `❌ 채점 실패: ${error.message}`;
        evaluationStatus.style.color = '#dc3545';
    } finally {
        evaluateButton.disabled = false;
        evaluateButton.textContent = '🤖 AI 채점 다시하기';
    }
}

// Load and display score data
async function loadAndDisplayScores(scoreNumber) {
    try {
        const response = await fetch(`/api/score/${scoreNumber}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const scoreData = await response.json();
        displayEvaluationResults(scoreData);
    } catch (error) {
        console.error('Error loading score data:', error);
        const evaluationStatus = document.getElementById('evaluationStatus');
        evaluationStatus.textContent = `❌ 점수 데이터 로드 실패: ${error.message}`;
        evaluationStatus.style.color = '#dc3545';
    }
}

// Display evaluation results in a table
function displayEvaluationResults(scoreData) {
    const container = document.getElementById('evaluationResult');
    container.innerHTML = '';

    if (!scoreData || !scoreData.submissions || scoreData.submissions.length === 0) {
        container.innerHTML = '<p>채점 결과가 없습니다.</p>';
        return;
    }

    const criteria = scoreData.evaluation_criteria || {};
    const criteriaKeys = Object.keys(criteria);
    const submissions = scoreData.submissions;

    const table = document.createElement('table');
    table.className = 'evaluation-table';

    // Create table header
    const thead = document.createElement('thead');
    let headerHtml = '<tr><th>순위</th><th>작명</th><th>설명</th>';
    criteriaKeys.forEach(key => {
        headerHtml += `<th>${key} (${criteria[key]}점)</th>`;
    });
    headerHtml += '<th>총점</th><th>코멘트</th></tr>';
    thead.innerHTML = headerHtml;
    table.appendChild(thead);

    // Create table body
    const tbody = document.createElement('tbody');
    submissions.forEach((submission, index) => {
        const row = document.createElement('tr');
        let rowHtml = `
            <td>${index + 1}</td>
            <td>${submission.submission}</td>
            <td>${submission.description}</td>
        `;
        criteriaKeys.forEach(key => {
            rowHtml += `<td>${submission.score[key] || 0}</td>`;
        });
        rowHtml += `
            <td><strong>${submission.total_score || 0}</strong></td>
            <td>${submission.comments || 'N/A'}</td>
        `;
        row.innerHTML = rowHtml;
        tbody.appendChild(row);
    });
    table.appendChild(tbody);

    container.appendChild(table);
}