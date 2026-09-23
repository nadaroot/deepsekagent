// NonRoot Autonomous AI Agent - Front-End Logic

let eventSource = null;
let isRunning = false;
let attachedImages = [];
let activeAssistantCard = null;
let activeReasoningBox = null;
let activeContentEl = null;

// Sessions State
let sessions = [];
let currentSessionId = null;
let currentWorkspace = '/';
let subagentsData = {}; // subagent_id -> { id, role, prompt, status, events: [], result: null }
let activeModalSubagentId = null;

// DOM Elements
const chatContainer = document.getElementById('chat-container');
const messagesFeed = document.getElementById('messages-feed');
const welcomeScreen = document.getElementById('welcome-screen');
const promptInput = document.getElementById('prompt-input');
const btnSend = document.getElementById('btn-send-prompt');
const btnStop = document.getElementById('btn-stop-agent');
const modelSelect = document.getElementById('model-select');
const statusBadge = null; // removed from UI
const statusText = null;  // removed from UI
const workspacePathEl = document.getElementById('workspace-path');
const workspacePill = document.getElementById('workspace-pill');
const btnTopWorkspace = document.getElementById('btn-top-workspace');
const topWorkspaceName = document.getElementById('top-workspace-name');
const sessionsListEl = document.getElementById('sessions-list');
const btnNewChat = document.getElementById('btn-new-chat');
const fileInput = document.getElementById('file-input');
const btnAttach = document.getElementById('btn-attach-image');
const imagePreviewStrip = document.getElementById('image-preview-strip');

// Scope Elements
const scopeCardRoot = document.getElementById('scope-card-root');
const scopeCardFolder = document.getElementById('scope-card-folder');
const scopeFolderDesc = document.getElementById('scope-folder-desc');

// Workspace Modal
const workspaceModal = document.getElementById('workspace-modal');
const inputModalWorkspace = document.getElementById('input-modal-workspace');
const btnSaveWorkspace = document.getElementById('btn-save-workspace');
const btnCancelWorkspace = document.getElementById('btn-cancel-workspace');
const btnCloseWorkspace = document.getElementById('btn-close-workspace');

// Subagent Modal
const subagentModal = document.getElementById('subagent-modal');
const subagentModalStatus = document.getElementById('subagent-modal-status');
const subagentModalRole = document.getElementById('subagent-modal-role');
const subagentModalPrompt = document.getElementById('subagent-modal-prompt');
const subagentModalFeed = document.getElementById('subagent-modal-feed');
const btnCloseSubagent = document.getElementById('btn-close-subagent');
const btnDismissSubagent = document.getElementById('btn-dismiss-subagent');

// Settings Elements
const settingsModal = document.getElementById('settings-modal');
const btnOpenSettings = document.getElementById('btn-open-settings');
const btnCloseSettings = document.getElementById('btn-close-settings');
const btnCancelSettings = document.getElementById('btn-cancel-settings');
const btnSaveSettings = document.getElementById('btn-save-settings');
const settingApiUrl = document.getElementById('setting-api-url');
const settingApiKey = document.getElementById('setting-api-key');
const settingWorkspace = document.getElementById('setting-workspace');
const settingMaxSteps = document.getElementById('setting-max-steps');
const settingSystemPrompt = document.getElementById('setting-system-prompt');
const settingAutoAccept = document.getElementById('setting-auto-accept');

// ============================================================================
// CHAT SESSIONS & STORAGE
// ============================================================================

function initSessions() {
    try {
        const stored = localStorage.getItem('nonroot_sessions');
        if (stored) {
            sessions = JSON.parse(stored);
        }
    } catch (e) {
        console.error('Failed to parse sessions:', e);
        sessions = [];
    }

    if (!sessions || sessions.length === 0) {
        const defaultSession = createSessionObject('Новый чат');
        sessions = [defaultSession];
        currentSessionId = defaultSession.id;
    } else {
        currentSessionId = sessions[0].id;
    }

    saveSessions();
    renderSessionsList();
    loadActiveSession();
}

function createSessionObject(title) {
    return {
        id: 'sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5),
        title: title || 'Новый чат',
        createdAt: Date.now(),
        workspace: currentWorkspace || '/',
        messages: [] // Array of { role, content, images, reasoning, tools: [], subagents: [] }
    };
}

function saveSessions() {
    try {
        localStorage.setItem('nonroot_sessions', JSON.stringify(sessions));
    } catch (e) {
        console.error('Failed to save sessions:', e);
    }
}

function getActiveSession() {
    return sessions.find(s => s.id === currentSessionId);
}

// Track which workspace groups are collapsed
const collapsedGroups = new Set();

function getWorkspaceGroupName(workspace) {
    if (!workspace || workspace === '/' || workspace === 'whole_machine') return 'Весь ПК';
    try {
        const parts = workspace.replace(/\/$/, '').split('/');
        return parts[parts.length - 1] || workspace;
    } catch (e) { return workspace; }
}

