// Global variables
let resultData = null;
let allSubmissions = [];

// Get result number from URL
function getResultNumber() {
    const path = window.location.pathname;
    const match = path.match(/\/result\/(\d+)/);
    return match ? match[1] : '1';
}

// Load result data
async function loadResultData() {
    const resultNumber = getResultNumber();
    const resultFile = `result${resultNumber.padStart(4, '0')}.json`;
    
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
    const stats = resultData.statistics || {};
    
    document.getElementById('totalSubmissions').textContent = stats.total_submissions || 0;
    document.getElementById('totalModels').textContent = Object.keys(stats.model_distribution || {}).length;
    document.getElementById('totalProviders').textContent = Object.keys(stats.provider_distribution || {}).length;
}

// Display provider distribution
function displayProviderDistribution() {
    const stats = resultData.statistics || {};
    const providerDist = stats.provider_distribution || {};
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
    const stats = resultData.statistics || {};
    const modelDist = stats.model_distribution || {};
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
        
        card.innerHTML = `
            <div class="submission-text">${submission.submission || 'N/A'}</div>
            <div class="submission-description">${submission.description || 'N/A'}</div>
            <div class="submission-meta">
                <span class="provider-badge">${getProviderDisplayName(submission.provider || 'unknown')}</span>
                <span class="model-badge">${getModelDisplayName(submission.model || 'unknown')}</span>
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
    
    // Add provider options
    providers.forEach(provider => {
        const option = document.createElement('option');
        option.value = provider;
        option.textContent = getProviderDisplayName(provider);
        providerFilter.appendChild(option);
    });
    
    // Add model options
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
        'github_ai': 'GitHub AI',
        'gemini': 'Google Gemini'
    };
    return names[provider] || provider;
}

function getModelDisplayName(model) {
    // Shorten long model names for display
    const shortNames = {
        'openai/gpt-oss-120b': 'GPT-OSS-120B',
        'deepseek-r1-distill-llama-70b': 'DeepSeek-R1-70B',
        'llama-3.3-70b-versatile': 'Llama-3.3-70B',
        'gemma2-9b-it': 'Gemma2-9B',
        'meta-llama/llama-prompt-guard-2-86m': 'Llama-Prompt-Guard',
        'qwen/qwen3-32b': 'Qwen3-32B',
        'microsoft/Phi-4': 'Phi-4',
        'deepseek/DeepSeek-R1-0528': 'DeepSeek-R1',
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
document.addEventListener('DOMContentLoaded', loadResultData);
