// Portfolio Dashboard JavaScript

// Chart instances
let portfolioValueChart = null;
let allocationChart = null;

// API base URL
const API_BASE = '';

// Format currency
function formatCurrency(value) {
    return new Intl.NumberFormat('en-AU', {
        style: 'currency',
        currency: 'AUD',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(value);
}

// Format percentage
function formatPercent(value) {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

// Get color based on value
function getColorForValue(value) {
    if (value > 0) return '#10b981';
    if (value < 0) return '#ef4444';
    return '#6b7280';
}

// Load portfolio data
async function loadPortfolioData() {
    try {
        const response = await fetch(`${API_BASE}/api/portfolio/current`);
        if (!response.ok) throw new Error('Failed to load portfolio data');
        return await response.json();
    } catch (error) {
        console.error('Error loading portfolio:', error);
        showError('Failed to load portfolio data. Please check if the API server is running.');
        return null;
    }
}

// Load portfolio history
async function loadPortfolioHistory(days = 30) {
    try {
        const response = await fetch(`${API_BASE}/api/portfolio/history?days=${days}`);
        if (!response.ok) throw new Error('Failed to load history');
        return await response.json();
    } catch (error) {
        console.error('Error loading history:', error);
        return [];
    }
}

// Load performance metrics
async function loadPerformanceMetrics() {
    try {
        const response = await fetch(`${API_BASE}/api/portfolio/performance`);
        if (!response.ok) throw new Error('Failed to load performance');
        return await response.json();
    } catch (error) {
        console.error('Error loading performance:', error);
        return null;
    }
}

// Load rebalancing data
async function loadRebalancingData() {
    try {
        const response = await fetch(`${API_BASE}/api/portfolio/rebalancing`);
        if (!response.ok) throw new Error('Failed to load rebalancing');
        return await response.json();
    } catch (error) {
        console.error('Error loading rebalancing:', error);
        return null;
    }
}

// Update portfolio summary
function updatePortfolioSummary(data, performance) {
    document.getElementById('totalValue').textContent = formatCurrency(data.total_value);
    document.getElementById('lastUpdated').textContent = `Last updated: ${new Date(data.timestamp).toLocaleString()}`;
    
    if (performance && performance.returns) {
        const returns = performance.returns;
        
        if (returns.daily !== undefined) {
            const el = document.getElementById('return24h');
            el.textContent = formatPercent(returns.daily);
            el.className = 'value ' + (returns.daily >= 0 ? 'positive' : 'negative');
        }
        
        if (returns.weekly !== undefined) {
            const el = document.getElementById('return7d');
            el.textContent = formatPercent(returns.weekly);
            el.className = 'value ' + (returns.weekly >= 0 ? 'positive' : 'negative');
        }
        
        if (returns.monthly !== undefined) {
            const el = document.getElementById('return30d');
            el.textContent = formatPercent(returns.monthly);
            el.className = 'value ' + (returns.monthly >= 0 ? 'positive' : 'negative');
        }
    }
}

// Create portfolio value chart
async function createPortfolioValueChart() {
    const history = await loadPortfolioHistory(30);
    
    if (!history || history.length === 0) {
        document.getElementById('portfolioValueChart').parentElement.innerHTML = 
            '<p class="loading">No historical data available</p>';
        return;
    }
    
    const ctx = document.getElementById('portfolioValueChart').getContext('2d');
    
    if (portfolioValueChart) {
        portfolioValueChart.destroy();
    }
    
    portfolioValueChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: history.map(h => new Date(h.date).toLocaleDateString()),
            datasets: [{
                label: 'Portfolio Value (AUD)',
                data: history.map(h => h.value),
                borderColor: '#667eea',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: function(context) {
                            return 'Value: ' + formatCurrency(context.parsed.y);
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    ticks: {
                        callback: function(value) {
                            return formatCurrency(value);
                        }
                    }
                }
            }
        }
    });
}

// Create allocation chart
function createAllocationChart(portfolio) {
    const ctx = document.getElementById('allocationChart').getContext('2d');
    
    if (allocationChart) {
        allocationChart.destroy();
    }
    
    // Sort by allocation percentage
    const sortedPortfolio = [...portfolio].sort((a, b) => b.allocation_percent - a.allocation_percent);
    
    const colors = [
        '#667eea', '#764ba2', '#f093fb', '#4facfe', '#00f2fe',
        '#43e97b', '#fa709a', '#fee140', '#30cfd0', '#330867'
    ];
    
    allocationChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: sortedPortfolio.map(a => a.symbol),
            datasets: [{
                data: sortedPortfolio.map(a => a.allocation_percent),
                backgroundColor: colors.slice(0, sortedPortfolio.length),
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        padding: 15,
                        font: {
                            size: 12
                        }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const asset = sortedPortfolio[context.dataIndex];
                            return [
                                `${label}: ${value.toFixed(2)}%`,
                                `Value: ${formatCurrency(asset.value)}`
                            ];
                        }
                    }
                }
            }
        }
    });
}