function renderSessionsList() {
    if (!sessionsListEl) return;
    if (sessions.length === 0) {
        sessionsListEl.innerHTML = '<div class="empty-sessions">Нет сохраненных чатов</div>';
        return;
    }

    // Group sessions by workspace
    const groups = new Map(); // workspace -> sessions[]
    sessions.forEach(s => {
        const ws = s.workspace || '/';
        if (!groups.has(ws)) groups.set(ws, []);
        groups.get(ws).push(s);
    });

    let html = '';
    groups.forEach((groupSessions, workspace) => {
        const groupName = getWorkspaceGroupName(workspace);
        const isCollapsed = collapsedGroups.has(workspace);
        const hasActive = groupSessions.some(s => s.id === currentSessionId);
        const groupId = 'grp-' + btoa(workspace).replace(/[^a-zA-Z0-9]/g, '_');

        html += `<div class="session-group ${hasActive ? 'has-active' : ''}" id="${groupId}">`;
        html += `<div class="session-group-header" onclick="toggleGroup('${groupId}', '${workspace.replace(/'/g, "\\'")}')">
            <svg class="group-chevron ${isCollapsed ? 'collapsed' : ''}" width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
            <span class="group-name">${escapeHtml(groupName)}</span>
            <span class="group-count">${groupSessions.length}</span>
        </div>`;

        if (!isCollapsed) {
            html += `<div class="session-group-items">`;
            groupSessions.forEach(s => {
                const isActive = s.id === currentSessionId;
                const timeStr = formatSessionTime(s.createdAt);
                html += `
                    <div class="session-item ${isActive ? 'active' : ''}" onclick="switchSession('${s.id}')">
                        <div class="session-info">
                            <span class="session-title">${escapeHtml(s.title || 'Чат')}</span>
                            <span class="session-time">${timeStr}</span>
                        </div>
                        <button class="session-delete" title="Удалить" onclick="deleteSession('${s.id}', event)">
                            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                        </button>
                    </div>`;
            });
            html += `</div>`;
        }

        html += `</div>`;
    });

    sessionsListEl.innerHTML = html;
}

window.toggleGroup = function(groupId, workspace) {
    if (collapsedGroups.has(workspace)) {
        collapsedGroups.delete(workspace);
    } else {
        collapsedGroups.add(workspace);
    }
    renderSessionsList();
};


function formatSessionTime(timestamp) {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    const now = new Date();
    const isToday = date.toDateString() === now.toDateString();
    if (isToday) {
        const hh = String(date.getHours()).padStart(2, '0');
        const mm = String(date.getMinutes()).padStart(2, '0');
        return `${hh}:${mm}`;
    }
    const dd = String(date.getDate()).padStart(2, '0');
    const mo = String(date.getMonth() + 1).padStart(2, '0');
    return `${dd}.${mo}`;
}

window.switchSession = function(id) {
    if (isRunning) return;
    currentSessionId = id;
    renderSessionsList();
    loadActiveSession();
};

window.deleteSession = function(id, event) {
    if (event) event.stopPropagation();
    if (isRunning) return;
    
    sessions = sessions.filter(s => s.id !== id);
    if (sessions.length === 0) {
        const newSess = createSessionObject('Новый чат');
        sessions = [newSess];
        currentSessionId = newSess.id;
    } else if (currentSessionId === id) {
        currentSessionId = sessions[0].id;
    }
    saveSessions();
    renderSessionsList();
    loadActiveSession();
};

function createNewChat() {
    if (isRunning) return;
    const newSession = createSessionObject('Новый чат');
    sessions.unshift(newSession);
    currentSessionId = newSession.id;
    saveSessions();
    renderSessionsList();
    loadActiveSession();
}

if (btnNewChat) {
    btnNewChat.addEventListener('click', createNewChat);
}

