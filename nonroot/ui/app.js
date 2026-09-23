// NonRoot Front-End Application Logic (OpenCode 1:1)

let eventSource = null;
let isRunning = false;
let attachedImages = [];
let activeAssistantCard = null;
let activeReasoningBox = null;
let activeContentEl = null;

const chatContainer = document.getElementById('chat-container');
const messagesFeed = document.getElementById('messages-feed');
const welcomeScreen = document.getElementById('welcome-screen');
const promptInput = document.getElementById('prompt-input');
const btnSend = document.getElementById('btn-send-prompt');
const btnStop = document.getElementById('btn-stop-agent');
const btnAutoAccept = document.getElementById('btn-auto-accept');
const modelSelect = document.getElementById('model-select');
const statusBadge = document.getElementById('agent-status-badge');
const statusText = document.getElementById('agent-status-text');
const workspacePathEl = document.getElementById('workspace-path');
const subagentsListEl = document.getElementById('subagents-list');
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

function setPrompt(text) {
    promptInput.value = text;
    promptInput.focus();
    adjustTextareaHeight();
}

function adjustTextareaHeight() {
    promptInput.style.height = 'auto';
    promptInput.style.height = Math.min(promptInput.scrollHeight, 200) + 'px';
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

function removeImage(idx) {
    attachedImages.splice(idx, 1);
    renderImagePreviews();
}

// Auto-Accept toggle
let autoAcceptEnabled = true;
btnAutoAccept.addEventListener('click', () => {
    autoAcceptEnabled = !autoAcceptEnabled;
    updateAutoAcceptUI();
    fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auto_accept_tools: autoAcceptEnabled })
    });
});

function updateAutoAcceptUI() {
    if (autoAcceptEnabled) {
        btnAutoAccept.classList.add('active');
        btnAutoAccept.querySelector('.pill-label').textContent = 'Auto-Accept: ON';
    } else {
        btnAutoAccept.classList.remove('active');
        btnAutoAccept.querySelector('.pill-label').textContent = 'Auto-Accept: OFF';
    }
}

// SSE Connection
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
            console.error('SSE JSON error:', e);
        }
    };

    eventSource.onerror = () => {
        setTimeout(connectSSE, 3000);
    };
}

function updateStatus(status, text) {
    statusBadge.className = 'status-badge ' + status;
    statusText.textContent = text;
}

function handleAgentEvent(evt) {
    switch (evt.type) {
        case 'init':
            workspacePathEl.textContent = evt.workspace || '...';
            autoAcceptEnabled = !!evt.auto_accept;
            updateAutoAcceptUI();
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
            break;

        case 'content':
            ensureAssistantCard();
            appendContent(evt.delta);
            break;

        case 'tool_confirmation_required':
            ensureAssistantCard();
            renderToolConfirmation(evt.id, evt.name, evt.args);
            break;

        case 'tool_start':
            ensureAssistantCard();
            renderToolStart(evt.id, evt.name, evt.args);
            updateStatus('executing', `Инструмент: ${evt.name}`);
            break;

        case 'tool_end':
            updateToolEnd(evt.id, evt.name, evt.result);
            break;

        case 'subagent_event':
            refreshSubagents();
            break;

        case 'task_completed':
            setRunningState(false);
            updateStatus('idle', 'Завершено');
            activeAssistantCard = null;
            break;

        case 'error':
            ensureAssistantCard();
            appendError(evt.error);
            setRunningState(false);
            updateStatus('idle', 'Ошибка');
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
    }
}

function appendReasoning(text) {
    if (!activeReasoningBox) {
        activeReasoningBox = document.createElement('div');
        activeReasoningBox.className = 'reasoning-box';
        activeReasoningBox.innerHTML = `
            <div class="reasoning-header" onclick="toggleReasoning(this)">
                <span>🧠 Процесс рассуждений (DeepSeek R1)</span>
                <span class="reasoning-toggle-icon">▼</span>
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
    header.querySelector('.reasoning-toggle-icon').textContent = body.classList.contains('collapsed') ? '▲' : '▼';
};

function appendContent(text) {
    if (activeContentEl) {
        activeContentEl.innerHTML = formatMarkdown(activeContentEl.getAttribute('data-raw') || '' + text);
        activeContentEl.setAttribute('data-raw', (activeContentEl.getAttribute('data-raw') || '') + text);
        scrollToBottom();
    }
}

function appendError(msg) {
    const errDiv = document.createElement('div');
    errDiv.style.color = 'var(--accent-danger)';
    errDiv.style.padding = '8px 12px';
    errDiv.style.background = 'rgba(239, 68, 68, 0.1)';
    errDiv.style.border = '1px solid rgba(239, 68, 68, 0.3)';
    errDiv.style.borderRadius = '6px';
    errDiv.style.marginTop = '8px';
    errDiv.textContent = '❌ ' + msg;
    activeAssistantCard.appendChild(errDiv);
    scrollToBottom();
}

function renderToolConfirmation(id, name, args) {
    const confirmBar = document.createElement('div');
    confirmBar.className = 'tool-confirm-bar';
    confirmBar.id = `tool-confirm-${id}`;
    confirmBar.innerHTML = `
        <div>
            <strong>Запрос на выполнение:</strong> <code>${name}</code>
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
            <span class="tool-name-badge">${name} <span style="color:var(--text-muted);font-weight:normal;">${escapeHtml(argSummary)}</span></span>
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
    // Basic clean markdown converter
    let html = escapeHtml(raw);
    html = html.replace(/```([a-z]*)
([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    html = html.replace(/

/g, '<p></p>');
    html = html.replace(/
/g, '<br>');
    return html;
}

function escapeHtml(str) {
    return (str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// Send Prompt
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

    // Add user bubble
    const userCard = document.createElement('div');
    userCard.className = 'message-card user';
    let imagesHtml = '';
    if (attachedImages.length > 0) {
        imagesHtml = '<div class="user-bubble-images">' + attachedImages.map(img => `<img class="user-img-thumb" src="${img}">`).join('') + '</div>';
    }
    userCard.innerHTML = `<div class="user-bubble">${escapeHtml(text)}${imagesHtml}</div>`;
    messagesFeed.appendChild(userCard);

    activeAssistantCard = null;
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
        appendError('Failed to send task: ' + err);
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
            <div style="font-size:11px;color:var(--text-muted);">${escapeHtml(s.prompt.slice(0, 45))}...</div>
        </div>
    `).join('');
}

function refreshSubagents() {
    fetch('/api/subagents')
        .then(r => r.json())
        .then(data => renderSubagents(data.subagents));
}

// New Chat button
document.getElementById('btn-new-chat').addEventListener('click', () => {
    messagesFeed.innerHTML = '';
    welcomeScreen.classList.remove('hidden');
    activeAssistantCard = null;
});

// Settings Modal
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
        });
});

[btnCloseSettings, btnCancelSettings].forEach(btn => {
    btn.addEventListener('click', () => settingsModal.classList.add('hidden'));
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
    }).then(() => {
        settingsModal.classList.add('hidden');
        autoAcceptEnabled = updates.auto_accept_tools;
        updateAutoAcceptUI();
        workspacePathEl.textContent = updates.workspace;
    });
});

// Initialize on Load
window.addEventListener('DOMContentLoaded', () => {
    connectSSE();
});