// Update allocation table
function updateAllocationTable(portfolio, analyses) {
    const tbody = document.getElementById('allocationTableBody');
    tbody.innerHTML = '';
    
    // Create a map of analyses by symbol
    const analysisMap = {};
    analyses.forEach(a => {
        analysisMap[a.symbol] = a;
    });
    
    // Sort by allocation
    const sortedPortfolio = [...portfolio].sort((a, b) => b.allocation_percent - a.allocation_percent);
    
    sortedPortfolio.forEach(asset => {
        const analysis = analysisMap[asset.symbol] || {};
        const row = document.createElement('tr');
        
        const trendClass = analysis.trend === 'bullish' ? 'trend-bullish' : 
                          analysis.trend === 'bearish' ? 'trend-bearish' : 'trend-neutral';
        const changeClass = (analysis.price_change_24h || 0) >= 0 ? 'change-positive' : 'change-negative';
        
        row.innerHTML = `
            <td><strong>${asset.symbol}</strong><br><small>${asset.name}</small></td>
            <td>${asset.allocation_percent.toFixed(2)}%</td>
            <td>${formatCurrency(asset.value)}</td>
            <td class="${changeClass}">${analysis.price_change_24h !== undefined ? formatPercent(analysis.price_change_24h) : '--'}</td>
            <td class="${trendClass}">${(analysis.trend || 'neutral').toUpperCase()}</td>
        `;
        
        tbody.appendChild(row);
    });
}

// Update recommendations
function updateRecommendations(analyses) {
    const container = document.getElementById('recommendationsContainer');
    container.innerHTML = '';
    
    if (!analyses || analyses.length === 0) {
        container.innerHTML = '<p class="loading">No recommendations available</p>';
        return;
    }
    
    // Group by recommendation type and sort by priority
    const recommendations = analyses
        .filter(a => a.recommendation && !a.recommendation.includes('HOLD'))
        .sort((a, b) => (b.dca_priority || 0) - (a.dca_priority || 0));
    
    if (recommendations.length === 0) {
        container.innerHTML = '<p class="loading">No active recommendations</p>';
        return;
    }
    
    recommendations.forEach(analysis => {
        const priority = analysis.dca_priority || 0;
        let priorityClass = 'low-priority';
        let priorityText = 'Low';
        
        if (priority >= 7) {
            priorityClass = 'high-priority';
            priorityText = 'High';
        } else if (priority >= 4) {
            priorityClass = 'medium-priority';
            priorityText = 'Medium';
        }
        
        const card = document.createElement('div');
        card.className = `recommendation-card ${priorityClass}`;
        card.innerHTML = `
            <div class="recommendation-header">
                <div>
                    <div class="recommendation-title">${analysis.recommendation.replace(/_/g, ' ')}</div>
                    <div class="recommendation-symbol">${analysis.symbol}</div>
                </div>
                <div class="recommendation-priority ${priorityClass}">${priorityText} Priority (${priority}/10)</div>
            </div>
            <div class="recommendation-reason">${analysis.reason || 'No reason provided'}</div>
            <div class="recommendation-action">${analysis.suggested_action || 'No action specified'}</div>
        `;
        
        container.appendChild(card);
    });
}