function loadActiveSession() {
    messagesFeed.innerHTML = '';
    activeAssistantCard = null;
    activeReasoningBox = null;
    activeContentEl = null;

    const session = getActiveSession();
    if (!session || !session.messages || session.messages.length === 0) {
        welcomeScreen.classList.remove('hidden');
        updateScopeUI(session ? session.workspace : currentWorkspace);
        return;
    }

    welcomeScreen.classList.add('hidden');

    for (const msg of session.messages) {
        if (msg.role === 'user') {
            const userCard = document.createElement('div');
            userCard.className = 'message-card user';
            let imagesHtml = '';
            if (msg.images && msg.images.length > 0) {
                imagesHtml = '<div class="user-bubble-images">' + 
                    msg.images.map(img => `<img class="user-img-thumb" src="${img}">`).join('') + 
                    '</div>';
            }
            userCard.innerHTML = `<div class="user-bubble">${escapeHtml(msg.content)}${imagesHtml}</div>`;
            messagesFeed.appendChild(userCard);
        } else if (msg.role === 'assistant') {
            const card = document.createElement('div');
            card.className = 'message-card assistant';

            if (msg.reasoning) {
                const reasoningBox = document.createElement('div');
                reasoningBox.className = 'reasoning-box';
                reasoningBox.innerHTML = `
                    <div class="reasoning-header" onclick="toggleReasoning(this)">
                        <div class="reasoning-title-wrap">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a8 8 0 0 0-8 8c0 3.4 2.1 6.3 5.1 7.4.3.1.5.4.5.7v1.9c0 .6.4 1 1 1h2.8c.6 0 1-.4 1-1v-1.9c0-.3.2-.6.5-.7C17.9 16.3 20 13.4 20 10a8 8 0 0 0-8-8z"/></svg>
                            <span>Рассуждения (DeepSeek R1)</span>
                        </div>
                        <span class="reasoning-toggle-icon">▾</span>
                    </div>
                    <div class="reasoning-body">${escapeHtml(msg.reasoning)}</div>
                `;
                card.appendChild(reasoningBox);
            }

            if (msg.tools && msg.tools.length > 0) {
                for (const tool of msg.tools) {
                    if (tool.name === 'spawn_subagent' || tool.is_subagent) {
                        const subId = tool.subagent_id;
                        const subRole = tool.subagent_role || 'Субагент';
                        const subPrompt = tool.subagent_prompt || '';
                        const subCard = createSubagentChatCard(subId, subRole, subPrompt, tool.status || 'completed');
                        card.appendChild(subCard);
                    } else {
                        const toolCard = document.createElement('div');
                        toolCard.className = 'tool-card';
                        const isSuccess = tool.success !== false;
                        toolCard.innerHTML = `
                            <div class="tool-header">
                                <span class="tool-name-badge">
                                    <span class="tool-icon-glyph">›_</span>
                                    ${escapeHtml(tool.name)} 
                                    <span style="color:var(--text-muted);font-weight:normal;">${escapeHtml(tool.summary || '')}</span>
                                </span>
                                <span class="tool-status-tag ${isSuccess ? 'success' : 'error'}">${isSuccess ? 'успешно' : 'ошибка'}</span>
                            </div>
                            <div class="tool-body">${escapeHtml(tool.output || tool.error || '')}</div>
                        `;
                        card.appendChild(toolCard);
                    }
                }
            }

            if (msg.content) {
                const contentEl = document.createElement('div');
                contentEl.className = 'assistant-content';
                contentEl.innerHTML = formatMarkdown(msg.content);
                card.appendChild(contentEl);
            }

            messagesFeed.appendChild(card);
        }
    }

    scrollToBottom();
}

// ============================================================================
// WORKSPACE SCOPE & MODAL
// ============================================================================

function updateWorkspaceDisplay(path) {
    currentWorkspace = path || '/';
    const isRoot = currentWorkspace === '/' || currentWorkspace === '';
    const displayShort = isRoot ? 'Весь ПК' : currentWorkspace.split('/').filter(Boolean).pop() || currentWorkspace;
    const displayFull = isRoot ? 'Весь ПК (Корень /)' : currentWorkspace;

    if (workspacePathEl) workspacePathEl.textContent = displayFull;
    if (topWorkspaceName) topWorkspaceName.textContent = displayShort;
    const inputScopeName = document.getElementById('input-scope-name');
    if (inputScopeName) inputScopeName.textContent = displayShort;

    updateScopeUI(currentWorkspace);

    const session = getActiveSession();
    if (session) {
        session.workspace = currentWorkspace;
        saveSessions();
    }
}

function updateScopeUI(path) {
    const isRoot = !path || path === '/' || path === '';
    if (scopeCardRoot && scopeCardFolder) {
        if (isRoot) {
            scopeCardRoot.classList.add('active');
            scopeCardFolder.classList.remove('active');
            if (scopeFolderDesc) scopeFolderDesc.textContent = 'Ограничить контекст конкретным проектом';
        } else {
            scopeCardRoot.classList.remove('active');
            scopeCardFolder.classList.add('active');
            if (scopeFolderDesc) scopeFolderDesc.textContent = path;
        }
    }
}

window.pickWorkspaceFolder = function() {
    fetch('/api/workspace/pick', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    }).then(r => r.json()).then(res => {
        if (res.success && res.workspace) {
            updateWorkspaceDisplay(res.workspace);
            closeWorkspaceModal();
        }
    }).catch(err => {
        console.error('Folder picker error:', err);
    });
};

window.selectWorkspaceScope = function(path) {
    const target = path || '/';
    fetch('/api/workspace/set', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace: target })
    }).then(r => r.json()).then(res => {
        if (res.success) {
            updateWorkspaceDisplay(res.workspace);
            closeWorkspaceModal();
        }
    }).catch(err => {
        console.error('Failed to set workspace:', err);
    });
};

function openWorkspaceModal() {
    if (inputModalWorkspace) {
        inputModalWorkspace.value = currentWorkspace === '/' ? '' : currentWorkspace;
    }
    if (workspaceModal) {
        workspaceModal.classList.remove('hidden');
        if (inputModalWorkspace) inputModalWorkspace.focus();
    }
}
window.openWorkspaceModal = openWorkspaceModal;

function closeWorkspaceModal() {
    if (workspaceModal) workspaceModal.classList.add('hidden');
}

if (workspacePill) workspacePill.addEventListener('click', openWorkspaceModal);
if (btnTopWorkspace) btnTopWorkspace.addEventListener('click', openWorkspaceModal);
if (btnCloseWorkspace) btnCloseWorkspace.addEventListener('click', closeWorkspaceModal);
if (btnCancelWorkspace) btnCancelWorkspace.addEventListener('click', closeWorkspaceModal);

