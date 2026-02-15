// Character Forge Logic

let currentCharacterData = null; // Holds the JSON of the character being worked on

document.addEventListener('DOMContentLoaded', () => {
    loadCharacterList();
});

function switchTab(tab) {
    // Buttons
    document.querySelectorAll('.mode-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById(`tab-${tab}`).classList.add('active');

    // Views
    document.getElementById('create-view').style.display = tab === 'create' ? 'block' : 'none';
    document.getElementById('modify-view').style.display = tab === 'modify' ? 'block' : 'none';
}

// ──────────────────────────────────────────────
//  CREATE MODE
// ──────────────────────────────────────────────

async function generateCharacter() {
    const desc = document.getElementById('create-desc').value.trim();
    if (!desc) {
        showNotification('Please enter a description first', 'warning');
        return;
    }

    const btn = document.querySelector('button[onclick="generateCharacter()"]');
    const originalText = btn.textContent;
    btn.textContent = '🔨 Forging... (This may take a moment)';
    btn.disabled = true;

    try {
        const result = await API.createCharacter(desc);

        if (result.status === 'success') {
            const char = result.character;

            // Populate preview
            document.getElementById('char-name').value = char.name || '';
            document.getElementById('char-description').value = char.description || '';
            document.getElementById('char-personality').value = char.personality || '';
            document.getElementById('char-first-mes').value = char.first_mes || '';

            // Enable save
            document.getElementById('btn-save-new').disabled = false;

            showNotification('Character generated successfully!', 'success');
        }
    } catch (error) {
        console.error('Generation failed:', error);
        showNotification('Failed to generate character: ' + error.message, 'error');
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

async function saveCharacter() {
    // Gather data from fields (in case user edited)
    const charData = {
        name: document.getElementById('char-name').value,
        description: document.getElementById('char-description').value,
        personality: document.getElementById('char-personality').value,
        first_mes: document.getElementById('char-first-mes').value,
        scenario: "", // Basic default
        mes_example: "" // Basic default
    };

    if (!charData.name) {
        showNotification('Character name is required', 'warning');
        return;
    }

    try {
        const filename = charData.name.replace(/[^a-z0-9]/gi, '_').toLowerCase();
        await API.saveCharacter(filename, charData);
        showNotification(`Saved to ${filename}.json`, 'success');

        // Refresh list if we switch content
        loadCharacterList();
    } catch (error) {
        showNotification('Save failed: ' + error.message, 'error');
    }
}

// ──────────────────────────────────────────────
//  MODIFY MODE
// ──────────────────────────────────────────────

async function loadCharacterList() {
    const select = document.getElementById('modify-select');
    try {
        const result = await API.listCharacters();

        select.innerHTML = '<option value="">Select a character...</option>';

        // Filter to JSON files only
        const jsonFiles = (result.characters || []).filter(f => f.endsWith('.json'));

        if (jsonFiles.length === 0) {
            select.innerHTML = '<option value="">No characters found — check Settings</option>';
            showNotification('No character files found. Ensure your Characters directory is configured in Settings.', 'warning');
            return;
        }

        jsonFiles.forEach(file => {
            const option = document.createElement('option');
            option.value = file;
            option.textContent = file;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading characters:', error);
        select.innerHTML = '<option value="">Error loading characters</option>';
        showNotification('Failed to load character list: ' + error.message, 'error');
    }
}

async function loadForModification() {
    const file = document.getElementById('modify-select').value;
    if (!file) return;

    addChatMessage('ai', `Loading ${file}...`);

    try {
        const content = await API.loadCharacter(file);
        currentCharacterData = content;

        // Update fields
        updateModifyPreview();

        // Enable chat
        document.getElementById('chat-input').disabled = false;
        document.getElementById('btn-send-mod').disabled = false;
        document.getElementById('btn-save-mod').disabled = false;

        addChatMessage('ai', `Loaded ${file}. I've analyzed the profile. What would you like to change? (e.g., "Make him 50 years older", "Change his job to Baker")`);

    } catch (error) {
        addChatMessage('ai', `Error loading file: ${error.message}`);
    }
}

function updateModifyPreview() {
    if (!currentCharacterData) return;
    document.getElementById('mod-name').value = currentCharacterData.name || '';
    document.getElementById('mod-description').value = currentCharacterData.description || '';
    document.getElementById('mod-first-mes').value = currentCharacterData.first_mes || '';
}

async function sendModification() {
    const input = document.getElementById('chat-input');
    const instruction = input.value.trim();
    if (!instruction) return;

    // User message
    addChatMessage('user', instruction);
    input.value = '';

    // AI processing
    addChatMessage('ai', 'Working on it...');

    try {
        const result = await API.modifyCharacter(currentCharacterData, instruction);

        if (result.status === 'success') {
            currentCharacterData = result.character;
            updateModifyPreview();
            addChatMessage('ai', 'Done! I have updated the preview on the right.');
        }
    } catch (error) {
        addChatMessage('ai', `Error: ${error.message}`);
    }
}

async function saveModifiedCharacter() {
    if (!currentCharacterData) return;
    try {
        // Overwrite usage
        const filename = document.getElementById('modify-select').value;
        // Or generic save
        await API.saveCharacter(filename, currentCharacterData);
        showNotification('Changes saved successfully!', 'success');
    } catch (error) {
        showNotification('Save failed: ' + error.message, 'error');
    }
}

// ──────────────────────────────────────────────
//  UTILITIES
// ──────────────────────────────────────────────

function addChatMessage(role, text) {
    const container = document.getElementById('chat-history');
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.textContent = text;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function showNotification(message, type = 'info') {
    // Reuse existing notification logic from other files (or duplicate it here for safety)
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
        notification.remove();
    }, 5000);
}

// Extension to API for loading file
API.loadCharacter = async function (filename) {
    const response = await fetch(`${API_BASE}/character/load?filename=${encodeURIComponent(filename)}`);
    return await this._handleResponse(response);
};
