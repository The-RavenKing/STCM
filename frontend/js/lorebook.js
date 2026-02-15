// Lorebook Builder JavaScript

let currentMode = 'freeform';
let lorebooks = [];
let selectedLorebook = null;

// XSS prevention
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ─────────────────────────────────────────
//  Initialization
// ─────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    loadLorebooks();
    setupCharCount();
    updateSubmitButton();

    // Listen for WebSocket progress updates
    if (typeof ws !== 'undefined') {
        ws.onMessage(handleWSMessage);
    }
});

function setupCharCount() {
    const freeformInput = document.getElementById('freeform-input');
    const counter = document.getElementById('freeform-count');

    freeformInput.addEventListener('input', () => {
        counter.textContent = freeformInput.value.length;
        updateSubmitButton();
    });

    // Also track structured inputs
    document.querySelectorAll('.category-textarea').forEach(textarea => {
        textarea.addEventListener('input', updateSubmitButton);
    });
}

// ─────────────────────────────────────────
//  Mode Switching
// ─────────────────────────────────────────

function switchMode(mode) {
    currentMode = mode;

    // Update toggle buttons
    document.getElementById('btn-freeform').classList.toggle('active', mode === 'freeform');
    document.getElementById('btn-structured').classList.toggle('active', mode === 'structured');

    // Show/hide sections
    document.getElementById('freeform-section').style.display = mode === 'freeform' ? 'block' : 'none';
    document.getElementById('structured-section').style.display = mode === 'structured' ? 'block' : 'none';

    // Update description
    const desc = document.getElementById('mode-description');
    if (mode === 'freeform') {
        desc.textContent = 'Paste or type your world-building text in one box. The AI will categorise it automatically.';
    } else {
        desc.textContent = 'Enter information for each category separately for more precise results.';
    }

    updateSubmitButton();
}

// ─────────────────────────────────────────
//  Lorebook Management
// ─────────────────────────────────────────

async function loadLorebooks() {
    try {
        const data = await API.listLorebooks();
        lorebooks = data.lorebooks || [];
        renderLorebookSelect();
    } catch (error) {
        console.error('Failed to load lorebooks:', error);
        showNotification('Failed to load lorebooks: ' + error.message, 'error');
    }
}

function renderLorebookSelect() {
    const select = document.getElementById('lorebook-select');
    select.innerHTML = '';

    // Default option
    const defaultOpt = document.createElement('option');
    defaultOpt.value = '';
    defaultOpt.textContent = 'Select a lorebook...';
    select.appendChild(defaultOpt);

    // Existing lorebooks grouped by type
    const standalone = lorebooks.filter(lb => lb.type === 'standalone');
    const character = lorebooks.filter(lb => lb.type === 'character');

    if (standalone.length > 0) {
        const group = document.createElement('optgroup');
        group.label = 'Standalone Lorebooks';
        standalone.forEach(lb => {
            const opt = document.createElement('option');
            opt.value = lb.file;
            opt.textContent = `${lb.name} (${lb.entries} entries)`;
            group.appendChild(opt);
        });
        select.appendChild(group);
    }

    if (character.length > 0) {
        const group = document.createElement('optgroup');
        group.label = 'Character Lorebooks';
        character.forEach(lb => {
            const opt = document.createElement('option');
            opt.value = lb.file;
            opt.textContent = `${lb.name} (${lb.entries} entries)`;
            group.appendChild(opt);
        });
        select.appendChild(group);
    }

    // Create new option
    const newOpt = document.createElement('option');
    newOpt.value = '__new__';
    newOpt.textContent = '➕ Create New Lorebook...';
    select.appendChild(newOpt);

    updateSubmitButton();
}

function onLorebookChange() {
    const select = document.getElementById('lorebook-select');
    const newForm = document.getElementById('new-lorebook-form');
    const infoDiv = document.getElementById('lorebook-info');

    if (select.value === '__new__') {
        newForm.style.display = 'flex';
        infoDiv.style.display = 'none';
        selectedLorebook = null;
    } else if (select.value) {
        newForm.style.display = 'none';
        selectedLorebook = lorebooks.find(lb => lb.file === select.value);

        if (selectedLorebook) {
            infoDiv.style.display = 'flex';
            const typeEl = document.getElementById('lorebook-type');
            typeEl.textContent = selectedLorebook.type === 'standalone' ? 'Standalone' : 'Character';
            typeEl.className = 'status-badge ' + (selectedLorebook.type === 'standalone' ? 'success' : '');
            document.getElementById('lorebook-entries').textContent = `${selectedLorebook.entries} entries`;
        }
    } else {
        newForm.style.display = 'none';
        infoDiv.style.display = 'none';
        selectedLorebook = null;
    }

    updateSubmitButton();
}

async function createNewLorebook() {
    const nameInput = document.getElementById('new-lorebook-name');
    const name = nameInput.value.trim();

    if (!name) {
        showNotification('Please enter a name for the lorebook', 'error');
        return;
    }

    try {
        const result = await API.createLorebook(name);

        if (result.status === 'created') {
            showNotification(`Lorebook "${name}" created!`, 'success');
            await loadLorebooks();

            // Auto-select the new lorebook
            const select = document.getElementById('lorebook-select');
            select.value = result.file;
            onLorebookChange();
        } else if (result.status === 'exists') {
            showNotification(`Lorebook "${name}" already exists`, 'error');
        }
    } catch (error) {
        showNotification('Failed to create lorebook: ' + error.message, 'error');
    }
}