if (btnSaveWorkspace) {
    btnSaveWorkspace.addEventListener('click', () => {
        const val = inputModalWorkspace.value.trim() || '/';
        selectWorkspaceScope(val);
    });
}

// ============================================================================
// IN-CHAT SUBAGENT RENDERING & MODAL
// ============================================================================

function createSubagentChatCard(subId, role, prompt, status) {
    const card = document.createElement('div');
    card.className = 'subagent-chat-card';
    card.id = `subagent-chat-${subId}`;
    
    const statusClass = status === 'completed' ? 'completed' : (status === 'error' ? 'error' : '');
    const statusLabel = status === 'completed' ? 'Завершено' : (status === 'error' ? 'Ошибка' : 'Выполняется...');

    card.innerHTML = `
        <div class="subagent-chat-info">
            <div class="subagent-chat-header">
                <span class="subagent-chat-role">${escapeHtml(role || 'Субагент')}</span>
                <span class="subagent-chat-badge ${statusClass}" id="subagent-badge-${subId}">${statusLabel}</span>
            </div>
            <div class="subagent-chat-prompt">${escapeHtml(prompt || '')}</div>
        </div>
        <button class="btn-open-subagent" onclick="openSubagentModal('${subId}')">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 3h6v6M10 14L21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></svg>
            <span>Открыть чат</span>
        </button>
    `;
    return card;
}

window.openSubagentModal = function(subagentId) {
    activeModalSubagentId = subagentId;
    const sub = subagentsData[subagentId];

    if (!sub) {
        fetch('/api/subagents')
            .then(r => r.json())
            .then(data => {
                const found = (data.subagents || []).find(s => s.id === subagentId);
                if (found) {
                    subagentsData[subagentId] = found;
                    renderSubagentModalContent(found);
                }
            });
    } else {
        renderSubagentModalContent(sub);
    }

    if (subagentModal) subagentModal.classList.remove('hidden');
};

function renderSubagentModalContent(sub) {
    if (!sub) return;
    if (subagentModalRole) subagentModalRole.textContent = `Субагент: ${sub.role || 'Помощник'}`;
    if (subagentModalPrompt) subagentModalPrompt.textContent = sub.prompt || '';
    
    const isCompleted = sub.status === 'completed';
    const isError = sub.status === 'error';
    if (subagentModalStatus) {
        subagentModalStatus.className = 'subagent-modal-badge ' + (isCompleted ? 'completed' : (isError ? 'error' : ''));
        subagentModalStatus.textContent = isCompleted ? 'Завершено' : (isError ? 'Ошибка' : 'Выполняется');
    }

    if (subagentModalFeed) {
        subagentModalFeed.innerHTML = '';
        if (sub.events && sub.events.length > 0) {
            for (const ev of sub.events) {
                appendSubagentModalEvent(ev);
            }
        } else {
            subagentModalFeed.innerHTML = '<div style="color:var(--text-muted);padding:10px;">Ожидание действий субагента...</div>';
        }
    }
}

function appendSubagentModalEvent(ev) {
    if (!subagentModalFeed) return;
    const item = document.createElement('div');
    item.className = 'subagent-log-step';

    if (ev.type === 'reasoning') {
        item.classList.add('reasoning');
        item.innerHTML = `<strong>Мысли:</strong> ${escapeHtml(ev.delta || ev.full || '')}`;
    } else if (ev.type === 'tool_start') {
        item.classList.add('tool');
        item.innerHTML = `<strong>Инструмент:</strong> <code>${escapeHtml(ev.tool)}</code> ${escapeHtml(JSON.stringify(ev.args || {}))}`;
    } else if (ev.type === 'tool_end') {
        item.classList.add('tool');
        const out = ev.result ? (ev.result.output || ev.result.error || '') : '';
        item.innerHTML = `<strong>Результат (${escapeHtml(ev.tool)}):</strong> <pre style="margin-top:4px;white-space:pre-wrap;">${escapeHtml(out)}</pre>`;
    } else if (ev.type === 'finished') {
        item.classList.add('result');
        item.innerHTML = `<strong>Итог:</strong> ${escapeHtml(ev.result || '')}`;
    } else {
        item.textContent = `[${ev.type}] ${escapeHtml(JSON.stringify(ev))}`;
    }
    subagentModalFeed.appendChild(item);
    subagentModalFeed.scrollTop = subagentModalFeed.scrollHeight;
}

function closeSubagentModal() {
    activeModalSubagentId = null;
    if (subagentModal) subagentModal.classList.add('hidden');
}

if (btnCloseSubagent) btnCloseSubagent.addEventListener('click', closeSubagentModal);
if (btnDismissSubagent) btnDismissSubagent.addEventListener('click', closeSubagentModal);

// ============================================================================
// PROMPT & TEXTAREA
// ============================================================================

function setPrompt(text) {
    promptInput.value = text;
    promptInput.focus();
    adjustTextareaHeight();
}
window.setPrompt = setPrompt;

