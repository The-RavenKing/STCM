// Settings Page JavaScript

document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
    loadMappings();
    
    // Form submit handler
    document.getElementById('settings-form').addEventListener('submit', saveSettings);
});

async function loadSettings() {
    try {
        const config = await API.getConfig();
        
        // Populate form fields
        document.getElementById('ollama-url').value = config.ollama.url || '';
        document.getElementById('ollama-model').value = config.ollama.model || 'llama3.2';
        
        if (config.sillytavern) {
            document.getElementById('chats-dir').value = config.sillytavern.chats_dir || '';
            document.getElementById('characters-dir').value = config.sillytavern.characters_dir || '';
            document.getElementById('personas-dir').value = config.sillytavern.personas_dir || '';
        }
        
        if (config.scanning) {
            document.getElementById('scan-schedule').value = config.scanning.schedule || '';
            document.getElementById('messages-per-scan').value = config.scanning.messages_per_scan || 50;
            document.getElementById('scan-recent-only').checked = config.scanning.scan_recent_only || false;
            document.getElementById('confidence-threshold').value = config.scanning.confidence_threshold || 0.7;
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

async function loadMappings() {
    try {
        const { database_mappings, config_mappings } = await API.getMappings();
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
    }
}

function addMapping() {
    addMappingRow();
}

function addMappingRow(chatFile = '', characterFile = '', personaFile = '') {
    const container = document.getElementById('mappings-list');
    
    const row = document.createElement('div');
    row.className = 'mapping-row';
    row.innerHTML = `
        <input type="text" placeholder="Chat file (e.g., Jinx_-_2026-02-13.jsonl)" 
               value="${chatFile}" class="mapping-chat">
        <input type="text" placeholder="Character file (e.g., Jinx__2_.json)" 
               value="${characterFile}" class="mapping-character">
        <input type="text" placeholder="Persona file (optional)" 
               value="${personaFile || ''}" class="mapping-persona">
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
        } else {
            resultEl.textContent = '✗ Failed';
            resultEl.style.color = 'var(--danger-color)';
            
            showNotification(result.message, 'error');
        }
    } catch (error) {
        resultEl.textContent = '✗ Error';
        resultEl.style.color = 'var(--danger-color)';
        
        showNotification('Failed to connect to Ollama', 'error');
    }
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