// Update rebalancing section
function updateRebalancing(rebalancingData) {
    const container = document.getElementById('rebalancingContainer');
    container.innerHTML = '';
    
    if (!rebalancingData || !rebalancingData.actions) {
        container.innerHTML = '<p class="loading">No rebalancing data available</p>';
        return;
    }
    
    const actions = rebalancingData.actions;
    const buyActions = actions.filter(a => a.action === 'BUY');
    const sellActions = actions.filter(a => a.action === 'SELL');
    const holdActions = actions.filter(a => a.action === 'HOLD');
    
    if (buyActions.length === 0 && sellActions.length === 0) {
        container.innerHTML = '<p class="loading">Portfolio is balanced - no rebalancing needed</p>';
        return;
    }
    
    // Buy actions
    if (buyActions.length > 0) {
        const buyGroup = document.createElement('div');
        buyGroup.className = 'rebalancing-group';
        buyGroup.innerHTML = '<h3>Assets to Buy</h3>';
        
        buyActions.forEach(action => {
            const actionEl = document.createElement('div');
            actionEl.className = 'rebalancing-action buy';
            actionEl.innerHTML = `
                <div class="action-details">
                    <div class="action-symbol">${action.name} (${action.symbol})</div>
                    <div class="action-info">
                        Current: ${action.current_allocation.toFixed(2)}% → Target: ${action.target_allocation.toFixed(2)}%
                    </div>
                </div>
                <div class="action-amount">
                    ${formatCurrency(action.value_diff)}<br>
                    <small>${action.amount_diff > 0 ? action.amount_diff.toFixed(8) + ' ' + action.symbol : 'N/A'}</small>
                </div>
            `;
            buyGroup.appendChild(actionEl);
        });
        
        container.appendChild(buyGroup);
    }
    
    // Sell actions
    if (sellActions.length > 0) {
        const sellGroup = document.createElement('div');
        sellGroup.className = 'rebalancing-group';
        sellGroup.innerHTML = '<h3>Assets to Sell</h3>';
        
        sellActions.forEach(action => {
            const actionEl = document.createElement('div');
            actionEl.className = 'rebalancing-action sell';
            actionEl.innerHTML = `
                <div class="action-details">
                    <div class="action-symbol">${action.name} (${action.symbol})</div>
                    <div class="action-info">
                        Current: ${action.current_allocation.toFixed(2)}% → Target: ${action.target_allocation.toFixed(2)}%
                    </div>
                </div>
                <div class="action-amount">
                    ${formatCurrency(Math.abs(action.value_diff))}<br>
                    <small>${Math.abs(action.amount_diff).toFixed(8)} ${action.symbol}</small>
                </div>
            `;
            sellGroup.appendChild(actionEl);
        });
        
        container.appendChild(sellGroup);
    }
}

// Show error message
function showError(message) {
    const container = document.querySelector('.container');
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error';
    errorDiv.textContent = message;
    container.insertBefore(errorDiv, container.firstChild);
}

// Initialize dashboard
async function initDashboard() {
    try {
        // Load all data in parallel
        const [portfolioData, performance, rebalancing] = await Promise.all([
            loadPortfolioData(),
            loadPerformanceMetrics(),
            loadRebalancingData()
        ]);
        
        if (!portfolioData) {
            return;
        }
        
        // Update UI
        updatePortfolioSummary(portfolioData, performance);
        createAllocationChart(portfolioData.portfolio);
        updateAllocationTable(portfolioData.portfolio, portfolioData.analyses);
        updateRecommendations(portfolioData.analyses);
        updateRebalancing(rebalancing);
        
        // Create history chart
        await createPortfolioValueChart();
        
    } catch (error) {
        console.error('Error initializing dashboard:', error);
        showError('Failed to initialize dashboard. Please refresh the page.');
    }
}

// Calculate deposit allocation
async function calculateDepositAllocation(amount) {
    try {
        const response = await fetch(`${API_BASE}/api/portfolio/deposit-allocation?amount=${amount}`);
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to calculate allocation');
        }
        return await response.json();
    } catch (error) {
        console.error('Error calculating deposit allocation:', error);
        showError(`Failed to calculate deposit allocation: ${error.message}`);
        return null;
    }
}

