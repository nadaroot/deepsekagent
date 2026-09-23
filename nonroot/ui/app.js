// NonRoot Autonomous AI Agent - Front-End Logic (OpenCode 1:1)

let eventSource = null;
let isRunning = false;
let attachedImages = [];
let activeAssistantCard = null;
let activeReasoningBox = null;
let activeContentEl = null;

// Sessions State
let sessions = [];
let currentSessionId = null;

// DOM Elements
const chatContainer = document.getElementById('chat-container');
const messagesFeed = document.getElementById('messages-feed');
const welcomeScreen = document.getElementById('welcome-screen');
const promptInput = document.getElementById('prompt-input');
const btnSend = document.getElementById('btn-send-prompt');
const btnStop = document.getElementById('btn-stop-agent');
const modelSelect = document.getElementById('model-select');
const statusBadge = document.getElementById('agent-status-badge');
const statusText = document.getElementById('agent-status-text');
const workspacePathEl = document.getElementById('workspace-path');
const subagentsListEl = document.getElementById('subagents-list');
const sessionsListEl = document.getElementById('sessions-list');
const btnNewChat = document.getElementById('btn-new-chat');
const btnToggleRightSidebar = document.getElementById('btn-toggle-right-sidebar');
const sidebarRight = document.getElementById('sidebar-right');
const fileInput = document.getElementById('file-input');
const btnAttach = document.getElementById('btn-attach-image');
const imagePreviewStrip = document.getElementById('image-preview-strip');

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
        messages: [] // Array of { role, content, images, reasoning, tools: [] }
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

function renderSessionsList() {
    if (!sessionsListEl) return;
    if (sessions.length === 0) {
        sessionsListEl.innerHTML = '<div class="empty-sessions">Нет сохраненных чатов</div>';
        return;
    }

    sessionsListEl.innerHTML = sessions.map(s => {
        const isActive = s.id === currentSessionId;
        const timeStr = formatSessionTime(s.createdAt);
        return `
            <div class="session-item ${isActive ? 'active' : ''}" onclick="switchSession('${s.id}')">
                <div class="session-info">
                    <span class="session-title">${escapeHtml(s.title || 'Чат')}</span>
                    <span class="session-time">${timeStr}</span>
                </div>
                <button class="session-delete" title="Удалить чат" onclick="deleteSession('${s.id}', event)">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
            </div>
        `;
    }).join('');
}

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

if (btnToggleRightSidebar && sidebarRight) {
    btnToggleRightSidebar.addEventListener('click', () => {
        sidebarRight.classList.toggle('collapsed');
    });
}

function loadActiveSession() {
    messagesFeed.innerHTML = '';
    activeAssistantCard = null;
    activeReasoningBox = null;
    activeContentEl = null;

    const session = getActiveSession();
    if (!session || !session.messages || session.messages.length === 0) {
        welcomeScreen.classList.remove('hidden');
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
    if (status === 'idle' || !text || text === 'Готов') {
        statusBadge.classList.add('hidden');
    } else {
        statusBadge.classList.remove('hidden');
        statusBadge.className = 'status-badge ' + status;
        statusText.textContent = text;
    }
}


let currentAssistantTurn = null;

function handleAgentEvent(evt) {
    switch (evt.type) {
        case 'init':
            workspacePathEl.textContent = evt.workspace || '...';
            if (evt.model) modelSelect.value = evt.model;
            if (evt.subagents) renderSubagents(evt.subagents);
            if (evt.is_running) {
                setRunningState(true);
            }
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
            renderToolStart(evt.id, evt.name, evt.args);
            updateStatus('executing', `${evt.name}`);
            break;

        case 'tool_end':
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
            break;

        case 'subagent_event':
            refreshSubagents();
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
    else if (name === 'spawn_subagent') argSummary = `${args.role}: ${args.prompt}`;

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
    let html = escapeHtml(raw);
    html = html.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    html = html.replace(/\n\n/g, '<p></p>');
    html = html.replace(/\n/g, '<br>');
    return html;
}

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
        model: modelSelect.value
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

// Subagents rendering
function renderSubagents(subagents) {
    if (!subagents || subagents.length === 0) {
        subagentsListEl.innerHTML = '<div class="empty-subagents">Нет активных субагентов</div>';
        return;
    }
    subagentsListEl.innerHTML = subagents.map(s => `
        <div class="subagent-item">
            <div class="subagent-header">
                <span class="subagent-role">${escapeHtml(s.role)}</span>
                <span class="subagent-status ${s.status}">${s.status}</span>
            </div>
            <div style="font-size:11px;color:var(--text-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(s.prompt)}</div>
        </div>
    `).join('');
}

function refreshSubagents() {
    fetch('/api/subagents')
        .then(r => r.json())
        .then(data => renderSubagents(data.subagents))
        .catch(() => {});
}

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

// Close modal on Escape or background click
window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !settingsModal.classList.contains('hidden')) {
        settingsModal.classList.add('hidden');
    }
});

settingsModal.addEventListener('click', (e) => {
    if (e.target === settingsModal) {
        settingsModal.classList.add('hidden');
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
            workspacePathEl.textContent = updates.workspace;
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