function adjustTextareaHeight() {
    promptInput.style.height = 'auto';
    promptInput.style.height = Math.min(promptInput.scrollHeight, 180) + 'px';
}
promptInput.addEventListener('input', adjustTextareaHeight);

// Image attachment handling
btnAttach.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', (e) => {
    for (const file of e.target.files) {
        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = (evt) => {
                attachedImages.push(evt.target.result);
                renderImagePreviews();
            };
            reader.readAsDataURL(file);
        }
    }
    fileInput.value = '';
});

// Drag & Drop / Paste images
window.addEventListener('paste', (e) => {
    const items = (e.clipboardData || e.originalEvent.clipboardData).items;
    for (const item of items) {
        if (item.type.indexOf('image') === 0) {
            const blob = item.getAsFile();
            const reader = new FileReader();
            reader.onload = (evt) => {
                attachedImages.push(evt.target.result);
                renderImagePreviews();
            };
            reader.readAsDataURL(blob);
        }
    }
});

function renderImagePreviews() {
    imagePreviewStrip.innerHTML = '';
    attachedImages.forEach((dataUrl, idx) => {
        const chip = document.createElement('div');
        chip.className = 'image-chip';
        chip.innerHTML = `
            <img src="${dataUrl}">
            <button class="image-chip-remove" onclick="removeImage(${idx})">×</button>
        `;
        imagePreviewStrip.appendChild(chip);
    });
}

window.removeImage = function(idx) {
    attachedImages.splice(idx, 1);
    renderImagePreviews();
};

// ============================================================================
// SSE REAL-TIME AGENT CONNECTION
// ============================================================================

function connectSSE() {
    if (eventSource) {
        eventSource.close();
    }
    eventSource = new EventSource('/api/events');

    eventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleAgentEvent(data);
        } catch (e) {
            console.error('SSE JSON parse error:', e);
        }
    };

    eventSource.onerror = () => {
        setTimeout(connectSSE, 3000);
    };
}

function updateStatus(status, text) {
    // Status badge removed from UI — no-op
}

let currentAssistantTurn = null;

function handleAgentEvent(evt) {
    switch (evt.type) {
        case 'init':
            if (evt.workspace) updateWorkspaceDisplay(evt.workspace);
            if (evt.model) modelSelect.value = evt.model;
            if (evt.is_running) {
                setRunningState(true);
            }
            break;

        case 'workspace_updated':
            updateWorkspaceDisplay(evt.workspace);
            break;

        case 'status':
            if (evt.status === 'thinking') {
                updateStatus('thinking', 'Мышление...');
            } else if (evt.status === 'executing') {
                updateStatus('executing', 'Выполнение...');
            } else if (evt.status === 'idle') {
                updateStatus('idle', 'Готов');
                setRunningState(false);
            } else if (evt.status === 'stopped') {
                updateStatus('idle', 'Остановлен');
                setRunningState(false);
            }
            break;

        case 'reasoning':
            ensureAssistantCard();
            appendReasoning(evt.delta);
            if (currentAssistantTurn) {
                currentAssistantTurn.reasoning = (currentAssistantTurn.reasoning || '') + evt.delta;
            }
            break;

        case 'content':
            ensureAssistantCard();
            appendContent(evt.delta);
            if (currentAssistantTurn) {
                currentAssistantTurn.content = (currentAssistantTurn.content || '') + evt.delta;
            }
            break;

        case 'tool_confirmation_required':
            ensureAssistantCard();
            renderToolConfirmation(evt.id, evt.name, evt.args);
            break;

        case 'tool_start':
            ensureAssistantCard();
            if (evt.name === 'spawn_subagent') {
                const subId = (evt.args && evt.args.id) || 'sub_' + Date.now();
                renderSubagentChatStart(subId, evt.args.role, evt.args.prompt);
            } else {
                renderToolStart(evt.id, evt.name, evt.args);
            }
            updateStatus('executing', `${evt.name}`);
            break;

        case 'tool_end':
            if (evt.name === 'spawn_subagent' || (evt.result && evt.result.is_subagent)) {
                const subId = evt.result.subagent_id;
                const subRole = evt.result.subagent_role || 'Субагент';
                const subPrompt = evt.result.subagent_prompt || '';
                subagentsData[subId] = {
                    id: subId,
                    role: subRole,
                    prompt: subPrompt,
                    status: 'running',
                    events: []
                };
                renderSubagentChatStart(subId, subRole, subPrompt);
                if (currentAssistantTurn) {
                    if (!currentAssistantTurn.tools) currentAssistantTurn.tools = [];
                    currentAssistantTurn.tools.push({
                        name: 'spawn_subagent',
                        subagent_id: subId,
                        subagent_role: subRole,
                        subagent_prompt: subPrompt,
                        is_subagent: true
                    });
                }
            } else {
                updateToolEnd(evt.id, evt.name, evt.result);
                if (currentAssistantTurn) {
                    if (!currentAssistantTurn.tools) currentAssistantTurn.tools = [];
                    currentAssistantTurn.tools.push({
                        name: evt.name,
                        success: evt.result.success,
                        output: evt.result.output,
                        error: evt.result.error
                    });
                }
            }
            break;

        case 'subagent_event':
            handleSubagentStreamEvent(evt);
            break;

        case 'task_completed':
            setRunningState(false);
            updateStatus('idle', 'Готов');
            activeAssistantCard = null;
            saveSessions();
            break;

        case 'error':
            ensureAssistantCard();
            appendError(evt.error);
            setRunningState(false);
            updateStatus('idle', 'Ошибка');
            saveSessions();
            break;
    }
}

