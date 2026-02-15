// Settings Page JavaScript

// Escape for attribute values
function escapeAttr(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

document.addEventListener('DOMContentLoaded', async () => {
    await loadSettings();  // Must complete first so current values are set
    loadMappings();
    fetchModels();  // Then populate dropdowns with fresh models from Ollama

    // Form submit handler
    document.getElementById('settings-form').addEventListener('submit', saveSettings);
});

async function fetchModels() {
    try {
        const result = await API.testOllama();
        if (result.available_models && result.available_models.length > 0) {
            populateModelDropdowns(result.available_models);
        }
    } catch (error) {
        // Silently fail — user can click Test Connection manually
        console.log('Auto-fetch models failed (Ollama may be offline):', error.message);
    }
}

async function loadSettings() {
    try {
        const config = await API.getConfig();

        // Populate form fields
        document.getElementById('ollama-url').value = config.ollama.url || '';
        document.getElementById('ollama-model').value = config.ollama.reader_model || config.ollama.model || 'llama3.2';

        // Populate coder model field if it exists in the DOM
        const coderModelEl = document.getElementById('ollama-coder-model');
        if (coderModelEl) {
            coderModelEl.value = config.ollama.coder_model || config.ollama.model || 'llama3.2';
        }

        if (config.sillytavern) {
            document.getElementById('chats-dir').value = config.sillytavern.chats_dir || '';
            document.getElementById('characters-dir').value = config.sillytavern.characters_dir || '';
            document.getElementById('personas-dir').value = config.sillytavern.personas_dir || '';
            document.getElementById('lorebooks-dir').value = config.sillytavern.lorebooks_dir || '';
        }

        if (config.scanning) {
            document.getElementById('scan-schedule').value = config.scanning.schedule || '';
            document.getElementById('messages-per-scan').value = config.scanning.messages_per_scan || 50;
            document.getElementById('scan-recent-only').checked = config.scanning.scan_recent_only || false;
            document.getElementById('confidence-threshold').value = config.scanning.confidence_threshold || 0.7;
            document.getElementById('chunk-size').value = config.scanning.chunk_size || 25;
            document.getElementById('chunk-overlap').value = config.scanning.chunk_overlap || 10;
        }

        if (config.auto_apply) {
            document.getElementById('auto-apply-enabled').checked = config.auto_apply.enabled || false;
            document.getElementById('high-confidence-threshold').value = config.auto_apply.high_confidence_threshold || 0.9;
            document.getElementById('create-backups').checked = config.auto_apply.create_backups !== false;
            document.getElementById('backup-retention').value = config.auto_apply.backup_retention_days || 30;
        }

        if (config.entity_tracking) {
            document.getElementById('track-npcs').checked = config.entity_tracking.npcs !== false;
            document.getElementById('track-factions').checked = config.entity_tracking.factions !== false;
            document.getElementById('track-locations').checked = config.entity_tracking.locations !== false;
            document.getElementById('track-items').checked = config.entity_tracking.items !== false;
            document.getElementById('track-aliases').checked = config.entity_tracking.aliases !== false;
            document.getElementById('track-stats').checked = config.entity_tracking.stats !== false;
        }

    } catch (error) {
        console.error('Error loading settings:', error);
        showNotification('Error loading settings', 'error');
    }
}

async function verifyPath(type, inputId) {
    const input = document.getElementById(inputId);
    const path = input.value.trim();
    const resultSpan = document.getElementById(inputId + '-result');

    if (!path) {
        showNotification('Please enter a path first', 'warning');
        return;
    }

    // Create result span if missing
    let display = resultSpan;
    if (!display) {
        display = document.createElement('div');
        display.id = inputId + '-result';
        display.className = 'verify-result';
        input.parentNode.appendChild(display);
    }

    display.textContent = 'Checking...';
    display.className = 'verify-result';

    try {
        const response = await API.verifyPath(path, type);

        display.textContent = response.message;

        if (response.status === 'success') {
            display.className = 'verify-result success';

            // Show sample files in tooltip or console
            if (response.files && response.files.length > 0) {
                const samples = response.files.join('\n');
                display.title = `Found:\n${samples}...`;
            }
        } else if (response.status === 'warning') {
            display.className = 'verify-result warning';
        } else {
            console.error(response);
            display.className = 'verify-result error';
        }

    } catch (error) {
        console.error(error);
        display.textContent = 'Error: ' + error.message;
        display.className = 'verify-result error';
    }
}

async function saveSettings(event) {
    event.preventDefault();

    const form = event.target;
    const formData = new FormData(form);

    // Build config object from form
    const updates = {};

    for (const [name, value] of formData.entries()) {
        // Handle checkboxes
        const input = form.elements[name];
        if (input.type === 'checkbox') {
            setNestedValue(updates, name, input.checked);
        } else if (input.type === 'number') {
            setNestedValue(updates, name, parseFloat(value));
        } else {
            setNestedValue(updates, name, value);
        }
    }

    try {
        await API.updateConfig(updates);
        showNotification('Settings saved successfully!', 'success');
    } catch (error) {
        console.error('Error saving settings:', error);
        showNotification('Error saving settings', 'error');
    }
}

function setNestedValue(obj, path, value) {
    const keys = path.split('.');
    let current = obj;

    for (let i = 0; i < keys.length - 1; i++) {
        if (!(keys[i] in current)) {
            current[keys[i]] = {};
        }
        current = current[keys[i]];
    }

    current[keys[keys.length - 1]] = value;
}

// Chat Mapping Functions

// Global state for file lists
let availableChats = [];
let availableCharacters = [];
let availablePersonas = [];

async function loadMappings() {
    try {
        // Fetch all lists in parallel
        const [mappingsData, chatsData, charsData, personasData] = await Promise.all([
            API.getMappings(),
            API.listChats(),
            API.listCharacters(),
            API.listPersonas()
        ]);

        const { database_mappings, config_mappings } = mappingsData;

        // Update global lists
        availableChats = chatsData.chats || []; // These are objects: {file: "name", ...}
        availableCharacters = charsData.characters || []; // Strings
        availablePersonas = personasData.personas || []; // Strings

        const container = document.getElementById('mappings-list');
        if (!container) return;

        container.innerHTML = '';

        // Load from database
        database_mappings.forEach(mapping => {
            addMappingRow(mapping.chat_file, mapping.character_file, mapping.persona_file);
        });

        // If no mappings, show one empty row
        if (database_mappings.length === 0) {
            addMappingRow();
        }

    } catch (error) {
        console.error('Error loading mappings:', error);
        showNotification('Error loading mapping data', 'error');
    }
}

function addMapping() {
    addMappingRow();
}

function addMappingRow(chatFile = '', characterFile = '', personaFile = '') {
    const container = document.getElementById('mappings-list');

    const row = document.createElement('div');
    row.className = 'mapping-row';

    // Helper to generate options
    const generateOptions = (items, selected, isChatObj = false) => {
        let html = '<option value="">-- Select --</option>';
        let found = false;

        items.forEach(item => {
            const val = isChatObj ? item.file : item;
            const isSelected = val === selected;
            if (isSelected) found = true;
            html += `<option value="${escapeAttr(val)}" ${isSelected ? 'selected' : ''}>${escapeAttr(val)}</option>`;
        });

        // Preserve existing value if not in list (e.g. deleted file)
        if (selected && !found) {
            html += `<option value="${escapeAttr(selected)}" selected>${escapeAttr(selected)} (Missing)</option>`;
        }
        return html;
    };

    row.innerHTML = `
        <select class="mapping-chat input-select">
            ${generateOptions(availableChats, chatFile, true)}
        </select>
        <select class="mapping-character input-select">
            ${generateOptions(availableCharacters, characterFile)}
        </select>
        <select class="mapping-persona input-select">
            ${generateOptions(availablePersonas, personaFile)}
        </select>
        <button type="button" onclick="saveMapping(this)" class="btn-secondary btn-small">Save</button>
        <button type="button" onclick="removeMapping(this)" class="btn-danger btn-small">Remove</button>
    `;

    container.appendChild(row);
}

async function saveMapping(button) {
    const row = button.parentElement;
    const chatFile = row.querySelector('.mapping-chat').value;
    const characterFile = row.querySelector('.mapping-character').value;
    const personaFile = row.querySelector('.mapping-persona').value;

    if (!chatFile || !characterFile) {
        showNotification('Chat file and character file are required', 'warning');
        return;
    }

    try {
        await API.addMapping(chatFile, characterFile, personaFile || null);
        showNotification('Mapping saved!', 'success');
    } catch (error) {
        console.error('Error saving mapping:', error);
        showNotification('Error saving mapping', 'error');
    }
}

function removeMapping(button) {
    const row = button.parentElement;
    row.remove();
}

// Test Ollama function (same as dashboard)
async function testOllama() {
    const resultEl = document.getElementById('ollama-test-result');
    resultEl.textContent = 'Testing...';

    try {
        const result = await API.testOllama();

        if (result.status === 'success') {
            resultEl.textContent = '✓ Connected';
            resultEl.style.color = 'var(--success-color)';

            showNotification('Ollama connection successful!', 'success');

            // Populate dropdowns if models are available
            if (result.available_models && result.available_models.length > 0) {
                populateModelDropdowns(result.available_models);
            }
        } else {
            resultEl.textContent = '✗ Failed';
            resultEl.style.color = 'var(--danger-color)';

            showNotification(result.message, 'error');

            // Still populate dropdowns if models available (partial connection)
            if (result.available_models && result.available_models.length > 0) {
                populateModelDropdowns(result.available_models);
            }
        }
    } catch (error) {
        console.error(error);
        resultEl.textContent = '✗ Error';
        resultEl.style.color = 'var(--danger-color)';

        showNotification('Failed to connect to Ollama', 'error');
    }
}

function populateModelDropdowns(models) {
    const readerSelect = document.getElementById('ollama-model');
    const coderSelect = document.getElementById('ollama-coder-model'); // If exists

    // Save current selections
    const currentReader = readerSelect.value;
    const currentCoder = coderSelect ? coderSelect.value : null;

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

    showNotification(`Found ${models.length} models`, 'info');
}

// Notification function (same as dashboard)
function showNotification(message, type = 'info') {
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

    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}
