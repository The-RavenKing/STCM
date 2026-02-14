// Dashboard JavaScript

// XSS prevention
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(String(str)));
    return div.innerHTML;
}

// Load dashboard data on page load
document.addEventListener('DOMContentLoaded', () => {
    loadDashboard();
    loadChatList();

    // Refresh stats every 30 seconds
    setInterval(loadDashboard, 30000);
});

async function loadDashboard() {
    try {
        const stats = await API.getStats();

        // Update cards
        document.getElementById('pending-count').textContent = stats.pending_count;
        document.getElementById('applied-count').textContent = stats.applied_today;
        document.getElementById('queue-count').textContent = stats.pending_count;

        // Update last scan
        if (stats.last_scan) {
            const scanDate = new Date(stats.last_scan.scan_date);
            document.getElementById('last-scan-time').textContent = formatRelativeTime(scanDate);

            const statusBadge = document.getElementById('last-scan-status');
            statusBadge.textContent = stats.last_scan.status;
            statusBadge.className = `status-badge ${stats.last_scan.status === 'completed' ? 'success' : 'error'}`;
        }

        // Load activity log
        loadActivityLog();

    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

async function loadChatList() {
    try {
        const { chats } = await API.listChats();
        const select = document.getElementById('chat-select');

        if (!select) return;

        select.innerHTML = '<option value="">Select a chat file...</option>';

        chats.forEach(chat => {
            const option = document.createElement('option');
            option.value = chat.file;
            option.textContent = `${chat.file} (${chat.message_count} messages)`;
            select.appendChild(option);
        });

    } catch (error) {
        console.error('Error loading chats:', error);
    }
}

async function loadActivityLog() {
    try {
        const { updates } = await API.getUpdateHistory(10);
        const log = document.getElementById('activity-log');

        if (!log) return;

        if (updates.length === 0) {
            log.innerHTML = '<p class="log-empty">No recent activity</p>';
            return;
        }

        log.innerHTML = updates.map(update => `
            <div class="log-entry">
                <strong>${escapeHtml(update.entity_name)}</strong> (${escapeHtml(update.entity_type)})
                ${escapeHtml(update.action)} to ${escapeHtml(update.target_file.split('/').pop())}
                <br>
                <small>${formatRelativeTime(new Date(update.applied_at))}</small>
            </div>
        `).join('');

    } catch (error) {
        console.error('Error loading activity log:', error);
    }
}

async function testOllama() {
    const statusEl = document.getElementById('ollama-status');
    statusEl.textContent = 'Testing...';

    try {
        const result = await API.testOllama();

        if (result.status === 'success') {
            statusEl.textContent = 'Connected ✓';
            statusEl.style.color = 'var(--success-color)';

            showNotification('Ollama connection successful!', 'success');
        } else {
            statusEl.textContent = 'Error ✗';
            statusEl.style.color = 'var(--danger-color)';

            showNotification(result.message, 'error');
        }
    } catch (error) {
        statusEl.textContent = 'Error ✗';
        statusEl.style.color = 'var(--danger-color)';

        showNotification('Failed to connect to Ollama', 'error');
    }
}

async function runManualScan() {
    const chatFile = document.getElementById('chat-select').value;
    const messagesLimit = parseInt(document.getElementById('messages-limit').value);

    if (!chatFile) {
        showNotification('Please select a chat file', 'warning');
        return;
    }

    try {
        const result = await API.runScan(chatFile, messagesLimit);

        if (result.status === 'started') {
            showNotification('Scan started! Check back in a moment.', 'success');

            // Reload dashboard after 10 seconds
            setTimeout(loadDashboard, 10000);
        } else {
            showNotification(result.message || 'Scan failed', 'error');
        }
    } catch (error) {
        showNotification('Error starting scan: ' + error.message, 'error');
    }
}

// Utility Functions

function formatRelativeTime(date) {
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
    return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        background: ${type === 'success' ? 'var(--success-color)' : type === 'error' ? 'var(--danger-color)' : 'var(--warning-color)'};
        color: white;
        border-radius: 4px;
        box-shadow: var(--shadow);
        z-index: 1000;
        animation: slideIn 0.3s ease-out;
    `;

    document.body.appendChild(notification);

    // Remove after 5 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

// Add animation styles
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(400px); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(400px); opacity: 0; }
    }
`;
document.head.appendChild(style);

// WebSocket message handler
ws.onMessage((data) => {
    if (data.type === 'scan_complete') {
        showNotification(`Scan completed! ${data.entities_found || 0} entities found.`, 'success');
        hideScanProgress();
        loadDashboard();
    } else if (data.type === 'scan_progress') {
        showScanProgress(data);
    } else if (data.type === 'entity_approved') {
        showNotification(`Entity "${data.entity_name}" approved`, 'success');
        loadDashboard();
    }
});

// Scan progress indicator
function showScanProgress(data) {
    let progressEl = document.getElementById('scan-progress');

    if (!progressEl) {
        progressEl = document.createElement('div');
        progressEl.id = 'scan-progress';
        progressEl.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 15px 20px;
            background: var(--bg-light, #1e293b);
            color: var(--text-color, #e2e8f0);
            border: 1px solid var(--primary-color, #6366f1);
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            z-index: 999;
            min-width: 280px;
            font-size: 14px;
        `;
        document.body.appendChild(progressEl);
    }

    const pct = data.total_chunks > 0
        ? Math.round((data.current_chunk / data.total_chunks) * 100)
        : 0;

    progressEl.innerHTML = `
        <div style="margin-bottom: 8px;"><strong>⏳ Scanning: ${escapeHtml(data.chat_file || '')}</strong></div>
        <div style="background: #334155; border-radius: 4px; height: 8px; overflow: hidden; margin-bottom: 6px;">
            <div style="background: var(--primary-color, #6366f1); height: 100%; width: ${pct}%; transition: width 0.3s;"></div>
        </div>
        <div style="font-size: 12px; color: #94a3b8;">Chunk ${data.current_chunk}/${data.total_chunks} • ${data.entities_found} entities found</div>
    `;
}

function hideScanProgress() {
    const el = document.getElementById('scan-progress');
    if (el) {
        setTimeout(() => el.remove(), 2000);
    }
}
