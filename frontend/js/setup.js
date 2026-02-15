// Setup Wizard JavaScript

let currentStep = 1;
const totalSteps = 3;

// ─────────────────────────────────────────
//  Step Navigation
// ─────────────────────────────────────────

function showStep(step) {
    // Hide all panels
    for (let i = 1; i <= totalSteps; i++) {
        const panel = document.getElementById('step-' + i);
        if (panel) panel.classList.toggle('active', i === step);
    }

    // Update dots
    for (let i = 1; i <= totalSteps; i++) {
        const dot = document.getElementById('dot-' + i);
        dot.classList.remove('active', 'done');
        if (i < step) dot.classList.add('done');
        else if (i === step) dot.classList.add('active');
    }

    // Update connectors
    for (let i = 1; i < totalSteps; i++) {
        const conn = document.getElementById('conn-' + i);
        conn.classList.toggle('done', i < step);
    }

    // Update nav buttons
    const backBtn = document.getElementById('btn-back');
    const nextBtn = document.getElementById('btn-next');
    const nav = document.getElementById('step-nav');

    if (step === totalSteps) {
        // Done step — hide nav entirely
        nav.style.display = 'none';
    } else {
        nav.style.display = 'flex';
        backBtn.style.visibility = step === 1 ? 'hidden' : 'visible';
        nextBtn.textContent = step === totalSteps - 1 ? 'Save & Finish →' : 'Next →';
    }

    currentStep = step;
}

function nextStep() {
    if (currentStep === 1) {
        // No validation required for step 1 — Ollama defaults are fine
        showStep(2);
    } else if (currentStep === 2) {
        // Validate required SillyTavern paths
        const chats = document.getElementById('setup-chats-dir').value.trim();
        const chars = document.getElementById('setup-characters-dir').value.trim();

        if (!chats || !chars) {
            showNotification('Chat Logs and Characters directories are required.', 'error');
            return;
        }

        // Save everything
        saveConfig();
    }
}

function prevStep() {
    if (currentStep > 1) {
        showStep(currentStep - 1);
    }
}

// ─────────────────────────────────────────
//  Save Config
// ─────────────────────────────────────────

async function saveConfig() {
    const btn = document.getElementById('btn-next');
    btn.disabled = true;
    btn.textContent = 'Saving...';

    const updates = {
        ollama: {
            url: document.getElementById('setup-ollama-url').value.trim() || 'http://localhost:11434',
            reader_model: document.getElementById('setup-reader-model').value,
            coder_model: document.getElementById('setup-coder-model').value,
        },
        sillytavern: {
            chats_dir: document.getElementById('setup-chats-dir').value.trim(),
            characters_dir: document.getElementById('setup-characters-dir').value.trim(),
            personas_dir: document.getElementById('setup-personas-dir').value.trim() || null,
            lorebooks_dir: document.getElementById('setup-lorebooks-dir').value.trim() || null,
        }
    };

    // Include API key only if provided
    const apiKey = document.getElementById('setup-api-key').value.trim();
    if (apiKey) {
        updates.ollama.api_key = apiKey;
    }

    try {
        await API.updateConfig(updates);
        showStep(3);
    } catch (error) {
        showNotification('Failed to save settings: ' + error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Save & Finish →';
    }
}

// ─────────────────────────────────────────
//  Test Ollama Connection
// ─────────────────────────────────────────

async function testConnection() {
    const el = document.getElementById('test-result');
    el.textContent = 'Testing...';
    el.className = 'test-result';

    try {
        const result = await API.testOllama();
        if (result.status === 'success') {
            el.textContent = '✓ Connected!';
            el.className = 'test-result ok';

            // Populate dropdowns if models are available
            if (result.available_models && result.available_models.length > 0) {
                populateModelDropdowns(result.available_models);
            }
        } else {
            el.textContent = '✗ ' + (result.message || 'Connection failed');
            el.className = 'test-result fail';
        }
    } catch (error) {
        el.textContent = '✗ Could not reach Ollama';
        el.className = 'test-result fail';
    }
}

function populateModelDropdowns(models) {
    const readerSelect = document.getElementById('setup-reader-model');
    const coderSelect = document.getElementById('setup-coder-model');

    // Save current selections
    const currentReader = readerSelect.value;
    const currentCoder = coderSelect.value;

    // Helper to clear and fill
    const fillSelect = (select, currentVal) => {
        if (!select) return;

        select.innerHTML = '';
        models.forEach(model => {
            const name = model.name || model; // Handle object or string
            const option = document.createElement('option');
            option.value = name;
            option.textContent = name;
            if (name === currentVal) option.selected = true;
            select.appendChild(option);
        });

        // Add current value if missing (custom/offline case)
        if (currentVal && !models.some(m => (m.name || m) === currentVal)) {
            const option = document.createElement('option');
            option.value = currentVal;
            option.textContent = `${currentVal} (Cached)`;
            option.selected = true;
            select.appendChild(option);
        }
    };

    fillSelect(readerSelect, currentReader);
    fillSelect(coderSelect, currentCoder);

    showNotification(`Found ${models.length} models`, 'success');
}

// ─────────────────────────────────────────
//  Notification
// ─────────────────────────────────────────

function showNotification(message, type = 'info') {
    const existing = document.querySelector('.notification');
    if (existing) existing.remove();

    const notification = document.createElement('div');
    notification.className = 'notification ' + type;
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
    });

    if (type === 'success') notification.style.background = '#10b981';
    else if (type === 'error') notification.style.background = '#ef4444';
    else notification.style.background = '#3b82f6';

    document.body.appendChild(notification);
    setTimeout(() => notification.remove(), 5000);
}