async function refreshLorebooks() {
    await loadLorebooks();
    showNotification('Lorebook list refreshed', 'info');
}

// ─────────────────────────────────────────
//  Submit / Build
// ─────────────────────────────────────────

function updateSubmitButton() {
    const btn = document.getElementById('btn-submit');
    const select = document.getElementById('lorebook-select');

    let hasContent = false;
    if (currentMode === 'freeform') {
        hasContent = document.getElementById('freeform-input').value.trim().length > 0;
    } else {
        hasContent = Array.from(document.querySelectorAll('.category-textarea'))
            .some(ta => ta.value.trim().length > 0);
    }

    const hasTarget = select.value && select.value !== '' && select.value !== '__new__';
    btn.disabled = !(hasContent && hasTarget);
}

async function submitBuild() {
    const select = document.getElementById('lorebook-select');
    const target = select.value;

    if (!target || target === '__new__') {
        showNotification('Please select a target lorebook', 'error');
        return;
    }

    // Build request
    const request = {
        mode: currentMode,
        target: target
    };

    if (currentMode === 'freeform') {
        request.text = document.getElementById('freeform-input').value.trim();
    } else {
        request.categories = {
            people: document.getElementById('cat-people').value.trim(),
            factions: document.getElementById('cat-factions').value.trim(),
            places: document.getElementById('cat-places').value.trim(),
            items: document.getElementById('cat-items').value.trim(),
            mythology: document.getElementById('cat-mythology').value.trim()
        };
    }

    // Show progress
    showProgress('Starting AI processing...');
    document.getElementById('btn-submit').disabled = true;

    try {
        const result = await API.buildLorebook(request);
        showProgress('AI is processing your text... This may take a moment.');
    } catch (error) {
        hideProgress();
        showResults('error', 'Failed to start processing: ' + error.message);
        document.getElementById('btn-submit').disabled = false;
    }
}

// ─────────────────────────────────────────
//  Progress & Results
// ─────────────────────────────────────────

function showProgress(message) {
    document.getElementById('progress-section').style.display = 'block';
    document.getElementById('progress-message').textContent = message;
    document.getElementById('results-section').style.display = 'none';
}

function hideProgress() {
    document.getElementById('progress-section').style.display = 'none';
}

function showResults(type, message, data = null) {
    hideProgress();

    const section = document.getElementById('results-section');
    const content = document.getElementById('results-content');
    section.style.display = 'block';

    let html = '';

    if (type === 'success' && data) {
        html += '<div class="results-summary">';
        html += `<div class="result-stat"><div class="stat-value">${data.entities_found || 0}</div><div class="stat-label">Entities Found</div></div>`;
        html += `<div class="result-stat"><div class="stat-value">${data.lorebook_entries || 0}</div><div class="stat-label">Entries Created</div></div>`;
        html += '</div>';
        html += `<div class="result-message success">✓ ${escapeHtml(message)}</div>`;
        html += '<a href="/static/review.html" class="review-link">📝 Go to Review Queue</a>';
    } else if (type === 'error') {
        html += `<div class="result-message error">✗ ${escapeHtml(message)}</div>`;
    } else {
        html += `<div class="result-message info">${escapeHtml(message)}</div>`;
    }

    content.innerHTML = html;
    document.getElementById('btn-submit').disabled = false;
}

// ─────────────────────────────────────────
//  WebSocket Handler
// ─────────────────────────────────────────

function handleWSMessage(data) {
    if (data.type === 'lorebook_build_progress') {
        showProgress(`Processing in ${data.mode} mode...`);
    } else if (data.type === 'lorebook_build_complete') {
        if (data.status === 'success') {
            showResults('success', 'Entities extracted and sent to review queue!', data);
        } else if (data.status === 'no_entities') {
            showResults('info', 'No significant entities were found in the text. Try providing more detail.');
        } else {
            showResults('info', 'Processing complete.');
        }
    } else if (data.type === 'lorebook_build_error') {
        showResults('error', 'Processing failed: ' + (data.error || 'Unknown error'));
    }
}

// ─────────────────────────────────────────
//  Notification (same as other pages)
// ─────────────────────────────────────────

function showNotification(message, type = 'info') {
    const existing = document.querySelector('.notification');
    if (existing) existing.remove();

    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;

    Object.assign(notification.style, {
        position: 'fixed',
        top: '20px',
        right: '20px',
        padding: '12px 24px',
        borderRadius: '6px',
        color: 'white',
        fontWeight: '500',
        zIndex: '1000',
        boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
        animation: 'fadeIn 0.3s ease'
    });

    if (type === 'success') notification.style.background = '#10b981';
    else if (type === 'error') notification.style.background = '#ef4444';
    else notification.style.background = '#3b82f6';

    document.body.appendChild(notification);
    setTimeout(() => notification.remove(), 4000);
}