function renderSubagentChatStart(subId, role, prompt) {
    let existing = document.getElementById(`subagent-chat-${subId}`);
    if (!existing) {
        const card = createSubagentChatCard(subId, role, prompt, 'running');
        activeAssistantCard.appendChild(card);
        scrollToBottom();
    }
}

function handleSubagentStreamEvent(evt) {
    const sId = evt.subagent_id;
    if (!sId) return;

    if (!subagentsData[sId]) {
        subagentsData[sId] = {
            id: sId,
            role: evt.role || 'Субагент',
            prompt: '',
            status: 'running',
            events: []
        };
    }

    subagentsData[sId].events.push(evt);

    if (evt.type === 'finished') {
        subagentsData[sId].status = 'completed';
        const badge = document.getElementById(`subagent-badge-${sId}`);
        if (badge) {
            badge.className = 'subagent-chat-badge completed';
            badge.textContent = 'Завершено';
        }
    } else if (evt.type === 'error') {
        subagentsData[sId].status = 'error';
        const badge = document.getElementById(`subagent-badge-${sId}`);
        if (badge) {
            badge.className = 'subagent-chat-badge error';
            badge.textContent = 'Ошибка';
        }
    }

    if (activeModalSubagentId === sId && subagentModal && !subagentModal.classList.contains('hidden')) {
        appendSubagentModalEvent(evt);
        if (evt.type === 'finished' || evt.type === 'error') {
            const isCompleted = evt.type === 'finished';
            subagentModalStatus.className = 'subagent-modal-badge ' + (isCompleted ? 'completed' : 'error');
            subagentModalStatus.textContent = isCompleted ? 'Завершено' : 'Ошибка';
        }
    }
}

function setRunningState(running) {
    isRunning = running;
    if (running) {
        btnSend.classList.add('hidden');
        btnStop.classList.remove('hidden');
    } else {
        btnSend.classList.remove('hidden');
        btnStop.classList.add('hidden');
    }
}

function ensureAssistantCard() {
    if (!activeAssistantCard) {
        welcomeScreen.classList.add('hidden');
        activeAssistantCard = document.createElement('div');
        activeAssistantCard.className = 'message-card assistant';

        activeReasoningBox = null;
        activeContentEl = document.createElement('div');
        activeContentEl.className = 'assistant-content';
        activeAssistantCard.appendChild(activeContentEl);

        messagesFeed.appendChild(activeAssistantCard);
        scrollToBottom();

        const session = getActiveSession();
        if (session) {
            currentAssistantTurn = {
                role: 'assistant',
                content: '',
                reasoning: '',
                tools: []
            };
            session.messages.push(currentAssistantTurn);
        }
    }
}

function appendReasoning(text) {
    if (!activeReasoningBox) {
        activeReasoningBox = document.createElement('div');
        activeReasoningBox.className = 'reasoning-box';
        activeReasoningBox.innerHTML = `
            <div class="reasoning-header" onclick="toggleReasoning(this)">
                <div class="reasoning-title-wrap">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a8 8 0 0 0-8 8c0 3.4 2.1 6.3 5.1 7.4.3.1.5.4.5.7v1.9c0 .6.4 1 1 1h2.8c.6 0 1-.4 1-1v-1.9c0-.3.2-.6.5-.7C17.9 16.3 20 13.4 20 10a8 8 0 0 0-8-8z"/></svg>
                    <span>Рассуждения (DeepSeek R1)</span>
                </div>
                <span class="reasoning-toggle-icon">▾</span>
            </div>
            <div class="reasoning-body"></div>
        `;
        activeAssistantCard.insertBefore(activeReasoningBox, activeContentEl);
    }
    const body = activeReasoningBox.querySelector('.reasoning-body');
    body.textContent += text;
    scrollToBottom();
}

window.toggleReasoning = function(header) {
    const body = header.nextElementSibling;
    body.classList.toggle('collapsed');
    header.querySelector('.reasoning-toggle-icon').textContent = body.classList.contains('collapsed') ? '▸' : '▾';
};

function appendContent(text) {
    if (activeContentEl) {
        const currentRaw = activeContentEl.getAttribute('data-raw') || '';
        const newRaw = currentRaw + text;
        activeContentEl.setAttribute('data-raw', newRaw);
        activeContentEl.innerHTML = formatMarkdown(newRaw);
        scrollToBottom();
    }
}

