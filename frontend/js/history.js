// History Page JavaScript

// XSS prevention
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(String(str)));
    return div.innerHTML;
}

document.addEventListener('DOMContentLoaded', () => {
    loadScans();
    loadUpdates();
});

function showTab(tabName, event) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });

    // Remove active from all tab buttons
    document.querySelectorAll('.tab').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected tab
    document.getElementById(`${tabName}-tab`).classList.add('active');

    // Make button active
    if (event && event.target) {
        event.target.classList.add('active');
    }
}

async function loadScans() {
    try {
        const { scans } = await API.getScanHistory(50);
        const container = document.getElementById('scans-list');

        if (scans.length === 0) {
            container.innerHTML = '<p class="loading">No scan history yet</p>';
            return;
        }

        container.innerHTML = scans.map(scan => `
            <div class="history-item ${escapeHtml(scan.status)}">
                <div class="history-header">
                    <span class="history-icon">${scan.status === 'completed' ? '✓' : '✗'}</span>
                    <div class="history-info">
                        <strong>${escapeHtml(scan.chat_file)}</strong>
                        <span class="history-meta">
                            ${formatDate(scan.scan_date)} • 
                            ${scan.messages_scanned} messages • 
                            ${scan.entities_found} entities found
                        </span>
                    </div>
                    <span class="status-badge ${escapeHtml(scan.status)}">
                        ${escapeHtml(scan.status)}
                    </span>
                </div>
                ${scan.error_message ? `
                    <div class="error-message">${escapeHtml(scan.error_message)}</div>
                ` : ''}
            </div>
        `).join('');

    } catch (error) {
        console.error('Error loading scan history:', error);
        document.getElementById('scans-list').innerHTML =
            '<p class="loading">Error loading scan history</p>';
    }
}

async function loadUpdates() {
    try {
        const { updates } = await API.getUpdateHistory(100);
        const container = document.getElementById('updates-list');

        if (updates.length === 0) {
            container.innerHTML = '<p class="loading">No updates applied yet</p>';
            return;
        }

        container.innerHTML = updates.map(update => `
            <div class="history-item completed">
                <div class="history-header">
                    <span class="history-icon">✓</span>
                    <div class="history-info">
                        <strong>${escapeHtml(update.entity_name)}</strong>
                        <span class="history-meta">
                            ${formatDate(update.applied_at)} • 
                            ${escapeHtml(update.entity_type)} • 
                            ${escapeHtml(update.action)} to ${escapeHtml(update.target_file.split('/').pop())}
                        </span>
                    </div>
                </div>
            </div>
        `).join('');

    } catch (error) {
        console.error('Error loading update history:', error);
        document.getElementById('updates-list').innerHTML =
            '<p class="loading">Error loading update history</p>';
    }
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString();
}

// Add tab styles
const style = document.createElement('style');
style.textContent = `
    .tabs {
        display: flex;
        gap: 5px;
        margin-bottom: 20px;
    }
    
    .tab {
        padding: 12px 24px;
        background: white;
        border: none;
        border-bottom: 3px solid transparent;
        cursor: pointer;
        font-weight: 500;
        transition: all 0.2s;
    }
    
    .tab:hover {
        background: var(--bg-light);
    }
    
    .tab.active {
        border-bottom-color: var(--primary-color);
        color: var(--primary-color);
    }
    
    .tab-content {
        display: none;
    }
    
    .tab-content.active {
        display: block;
    }
    
    .history-list {
        background: white;
        border-radius: 8px;
        box-shadow: var(--shadow);
        padding: 20px;
    }
    
    .history-item {
        padding: 15px;
        border-left: 4px solid var(--success-color);
        background: #f9fafb;
        margin-bottom: 10px;
        border-radius: 4px;
    }
    
    .history-item.failed {
        border-left-color: var(--danger-color);
    }
    
    .history-header {
        display: flex;
        align-items: center;
        gap: 15px;
    }
    
    .history-icon {
        font-size: 1.5rem;
    }
    
    .history-info {
        flex: 1;
    }
    
    .history-meta {
        display: block;
        font-size: 13px;
        color: #6b7280;
        margin-top: 4px;
    }
    
    .error-message {
        margin-top: 10px;
        padding: 10px;
        background: #fee2e2;
        color: var(--danger-color);
        border-radius: 4px;
        font-size: 13px;
    }
    
    .status-badge {
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
    }
    
    .status-badge.completed {
        background: #d1fae5;
        color: var(--success-color);
    }
    
    .status-badge.failed {
        background: #fee2e2;
        color: var(--danger-color);
    }
    
    .status-badge.partial {
        background: #fef3c7;
        color: var(--warning-color);
    }
`;
document.head.appendChild(style);