// Display deposit allocation results
function displayDepositResults(data) {
    const resultsContainer = document.getElementById('depositResults');
    resultsContainer.style.display = 'block';
    
    let html = `
        <div class="deposit-summary">
            <h3>Deposit Summary</h3>
            <div class="summary-stats">
                <div class="summary-stat">
                    <div class="summary-stat-label">Current Portfolio Value</div>
                    <div class="summary-stat-value">${formatCurrency(data.current_total)}</div>
                </div>
                <div class="summary-stat">
                    <div class="summary-stat-label">Deposit Amount</div>
                    <div class="summary-stat-value">${formatCurrency(data.deposit_amount)}</div>
                </div>
                <div class="summary-stat">
                    <div class="summary-stat-label">New Portfolio Value</div>
                    <div class="summary-stat-value">${formatCurrency(data.new_total)}</div>
                </div>
                <div class="summary-stat">
                    <div class="summary-stat-label">Total Allocated</div>
                    <div class="summary-stat-value">${formatCurrency(data.total_allocated)}</div>
                </div>
            </div>
        </div>
    `;
    
    if (data.allocations && data.allocations.length > 0) {
        html += `
            <div class="allocation-plan">
                <h3>Allocation Plan</h3>
                <table class="allocation-table">
                    <thead>
                        <tr>
                            <th>Asset</th>
                            <th>Current %</th>
                            <th>Target %</th>
                            <th>Deposit Amount</th>
                            <th>New %</th>
                            <th>Buy Amount</th>
                        </tr>
                    </thead>
                    <tbody>
        `;
        
        // Sort by deposit allocation (highest first)
        const sorted = [...data.allocations].sort((a, b) => b.deposit_allocation - a.deposit_allocation);
        
        sorted.forEach(allocation => {
            const buyAmount = allocation.amount_to_buy > 0 
                ? `${allocation.amount_to_buy.toFixed(8)} ${allocation.symbol}`
                : 'N/A';
            
            html += `
                <tr>
                    <td><strong>${allocation.symbol}</strong><br><small>${allocation.name}</small></td>
                    <td>${allocation.current_allocation.toFixed(2)}%</td>
                    <td>${allocation.target_allocation.toFixed(2)}%</td>
                    <td>${formatCurrency(allocation.deposit_allocation)}</td>
                    <td>${allocation.new_allocation.toFixed(2)}%</td>
                    <td>${buyAmount}</td>
                </tr>
            `;
        });
        
        html += `
                    </tbody>
                </table>
            </div>
        `;
    } else {
        html += '<p class="loading">No under-allocated assets found. Portfolio is already balanced.</p>';
    }
    
    if (data.projected_allocations && data.projected_allocations.length > 0) {
        html += `
            <div class="projected-allocations">
                <h3>Projected Allocations After Deposit</h3>
                <table class="allocation-table">
                    <thead>
                        <tr>
                            <th>Asset</th>
                            <th>Current %</th>
                            <th>After Deposit %</th>
                            <th>Target %</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
        `;
        
        // Sort by after allocation (highest first)
        const sorted = [...data.projected_allocations].sort((a, b) => b.after - a.after);
        
        sorted.forEach(asset => {
            const statusText = asset.status.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
            html += `
                <tr>
                    <td><strong>${asset.symbol}</strong><br><small>${asset.name}</small></td>
                    <td>${asset.current.toFixed(2)}%</td>
                    <td>${asset.after.toFixed(2)}%</td>
                    <td>${asset.target.toFixed(2)}%</td>
                    <td><span class="status-badge ${asset.status}">${statusText}</span></td>
                </tr>
            `;
        });
        
        html += `
                    </tbody>
                </table>
            </div>
        `;
    }
    
    resultsContainer.innerHTML = html;
    
    // Scroll to results
    resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initDashboard();
    
    // Deposit calculator event listener
    const calculateBtn = document.getElementById('calculateDeposit');
    const depositInput = document.getElementById('depositAmount');
    
    if (calculateBtn && depositInput) {
        calculateBtn.addEventListener('click', async function() {
            const amount = parseFloat(depositInput.value);
            
            if (!amount || amount <= 0) {
                showError('Please enter a valid deposit amount greater than 0');
                return;
            }
            
            calculateBtn.disabled = true;
            calculateBtn.textContent = 'Calculating...';
            
            const result = await calculateDepositAllocation(amount);
            
            calculateBtn.disabled = false;
            calculateBtn.textContent = 'Calculate Allocation';
            
            if (result) {
                displayDepositResults(result);
            }
        });
        
        // Allow Enter key to trigger calculation
        depositInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                calculateBtn.click();
            }
        });
    }
});

// Auto-refresh every 5 minutes (uses cached data to avoid rate limits)
setInterval(initDashboard, 5 * 60 * 1000);