function appendError(msg) {
    const errDiv = document.createElement('div');
    errDiv.style.color = 'var(--accent-danger)';
    errDiv.style.padding = '8px 10px';
    errDiv.style.background = 'rgba(239, 68, 68, 0.1)';
    errDiv.style.border = '1px solid rgba(239, 68, 68, 0.25)';
    errDiv.style.borderRadius = '6px';
    errDiv.style.marginTop = '6px';
    errDiv.style.fontSize = '12px';
    errDiv.style.fontFamily = 'var(--font-mono)';
    errDiv.textContent = msg;
    activeAssistantCard.appendChild(errDiv);
    scrollToBottom();
}

function renderToolConfirmation(id, name, args) {
    const confirmBar = document.createElement('div');
    confirmBar.className = 'tool-confirm-bar';
    confirmBar.id = `tool-confirm-${id}`;
    confirmBar.innerHTML = `
        <div>
            <strong>Выполнить инструмент:</strong> <code>${name}</code>
        </div>
        <div class="tool-confirm-actions">
            <button class="btn btn-secondary btn-sm" onclick="confirmTool('${id}', false)">Отклонить</button>
            <button class="btn btn-success btn-sm" onclick="confirmTool('${id}', true)">Разрешить</button>
        </div>
    `;
    activeAssistantCard.appendChild(confirmBar);
    scrollToBottom();
}

window.confirmTool = function(id, approved) {
    const bar = document.getElementById(`tool-confirm-${id}`);
    if (bar) bar.remove();
    fetch('/api/tools/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, approved })
    });
};

function renderToolStart(id, name, args) {
    const card = document.createElement('div');
    card.className = 'tool-card';
    card.id = `tool-card-${id}`;

    let argSummary = '';
    if (name === 'run_command') argSummary = args.command || '';
    else if (name === 'read_file' || name === 'write_file' || name === 'edit_file') argSummary = args.path || '';
    else if (name === 'web_fetch') argSummary = args.url || '';

    card.innerHTML = `
        <div class="tool-header">
            <span class="tool-name-badge">
                <span class="tool-icon-glyph">›_</span>
                ${name} 
                <span style="color:var(--text-muted);font-weight:normal;">${escapeHtml(argSummary)}</span>
            </span>
            <span class="tool-status-tag running">выполняется...</span>
        </div>
        <div class="tool-body" style="display:none;"></div>
    `;
    activeAssistantCard.appendChild(card);
    scrollToBottom();
}

function updateToolEnd(id, name, result) {
    const card = document.getElementById(`tool-card-${id}`);
    if (card) {
        const tag = card.querySelector('.tool-status-tag');
        const body = card.querySelector('.tool-body');
        body.style.display = 'block';

        if (result.success) {
            tag.className = 'tool-status-tag success';
            tag.textContent = 'успешно';
            body.textContent = result.output || '(Готово)';
        } else {
            tag.className = 'tool-status-tag error';
            tag.textContent = 'ошибка';
            body.textContent = result.error || result.output || 'Execution failed';
        }
        scrollToBottom();
    }
}

function formatMarkdown(raw) {
    if (!raw) return '';
    // Strip tool_call and internal JSON invocation blocks so assistant communicates in normal text
    let clean = raw
        .replace(/```tool_call[\s\S]*?```/gi, '')
        .replace(/```json\s*\{\s*"tool_call"[\s\S]*?```/gi, '')
        .replace(/\{\s*"tool_call"\s*:\s*\{[\s\S]*?\}\s*\}/gi, '')
        .trim();

    if (!clean && /tool_call/i.test(raw)) {
        return '<span class="action-narrative">Выполняю действия...</span>';
    }

    let html = escapeHtml(clean);

    // Code blocks with Antigravity header & copy button
    html = html.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
        const langLabel = lang || 'code';
        return `
            <div class="code-block-wrapper">
                <div class="code-block-header">
                    <span class="code-block-lang">${escapeHtml(langLabel)}</span>
                    <button class="copy-code-btn" onclick="copyCode(this)" title="Копировать">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                        <span>Копировать</span>
                    </button>
                </div>
                <pre><code>${code}</code></pre>
            </div>
        `;
    });

    // Headers
    html = html.replace(/^### (.*$)/gim, '<h3 class="md-h3">$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2 class="md-h2">$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1 class="md-h1">$1</h1>');

    // Inline elements
    html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // Lists
    html = html.replace(/^\s*[-*]\s+(.*)$/gim, '<div class="md-list-item">• $1</div>');
    html = html.replace(/^\s*(\d+)\.\s+(.*)$/gim, '<div class="md-list-item"><span class="list-num">$1.</span> $2</div>');

    // Paragraphs
    html = html.replace(/\n\n/g, '<div class="md-para-gap"></div>');
    html = html.replace(/\n/g, '<br>');
    return html;
}

window.copyCode = function(button) {
    const codeEl = button.closest('.code-block-wrapper').querySelector('code');
    if (!codeEl) return;
    navigator.clipboard.writeText(codeEl.innerText).then(() => {
        const span = button.querySelector('span');
        const orig = span.textContent;
        span.textContent = 'Скопировано!';
        button.classList.add('copied');
        setTimeout(() => {
            span.textContent = orig;
            button.classList.remove('copied');
        }, 2000);
    });
};

function escapeHtml(str) {
    return (str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// ============================================================================
// PROMPT SUBMISSION
// ============================================================================

btnSend.addEventListener('click', submitPrompt);
promptInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        submitPrompt();
    }
});

