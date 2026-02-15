// API Client for STCM
const API_BASE = '/api';

class API {
    // Shared response handler — validates status and parses JSON
    static async _handleResponse(response) {
        if (!response.ok) {
            let detail = `HTTP ${response.status}`;
            try {
                const body = await response.json();
                detail = body.detail || body.message || detail;
            } catch { /* non-JSON error body */ }
            throw new Error(detail);
        }
        return await response.json();
    }

    // Config
    static async getConfig() {
        const response = await fetch(`${API_BASE}/config`);
        return await this._handleResponse(response);
    }

    static async updateConfig(updates) {
        const response = await fetch(`${API_BASE}/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates)
        });
        return await this._handleResponse(response);
    }

    // Ollama
    static async testOllama() {
        const response = await fetch(`${API_BASE}/test/ollama`, {
            method: 'POST'
        });
        return await this._handleResponse(response);
    }

    // Scans
    static async runScan(chatFile, messagesLimit = 50) {
        const response = await fetch(`${API_BASE}/scan/manual`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chat_file: chatFile,
                messages_limit: messagesLimit
            })
        });
        return await this._handleResponse(response);
    }

    // Queue
    static async getQueue(entityType = null) {
        const url = entityType
            ? `${API_BASE}/queue?entity_type=${entityType}`
            : `${API_BASE}/queue`;
        const response = await fetch(url);
        return await this._handleResponse(response);
    }

    static async approveEntity(entityId) {
        const response = await fetch(`${API_BASE}/queue/${entityId}/approve`, {
            method: 'POST'
        });
        return await this._handleResponse(response);
    }

    static async rejectEntity(entityId) {
        const response = await fetch(`${API_BASE}/queue/${entityId}/reject`, {
            method: 'POST'
        });
        return await this._handleResponse(response);
    }

    static async editEntity(entityId, entityData) {
        const response = await fetch(`${API_BASE}/queue/${entityId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ entity_data: entityData })
        });
        return await this._handleResponse(response);
    }

    // History
    static async getScanHistory(limit = 50) {
        const response = await fetch(`${API_BASE}/history/scans?limit=${limit}`);
        return await this._handleResponse(response);
    }

    static async getUpdateHistory(limit = 100) {
        const response = await fetch(`${API_BASE}/history/updates?limit=${limit}`);
        return await this._handleResponse(response);
    }

    // Files
    static async listChats() {
        const response = await fetch(`${API_BASE}/files/chats`);
        return await this._handleResponse(response);
    }

    static async listCharacters() {
        const response = await fetch(`${API_BASE}/files/characters`);
        return await this._handleResponse(response);
    }

    static async listPersonas() {
        const response = await fetch(`${API_BASE}/files/personas`);
        return await this._handleResponse(response);
    }

    static async listBackups(filePath = null) {
        const url = filePath
            ? `${API_BASE}/files/backups?file_path=${filePath}`
            : `${API_BASE}/files/backups`;
        const response = await fetch(url);
        return await this._handleResponse(response);
    }

    static async verifyPath(path, type) {
        const response = await fetch(`${API_BASE}/files/verify-path`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path, type })
        });
        return await this._handleResponse(response);
    }

    // Mappings
    static async getMappings() {
        const response = await fetch(`${API_BASE}/mappings`);
        return await this._handleResponse(response);
    }

    static async addMapping(chatFile, characterFile, personaFile = null) {
        const response = await fetch(`${API_BASE}/mappings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chat_file: chatFile,
                character_file: characterFile,
                persona_file: personaFile
            })
        });
        return await this._handleResponse(response);
    }

    // Stats
    static async getStats() {
        const response = await fetch(`${API_BASE}/stats`);
        return await this._handleResponse(response);
    }

    // Lorebook Builder
    static async buildLorebook(request) {
        const response = await fetch(`${API_BASE}/lorebook/build`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request)
        });
        return await this._handleResponse(response);
    }

    static async listLorebooks() {
        const response = await fetch(`${API_BASE}/lorebook/list`);
        return await this._handleResponse(response);
    }

    static async createLorebook(name) {
        const response = await fetch(`${API_BASE}/lorebook/create`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        return await this._handleResponse(response);
    }

    static async getLorebook(name) {
        const response = await fetch(`${API_BASE}/lorebook/${encodeURIComponent(name)}`);
        return await this._handleResponse(response);
    }

    // Character Forge
    static async listCharacters() {
        const response = await fetch(`${API_BASE}/files/characters`);
        return await this._handleResponse(response);
    }

    static async createCharacter(description) {
        const response = await fetch(`${API_BASE}/character/create`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ description })
        });
        return await this._handleResponse(response);
    }

    static async modifyCharacter(characterData, instructions) {
        const response = await fetch(`${API_BASE}/character/modify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ character_data: characterData, instructions })
        });
        return await this._handleResponse(response);
    }

    static async summarizeCharacter(characterData) {
        const response = await fetch(`${API_BASE}/character/summary`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ character_data: characterData, instructions: "" }) // Schema reuses modify request
        });
        return await this._handleResponse(response);
    }

    static async saveCharacter(filename, characterData) {
        const response = await fetch(`${API_BASE}/character/save`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename, character_data: characterData })
        });
        return await this._handleResponse(response);
    }
}

// WebSocket Connection
class WSClient {
    constructor() {
        this.ws = null;
        this.callbacks = [];
        this.connect();
    }

    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.updateStatus(true);
        };

        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.updateStatus(false);
            // Reconnect after 5 seconds
            setTimeout(() => this.connect(), 5000);
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.callbacks.forEach(cb => cb(data));
        };
    }

    updateStatus(connected) {
        const indicator = document.getElementById('ws-status');
        const message = document.getElementById('status-message');

        if (indicator) {
            indicator.className = connected ? 'ws-indicator connected' : 'ws-indicator disconnected';
        }

        if (message) {
            message.textContent = connected ? 'Connected' : 'Disconnected';
        }
    }

    onMessage(callback) {
        this.callbacks.push(callback);
    }
}

// Initialize WebSocket (skip on setup wizard page — no ws-status element there)
const ws = window.location.pathname === '/setup' ? null : new WSClient();
