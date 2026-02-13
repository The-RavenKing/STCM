// API Client for STCM
const API_BASE = '/api';

class API {
    // Config
    static async getConfig() {
        const response = await fetch(`${API_BASE}/config`);
        return await response.json();
    }
    
    static async updateConfig(updates) {
        const response = await fetch(`${API_BASE}/config`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(updates)
        });
        return await response.json();
    }
    
    // Ollama
    static async testOllama() {
        const response = await fetch(`${API_BASE}/test/ollama`, {
            method: 'POST'
        });
        return await response.json();
    }
    
    // Scans
    static async runScan(chatFile, messagesLimit = 50) {
        const response = await fetch(`${API_BASE}/scan/manual`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                chat_file: chatFile,
                messages_limit: messagesLimit
            })
        });
        return await response.json();
    }
    
    // Queue
    static async getQueue(entityType = null) {
        const url = entityType 
            ? `${API_BASE}/queue?entity_type=${entityType}`
            : `${API_BASE}/queue`;
        const response = await fetch(url);
        return await response.json();
    }
    
    static async approveEntity(entityId) {
        const response = await fetch(`${API_BASE}/queue/${entityId}/approve`, {
            method: 'POST'
        });
        return await response.json();
    }
    
    static async rejectEntity(entityId) {
        const response = await fetch(`${API_BASE}/queue/${entityId}/reject`, {
            method: 'POST'
        });
        return await response.json();
    }
    
    static async editEntity(entityId, entityData) {
        const response = await fetch(`${API_BASE}/queue/${entityId}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({entity_data: entityData})
        });
        return await response.json();
    }
    
    // History
    static async getScanHistory(limit = 50) {
        const response = await fetch(`${API_BASE}/history/scans?limit=${limit}`);
        return await response.json();
    }
    
    static async getUpdateHistory(limit = 100) {
        const response = await fetch(`${API_BASE}/history/updates?limit=${limit}`);
        return await response.json();
    }
    
    // Files
    static async listChats() {
        const response = await fetch(`${API_BASE}/files/chats`);
        return await response.json();
    }
    
    static async listBackups(filePath = null) {
        const url = filePath 
            ? `${API_BASE}/files/backups?file_path=${filePath}`
            : `${API_BASE}/files/backups`;
        const response = await fetch(url);
        return await response.json();
    }
    
    // Mappings
    static async getMappings() {
        const response = await fetch(`${API_BASE}/mappings`);
        return await response.json();
    }
    
    static async addMapping(chatFile, characterFile, personaFile = null) {
        const response = await fetch(`${API_BASE}/mappings`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                chat_file: chatFile,
                character_file: characterFile,
                persona_file: personaFile
            })
        });
        return await response.json();
    }
    
    // Stats
    static async getStats() {
        const response = await fetch(`${API_BASE}/stats`);
        return await response.json();
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

// Initialize WebSocket
const ws = new WSClient();