function submitPrompt() {
    const text = promptInput.value.trim();
    if (!text && attachedImages.length === 0) return;
    if (isRunning) return;

    welcomeScreen.classList.add('hidden');

    const session = getActiveSession();
    if (session) {
        if (session.title === 'Новый чат' && text) {
            session.title = text.length > 28 ? text.slice(0, 28) + '...' : text;
            renderSessionsList();
        }
        session.messages.push({
            role: 'user',
            content: text,
            images: [...attachedImages]
        });
        saveSessions();
    }

    // Add user bubble
    const userCard = document.createElement('div');
    userCard.className = 'message-card user';
    let imagesHtml = '';
    if (attachedImages.length > 0) {
        imagesHtml = '<div class="user-bubble-images">' + 
            attachedImages.map(img => `<img class="user-img-thumb" src="${img}">`).join('') + 
            '</div>';
    }
    userCard.innerHTML = `<div class="user-bubble">${escapeHtml(text)}${imagesHtml}</div>`;
    messagesFeed.appendChild(userCard);

    activeAssistantCard = null;
    currentAssistantTurn = null;
    setRunningState(true);
    updateStatus('thinking', 'Планирование...');

    const payload = {
        prompt: text,
        images: [...attachedImages],
        model: modelSelect.value,
        workspace: currentWorkspace
    };

    attachedImages = [];
    renderImagePreviews();
    promptInput.value = '';
    adjustTextareaHeight();
    scrollToBottom();

    fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    }).catch(err => {
        appendError('Ошибка отправки: ' + err);
        setRunningState(false);
    });
}

// Stop Agent
btnStop.addEventListener('click', () => {
    fetch('/api/stop', { method: 'POST' });
});

// ============================================================================
// SETTINGS MODAL
// ============================================================================

btnOpenSettings.addEventListener('click', () => {
    fetch('/api/settings')
        .then(r => r.json())
        .then(cfg => {
            settingApiUrl.value = cfg.api_base_url || '';
            settingApiKey.value = cfg.api_key || '';
            settingWorkspace.value = cfg.workspace || '';
            settingMaxSteps.value = cfg.max_steps || 30;
            settingSystemPrompt.value = cfg.system_prompt || '';
            settingAutoAccept.checked = !!cfg.auto_accept_tools;
            settingsModal.classList.remove('hidden');
        })
        .catch(err => {
            console.error('Failed to load settings:', err);
            settingsModal.classList.remove('hidden');
        });
});

[btnCloseSettings, btnCancelSettings].forEach(btn => {
    if (btn) {
        btn.addEventListener('click', () => settingsModal.classList.add('hidden'));
    }
});

// Close modals on Escape
window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        if (settingsModal && !settingsModal.classList.contains('hidden')) settingsModal.classList.add('hidden');
        if (workspaceModal && !workspaceModal.classList.contains('hidden')) workspaceModal.classList.add('hidden');
        if (subagentModal && !subagentModal.classList.contains('hidden')) closeSubagentModal();
    }
});

[settingsModal, workspaceModal, subagentModal].forEach(modal => {
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.add('hidden');
                if (modal === subagentModal) activeModalSubagentId = null;
            }
        });
    }
});

btnSaveSettings.addEventListener('click', () => {
    const updates = {
        api_base_url: settingApiUrl.value.trim(),
        api_key: settingApiKey.value.trim(),
        workspace: settingWorkspace.value.trim(),
        max_steps: parseInt(settingMaxSteps.value, 10) || 30,
        system_prompt: settingSystemPrompt.value.trim(),
        auto_accept_tools: settingAutoAccept.checked
    };
    fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
    }).then(r => r.json()).then(data => {
        settingsModal.classList.add('hidden');
        if (updates.workspace) {
            updateWorkspaceDisplay(updates.workspace);
        }
    }).catch(err => {
        alert('Ошибка при сохранении настроек: ' + err);
    });
});

// Load Models dynamically from API
function loadModelsList() {
    fetch('/api/models')
        .then(r => r.json())
        .then(data => {
            if (data.models && data.models.length > 0) {
                const currentVal = modelSelect.value;
                const existingGroup = {};
                for (const m of data.models) {
                    const grp = m.group || 'Модели';
                    if (!existingGroup[grp]) existingGroup[grp] = [];
                    existingGroup[grp].push(m);
                }
                let optionsHtml = '';
                for (const [groupName, groupModels] of Object.entries(existingGroup)) {
                    optionsHtml += `<optgroup label="${escapeHtml(groupName)}">`;
                    for (const mod of groupModels) {
                        optionsHtml += `<option value="${escapeHtml(mod.id)}">${escapeHtml(mod.name || mod.id)}</option>`;
                    }
                    optionsHtml += `</optgroup>`;
                }
                modelSelect.innerHTML = optionsHtml;
                if (currentVal) modelSelect.value = currentVal;
            }
        })
        .catch(() => {});
}

// Initialize on Load
window.addEventListener('DOMContentLoaded', () => {
    initSessions();
    connectSSE();
    loadModelsList();
});

