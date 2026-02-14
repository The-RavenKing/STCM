// Review Queue JavaScript

let allEntities = [];
let filteredEntities = [];

// XSS prevention: escape HTML in user-controlled content
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(String(str)));
    return div.innerHTML;
}

// Escape for use inside HTML attribute values (e.g. input value="...")
function escapeAttr(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

document.addEventListener('DOMContentLoaded', () => {
    loadEntities();

    // Setup edit form handler
    document.getElementById('edit-form').addEventListener('submit', saveEdit);
});

async function loadEntities() {
    try {
        const { entities, count } = await API.getQueue();
        allEntities = entities;
        filteredEntities = entities;

        document.getElementById('total-count').textContent = `${count} entities pending review`;

        renderEntities();
    } catch (error) {
        console.error('Error loading entities:', error);
        document.getElementById('entity-list').innerHTML =
            '<p class="loading">Error loading entities</p>';
    }
}

function renderEntities() {
    const container = document.getElementById('entity-list');

    if (filteredEntities.length === 0) {
        container.innerHTML = '<p class="loading">No entities to review</p>';
        return;
    }

    container.innerHTML = filteredEntities.map(entity => createEntityCard(entity)).join('');

    // Update filtered count
    const filteredCount = document.getElementById('filtered-count');
    if (filteredEntities.length !== allEntities.length) {
        filteredCount.textContent = `(showing ${filteredEntities.length})`;
    } else {
        filteredCount.textContent = '';
    }
}

function createEntityCard(entity) {
    const data = entity.entity_data;
    const confidence = entity.confidence_score || 0;
    const confidenceClass = confidence > 0.8 ? 'high' : confidence > 0.5 ? 'medium' : 'low';
    const confidenceLabel = confidence > 0.8 ? 'High' : confidence > 0.5 ? 'Medium' : 'Low';

    return `
        <div class="entity-card ${confidenceClass}-confidence" data-id="${entity.id}" data-type="${escapeHtml(entity.entity_type)}">
            <div class="entity-header">
                <div class="entity-title">
                    <h3 class="entity-name">${escapeHtml(entity.entity_name)}</h3>
                    <span class="entity-type-badge ${escapeHtml(entity.entity_type)}">${escapeHtml(entity.entity_type)}</span>
                </div>
                <span class="confidence-badge ${confidenceClass}">
                    ${confidenceLabel} (${(confidence * 100).toFixed(0)}%)
                </span>
            </div>
            
            <div class="entity-body">
                ${renderEntityFields(entity.entity_type, data)}
                
                ${data.source_context ? `
                    <div class="entity-field">
                        <label>Source Context:</label>
                        <div class="source-context">"${escapeHtml(data.source_context)}"</div>
                    </div>
                ` : ''}
                
                <div class="target-info">
                    <strong>Will be added to:</strong> ${escapeHtml(entity.target_file.split('/').pop())}
                </div>
            </div>
            
            <div class="entity-actions">
                <button class="btn-approve" onclick="approveEntity(${entity.id})">
                    ✓ Approve
                </button>
                <button class="btn-edit" onclick="editEntity(${entity.id})">
                    ✏️ Edit
                </button>
                <button class="btn-reject" onclick="rejectEntity(${entity.id})">
                    ✗ Reject
                </button>
            </div>
        </div>
    `;
}

function renderEntityFields(type, data) {
    const fields = [];

    // Description (common to all)
    if (data.description) {
        fields.push(`
            <div class="entity-field">
                <label>Description:</label>
                <div class="entity-field-value">${escapeHtml(data.description)}</div>
            </div>
        `);
    }

    // Type-specific fields
    if (type === 'npc') {
        if (data.relationship) {
            fields.push(`
                <div class="entity-field">
                    <label>Relationship to Player:</label>
                    <div class="entity-field-value">${escapeHtml(data.relationship)}</div>
                </div>
            `);
        }
    } else if (type === 'faction') {
        if (data.goals) fields.push(`<div class="entity-field"><label>Goals:</label><div class="entity-field-value">${escapeHtml(data.goals)}</div></div>`);
        if (data.leadership) fields.push(`<div class="entity-field"><label>Leadership:</label><div class="entity-field-value">${escapeHtml(data.leadership)}</div></div>`);
        if (data.territory) fields.push(`<div class="entity-field"><label>Territory:</label><div class="entity-field-value">${escapeHtml(data.territory)}</div></div>`);
        if (data.relationship) fields.push(`<div class="entity-field"><label>Relationship:</label><div class="entity-field-value">${escapeHtml(data.relationship)}</div></div>`);
    } else if (type === 'location') {
        if (data.significance) fields.push(`<div class="entity-field"><label>Significance:</label><div class="entity-field-value">${escapeHtml(data.significance)}</div></div>`);
    } else if (type === 'item') {
        if (data.properties) fields.push(`<div class="entity-field"><label>Properties:</label><div class="entity-field-value">${escapeHtml(data.properties)}</div></div>`);
    } else if (type === 'alias') {
        if (data.real_identity) fields.push(`<div class="entity-field"><label>Real Identity:</label><div class="entity-field-value">${escapeHtml(data.real_identity)}</div></div>`);
        if (data.purpose) fields.push(`<div class="entity-field"><label>Purpose:</label><div class="entity-field-value">${escapeHtml(data.purpose)}</div></div>`);
        if (data.appearance) fields.push(`<div class="entity-field"><label>Appearance:</label><div class="entity-field-value">${escapeHtml(data.appearance)}</div></div>`);
    }

    return fields.join('');
}

// Filter Functions

function filterEntities() {
    const typeFilter = document.getElementById('filter-type').value;
    const confidenceFilter = document.getElementById('filter-confidence').value;

    filteredEntities = allEntities.filter(entity => {
        // Type filter
        if (typeFilter !== 'all' && entity.entity_type !== typeFilter) {
            return false;
        }

        // Confidence filter
        const confidence = entity.confidence_score || 0;
        if (confidenceFilter === 'high' && confidence <= 0.8) return false;
        if (confidenceFilter === 'medium' && (confidence <= 0.5 || confidence > 0.8)) return false;
        if (confidenceFilter === 'low' && confidence > 0.5) return false;

        return true;
    });

    renderEntities();
}

// Action Functions

async function approveEntity(entityId) {
    try {
        await API.approveEntity(entityId);
        showNotification('Entity approved!', 'success');

        // Remove from list
        allEntities = allEntities.filter(e => e.id !== entityId);
        filterEntities();

        // Update count
        document.getElementById('total-count').textContent =
            `${allEntities.length} entities pending review`;
    } catch (error) {
        console.error('Error approving entity:', error);
        showNotification('Error approving entity', 'error');
    }
}

async function rejectEntity(entityId) {
    if (!confirm('Are you sure you want to reject this entity?')) {
        return;
    }

    try {
        await API.rejectEntity(entityId);
        showNotification('Entity rejected', 'success');

        // Remove from list
        allEntities = allEntities.filter(e => e.id !== entityId);
        filterEntities();

        // Update count
        document.getElementById('total-count').textContent =
            `${allEntities.length} entities pending review`;
    } catch (error) {
        console.error('Error rejecting entity:', error);
        showNotification('Error rejecting entity', 'error');
    }
}

function editEntity(entityId) {
    const entity = allEntities.find(e => e.id === entityId);
    if (!entity) return;

    const data = entity.entity_data;

    // Populate form
    document.getElementById('edit-entity-id').value = entityId;
    document.getElementById('edit-name').value = data.name || '';
    document.getElementById('edit-description').value = data.description || '';

    // Add type-specific fields
    const extraFields = document.getElementById('edit-extra-fields');
    extraFields.innerHTML = '';

    if (entity.entity_type === 'npc') {
        extraFields.innerHTML = `
            <div class="form-group">
                <label>Relationship:</label>
                <input type="text" id="edit-relationship" value="${escapeAttr(data.relationship || '')}">
            </div>
        `;
    } else if (entity.entity_type === 'faction') {
        extraFields.innerHTML = `
            <div class="form-group">
                <label>Goals:</label>
                <input type="text" id="edit-goals" value="${escapeAttr(data.goals || '')}">
            </div>
            <div class="form-group">
                <label>Leadership:</label>
                <input type="text" id="edit-leadership" value="${escapeAttr(data.leadership || '')}">
            </div>
        `;
    }

    // Show modal
    document.getElementById('edit-modal').classList.add('active');
}

async function saveEdit(event) {
    event.preventDefault();

    const entityId = parseInt(document.getElementById('edit-entity-id').value);
    const entity = allEntities.find(e => e.id === entityId);
    if (!entity) return;

    const data = { ...entity.entity_data };

    // Update common fields
    data.name = document.getElementById('edit-name').value;
    data.description = document.getElementById('edit-description').value;

    // Update type-specific fields
    if (entity.entity_type === 'npc') {
        const rel = document.getElementById('edit-relationship');
        if (rel) data.relationship = rel.value;
    } else if (entity.entity_type === 'faction') {
        const goals = document.getElementById('edit-goals');
        const leadership = document.getElementById('edit-leadership');
        if (goals) data.goals = goals.value;
        if (leadership) data.leadership = leadership.value;
    }

    try {
        await API.editEntity(entityId, data);
        showNotification('Entity updated!', 'success');

        // Update in local array
        entity.entity_data = data;
        entity.entity_name = data.name;

        // Re-render
        renderEntities();

        // Close modal
        closeEditModal();
    } catch (error) {
        console.error('Error updating entity:', error);
        showNotification('Error updating entity', 'error');
    }
}

function closeEditModal() {
    document.getElementById('edit-modal').classList.remove('active');
}

// Bulk Actions

async function approveAll() {
    if (!confirm(`Approve all ${filteredEntities.length} visible entities?`)) {
        return;
    }

    let success = 0;
    let failed = 0;

    for (const entity of filteredEntities) {
        try {
            await API.approveEntity(entity.id);
            success++;
        } catch (error) {
            failed++;
            console.error('Error approving:', error);
        }
    }

    showNotification(`Approved ${success} entities${failed > 0 ? `, ${failed} failed` : ''}`, 'success');
    loadEntities();
}

async function rejectAll() {
    if (!confirm(`Reject all ${filteredEntities.length} visible entities?`)) {
        return;
    }

    let success = 0;
    let failed = 0;

    for (const entity of filteredEntities) {
        try {
            await API.rejectEntity(entity.id);
            success++;
        } catch (error) {
            failed++;
            console.error('Error rejecting:', error);
        }
    }

    showNotification(`Rejected ${success} entities${failed > 0 ? `, ${failed} failed` : ''}`, 'success');
    loadEntities();
}

// Notification (same as other pages)
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
