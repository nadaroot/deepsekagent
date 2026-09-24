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
const settingWorkspace = document.getElementById('setting-workspace');
const settingMaxSteps = document.getElementById('setting-max-steps');
const settingSystemPrompt = document.getElementById('setting-system-prompt');
const settingAutoAccept = document.getElementById('setting-auto-accept');

// Browser Sidepanel & AI Cursor Elements
const browserSidepanel = document.getElementById('browser-sidepanel');
const btnToggleBrowser = document.getElementById('btn-toggle-browser');
const browserPulseDot = document.getElementById('browser-pulse-dot');
const browserBtnBack = document.getElementById('browser-btn-back');
const browserBtnForward = document.getElementById('browser-btn-forward');
const browserBtnReload = document.getElementById('browser-btn-reload');
const browserUrlInput = document.getElementById('browser-url-input');
const browserBtnGo = document.getElementById('browser-btn-go');
const browserAiBadge = document.getElementById('browser-ai-badge');
const browserAiStatusText = document.getElementById('browser-ai-status-text');
const browserBtnClose = document.getElementById('browser-btn-close');
const browserViewportWrapper = document.getElementById('browser-viewport-wrapper');
const browserViewportCanvas = document.getElementById('browser-viewport-canvas');
const browserScreenImg = document.getElementById('browser-screen-img');
const browserLoadingOverlay = document.getElementById('browser-loading-overlay');
const aiCursor = document.getElementById('ai-cursor');
const aiCursorBadge = document.getElementById('ai-cursor-badge');
const aiCursorLabel = document.getElementById('ai-cursor-label');
const aiCursorRipple = document.getElementById('ai-cursor-ripple');
const browserFooterTitle = document.getElementById('browser-footer-title');
const btnBrowserClone = document.getElementById('btn-browser-clone');
const btnBrowserInspectChat = document.getElementById('btn-browser-inspect-chat');

// Monotonic run generation counter to discard stale streaming events after stop or rollback
let currentRunGeneration = 0;

// ============================================================================
// CHAT SESSIONS & STORAGE
// ============================================================================

function initSessions() {
    try {
        const stored = localStorage.getItem('nonroot_sessions');
        if (stored) {
            const parsed = JSON.parse(stored);
            if (Array.isArray(parsed)) {
                sessions = parsed.filter(s => s && typeof s === 'object' && s.id);
            }
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

// Track which workspace groups are collapsed, persisted in localStorage
const COLLAPSED_GROUPS_KEY = 'nonroot_collapsed_groups';
let collapsedGroups = new Set();
try {
    const saved = localStorage.getItem(COLLAPSED_GROUPS_KEY);
    if (saved) collapsedGroups = new Set(JSON.parse(saved));
} catch (_) {}

function getWorkspaceGroupName(workspace) {
    if (!workspace || workspace === '/' || workspace === 'whole_machine') return 'Весь ПК';
    try {
        const parts = workspace.replace(/\/$/, '').split('/');
        return parts[parts.length - 1] || workspace;
    } catch (e) { return workspace; }
}

function safeGroupId(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = ((hash << 5) - hash) + str.charCodeAt(i);
        hash |= 0;
    }
    return 'grp_' + Math.abs(hash).toString(36) + '_' + str.length;
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
        const groupId = safeGroupId(workspace);
        const encodedWs = encodeURIComponent(workspace);

        html += `<div class="session-group ${hasActive ? 'has-active' : ''}" id="${groupId}">`;
        html += `<div class="session-group-header" onclick="toggleGroupEncoded('${encodedWs}')">
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
                        <button class="session-delete" title="Удалить чат" onclick="deleteSession('${s.id}', event)">
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

window.toggleGroupEncoded = function(encodedWs) {
    try {
        const workspace = decodeURIComponent(encodedWs);
        if (collapsedGroups.has(workspace)) {
            collapsedGroups.delete(workspace);
        } else {
            collapsedGroups.add(workspace);
        }
        try {
            localStorage.setItem(COLLAPSED_GROUPS_KEY, JSON.stringify([...collapsedGroups]));
        } catch (_) {}
        renderSessionsList();
    } catch (e) {
        console.error('toggleGroup error:', e);
    }
};

window.toggleGroup = function(groupId, workspace) {
    if (collapsedGroups.has(workspace)) {
        collapsedGroups.delete(workspace);
    } else {
        collapsedGroups.add(workspace);
    }
    try {
        localStorage.setItem(COLLAPSED_GROUPS_KEY, JSON.stringify([...collapsedGroups]));
    } catch (_) {}
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
    
    if (!confirm('Вы уверены, что хотите удалить этот чат?')) {
        return;
    }
    
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
    toggleBrowserSidepanel(false);
    if (btnToggleBrowser) btnToggleBrowser.classList.add('hidden');
}

if (btnNewChat) {
    btnNewChat.addEventListener('click', createNewChat);
}

window.copyMessageText = function(btn, idx) {
    const session = getActiveSession();
    let text = '';
    if (session && session.messages && session.messages[idx]) {
        text = session.messages[idx].content || '';
    } else if (btn && btn.closest('.user-bubble-wrapper')) {
        const bubble = btn.closest('.user-bubble-wrapper').querySelector('.user-bubble');
        if (bubble) text = bubble.innerText;
    }
    if (!text && text !== '') return;

    const onSuccess = () => {
        const origHtml = btn.innerHTML;
        btn.classList.add('copied');
        btn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`;
        btn.title = "Скопировано!";
        setTimeout(() => {
            btn.classList.remove('copied');
            btn.innerHTML = origHtml;
            btn.title = "Скопировать текст";
        }, 1500);
    };

    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(onSuccess).catch(() => {
            fallbackCopyText(text, onSuccess);
        });
    } else {
        fallbackCopyText(text, onSuccess);
    }
};

function fallbackCopyText(text, cb) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    ta.style.top = '-9999px';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try {
        document.execCommand('copy');
        if (cb) cb();
    } catch (e) {}
    document.body.removeChild(ta);
}

window.rollbackToMessage = function(msgIndex) {
    if (!confirm('Откатить диалог и файлы до этого действия? Сообщение вернется в поле ввода, а созданные или измененные файлы будут возвращены к прежнему состоянию.')) {
        return;
    }
    currentRunGeneration++;
    if (isRunning) {
        fetch('/api/stop', { method: 'POST' }).catch(() => {});
        setRunningState(false);
    }

    const session = getActiveSession();
    const userTurnIndex = session && session.messages ? 
        session.messages.slice(0, msgIndex).filter(m => m.role === 'user').length : 
        Math.floor(msgIndex / 2);

    // Inform backend to truncate agent messages and rollback files
    fetch('/api/chat/rollback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ index: msgIndex, user_turn: userTurnIndex })
    }).then(r => r.json()).then(data => {
        if (data.restored_files && data.restored_files.length > 0) {
            updateStatus('idle', `Откат: файлов восстановлено/удалено: ${data.restored_files.length}`);
        } else {
            updateStatus('idle', 'Откат завершен');
        }
    }).catch(() => {});

    currentAssistantTurn = null;
    activeAssistantCard = null;
    activeReasoningBox = null;
    activeContentEl = null;

    const session = getActiveSession();
    if (!session || !session.messages || msgIndex < 0 || msgIndex >= session.messages.length) return;

    const targetMsg = session.messages[msgIndex];
    if (targetMsg) {
        promptInput.value = targetMsg.content || '';
        if (targetMsg.images && Array.isArray(targetMsg.images)) {
            attachedImages = [...targetMsg.images];
            renderImagePreviews();
        }
        adjustTextareaHeight();
        promptInput.focus();
    }

    // Truncate messages from this user message onwards
    session.messages = session.messages.slice(0, msgIndex);
    saveSessions();
    loadActiveSession();
};

function loadActiveSession() {
    messagesFeed.innerHTML = '';
    activeAssistantCard = null;
    activeReasoningBox = null;
    activeContentEl = null;

    const session = getActiveSession();
    if (!session || !session.messages || session.messages.length === 0) {
        welcomeScreen.classList.remove('hidden');
        if (session && session.workspace) {
            currentWorkspace = session.workspace;
        }
        updateWorkspaceDisplay(currentWorkspace, false);
        return;
    }

    welcomeScreen.classList.add('hidden');
    if (session && session.workspace) {
        currentWorkspace = session.workspace;
        updateWorkspaceDisplay(currentWorkspace, false);
    }

    session.messages.forEach((msg, idx) => {
        if (msg.role === 'user') {
            const userCard = document.createElement('div');
            userCard.className = 'message-card user';
            let imagesHtml = '';
            if (msg.images && msg.images.length > 0) {
                imagesHtml = '<div class="user-bubble-images">' + 
                    msg.images.map(img => `<img class="user-img-thumb" src="${img}">`).join('') + 
                    '</div>';
            }
            userCard.innerHTML = `
                <div class="user-bubble-wrapper">
                    <div class="user-msg-actions">
                        <button class="btn-msg-action btn-msg-rollback" type="button" title="Откатить до этого сообщения" onclick="rollbackToMessage(${idx})">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M3 10h10a5 5 0 0 1 5 5v2"/><polyline points="8 5 3 10 8 15"/></svg>
                        </button>
                        <button class="btn-msg-action btn-msg-copy" type="button" title="Скопировать текст" onclick="copyMessageText(this, ${idx})">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                        </button>
                    </div>
                    <div class="user-bubble">${escapeHtml(msg.content)}${imagesHtml}</div>
                </div>
            `;
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
    });

    // Check if current session has any browser activity
    let hasBrowserActivity = false;
    if (session && session.messages && Array.isArray(session.messages)) {
        for (const msg of session.messages) {
            if (msg.tools && Array.isArray(msg.tools)) {
                if (msg.tools.some(t => t.name && t.name.startsWith('browser_'))) {
                    hasBrowserActivity = true;
                    break;
                }
            }
        }
    }

    if (hasBrowserActivity) {
        if (btnToggleBrowser) btnToggleBrowser.classList.remove('hidden');
        toggleBrowserSidepanel(true);
    } else {
        if (btnToggleBrowser) btnToggleBrowser.classList.add('hidden');
        toggleBrowserSidepanel(false);
    }

    scrollToBottom();
}

// ============================================================================
// WORKSPACE SCOPE & MODAL
// ============================================================================

function updateWorkspaceDisplay(path, saveToSession = true) {
    currentWorkspace = path || '/';
    const isRoot = currentWorkspace === '/' || currentWorkspace === '';
    const displayShort = isRoot ? 'Весь ПК' : currentWorkspace.split('/').filter(Boolean).pop() || currentWorkspace;
    const displayFull = isRoot ? 'Весь ПК (Корень /)' : currentWorkspace;

    if (workspacePathEl) workspacePathEl.textContent = displayFull;
    if (topWorkspaceName) topWorkspaceName.textContent = displayShort;
    const inputScopeName = document.getElementById('input-scope-name');
    if (inputScopeName) inputScopeName.textContent = displayShort;

    updateScopeUI(currentWorkspace);

    if (saveToSession) {
        const session = getActiveSession();
        if (session) {
            session.workspace = currentWorkspace;
            saveSessions();
            renderSessionsList();
        }
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

function triggerFolderButtonAnimation(targetEl) {
    const targets = [];
    if (targetEl && targetEl instanceof HTMLElement) {
        targets.push(targetEl);
    }
    const folderCard = document.getElementById('scope-card-folder');
    if (folderCard && !targets.includes(folderCard)) targets.push(folderCard);
    const sidebarBtn = document.getElementById('btn-sidebar-pick-folder');
    if (sidebarBtn && !targets.includes(sidebarBtn)) targets.push(sidebarBtn);

    targets.forEach(t => {
        t.classList.remove('btn-anim-click');
        void t.offsetWidth;
        t.classList.add('btn-anim-click');
        setTimeout(() => {
            t.classList.remove('btn-anim-click');
        }, 360);
    });
}

window.onNativeFolderPicked = function(data) {
    const ws = (typeof data === 'string') ? data : (data && data.workspace);
    if (ws) {
        selectWorkspaceScope(ws);
    }
};

window.pickWorkspaceFolder = function(triggerEl) {
    triggerFolderButtonAnimation(triggerEl);

    // Instant native macOS Cocoa dialog via WebKit bridge (0ms delay)
    if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.nativePickFolder) {
        try {
            window.webkit.messageHandlers.nativePickFolder.postMessage({});
            return;
        } catch (e) {
            console.warn('Native folder bridge fallback:', e);
        }
    }

    // Fallback to server API
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
    hideModelPickerPopover();
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

if (workspacePill) {
    workspacePill.addEventListener('click', openWorkspaceModal);
    workspacePill.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            openWorkspaceModal();
        }
    });
}
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
    hideModelPickerPopover();
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
            })
            .catch(() => {});
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
    if (!isRunning && ['reasoning', 'content', 'tool_start', 'tool_end', 'task_completed', 'tool_confirmation_required'].includes(evt.type)) {
        return;
    }
    switch (evt.type) {
        case 'init':
            if (evt.workspace) updateWorkspaceDisplay(evt.workspace, false);
            if (evt.model) {
                if (modelSelect) modelSelect.value = evt.model;
                updateModelLabels(evt.model);
            }
            if (evt.is_running) {
                setRunningState(true);
            }
            break;

        case 'workspace_updated':
            updateWorkspaceDisplay(evt.workspace, false);
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
            if (evt.name && (evt.name.startsWith('browser_') || evt.name.includes('search'))) {
                if (btnToggleBrowser) btnToggleBrowser.classList.remove('hidden');
                toggleBrowserSidepanel(true);
            }
            if (evt.name === 'spawn_subagent') {
                const subId = (evt.args && evt.args.id) || 'sub_' + Date.now();
                renderSubagentChatStart(subId, evt.args.role, evt.args.prompt);
            } else {
                renderToolStart(evt.id, evt.name, evt.args);
            }
            updateStatus('executing', `${evt.name}`);
            break;

        case 'tool_end':
            if (evt.name && (evt.name.startsWith('browser_') || evt.name.includes('search'))) {
                if (evt.result && evt.result.screenshot) {
                    handleBrowserStateEvent({
                        screenshot: evt.result.screenshot,
                        url: evt.result.url,
                        title: evt.result.title
                    });
                }
            }
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

        case 'browser_state':
            handleBrowserStateEvent(evt);
            break;

        case 'browser_cursor':
            handleBrowserCursorEvent(evt);
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
    if (!activeAssistantCard) ensureAssistantCard();
    if (!activeContentEl) {
        activeContentEl = document.createElement('div');
        activeContentEl.className = 'assistant-content';
        activeAssistantCard.appendChild(activeContentEl);
    }
    const currentRaw = activeContentEl.getAttribute('data-raw') || '';
    const newRaw = currentRaw + text;
    activeContentEl.setAttribute('data-raw', newRaw);
    activeContentEl.innerHTML = formatMarkdown(newRaw);
    scrollToBottom();
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
    }).catch(err => {
        console.error('confirmTool error:', err);
    });
};

function renderToolStart(id, name, args) {
    const card = document.createElement('div');
    card.className = 'tool-card';
    card.id = `tool-card-${id}`;

    activeContentEl = null; // New assistant text after this tool will be placed below
    let argSummary = '';
    if (name === 'run_command') argSummary = args.command || '';
    else if (name === 'read_file' || name === 'write_file' || name === 'edit_file') argSummary = args.path || '';
    else if (name === 'web_fetch' || name === 'browser_open') argSummary = args.url || '';
    else if (name === 'google_search' || name === 'web_search') argSummary = args.query || '';
    else if (name === 'browser_type') argSummary = args.text || '';
    else if (name === 'browser_click') argSummary = args.description || args.selector || '';

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

    // Strip stray braces left behind by tool arguments
    clean = clean.replace(/^\s*\}\s*$/gm, '').trim();

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
    }).catch(err => {
        console.error('Failed to copy to clipboard:', err);
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
    const userMsgIndex = session ? session.messages.length - 1 : 0;
    userCard.innerHTML = `
        <div class="user-bubble-wrapper">
            <div class="user-msg-actions">
                <button class="btn-msg-action btn-msg-rollback" type="button" title="Откатить до этого сообщения" onclick="rollbackToMessage(${userMsgIndex})">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M3 10h10a5 5 0 0 1 5 5v2"/><polyline points="8 5 3 10 8 15"/></svg>
                </button>
                <button class="btn-msg-action btn-msg-copy" type="button" title="Скопировать текст" onclick="copyMessageText(this, ${userMsgIndex})">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                </button>
            </div>
            <div class="user-bubble">${escapeHtml(text)}${imagesHtml}</div>
        </div>
    `;
    messagesFeed.appendChild(userCard);

    currentRunGeneration++;
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
    currentRunGeneration++;
    currentAssistantTurn = null;
    setRunningState(false);
    fetch('/api/stop', { method: 'POST' }).catch(() => {});
});

// ============================================================================
// SETTINGS MODAL
// ============================================================================

let currentProviders = [];

// Provider Template Presets
const PROVIDER_PRESETS = {
    openai: {
        name: 'OpenAI',
        url: 'https://api.openai.com/v1',
        models: 'gpt-4o, gpt-4o-mini, o3-mini, o1'
    },
    openrouter: {
        name: 'OpenRouter',
        url: 'https://openrouter.ai/api/v1',
        models: 'anthropic/claude-3.5-sonnet, deepseek/deepseek-r1, meta-llama/llama-3.3-70b-instruct'
    },
    deepseek_official: {
        name: 'DeepSeek (Официальный)',
        url: 'https://api.deepseek.com/v1',
        models: 'deepseek-chat-official, deepseek-reasoner-official'
    },
    groq: {
        name: 'Groq',
        url: 'https://api.groq.com/openai/v1',
        models: 'llama-3.3-70b-versatile, deepseek-r1-distill-llama-70b'
    },
    ollama: {
        name: 'Ollama (Локальный)',
        url: 'http://localhost:11434/v1',
        models: 'llama3, deepseek-r1, qwen2.5-coder'
    }
};

// DOM Elements for Providers & Updates
const providersListEl = document.getElementById('providers-list');
const provTemplate = document.getElementById('prov-template');
const provName = document.getElementById('prov-name');
const provUrl = document.getElementById('prov-url');
const provKey = document.getElementById('prov-key');
const provModels = document.getElementById('prov-models');
const btnSaveProviderItem = document.getElementById('btn-save-provider-item');

const updateBanner = document.getElementById('update-banner');
const updateVersionLabel = document.getElementById('update-version-label');
const updateMsgLabel = document.getElementById('update-msg-label');
const btnDismissUpdate = document.getElementById('btn-dismiss-update');
const btnApplyUpdate = document.getElementById('btn-apply-update');
const updateCurrentCommit = document.getElementById('update-current-commit');
const updateCheckStatus = document.getElementById('update-check-status');
const btnCheckUpdateManual = document.getElementById('btn-check-update-manual');
const btnApplyUpdateModal = document.getElementById('btn-apply-update-modal');

// Settings Tabs
document.querySelectorAll('.settings-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.settings-tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.settings-tab-pane').forEach(p => p.style.display = 'none');
        btn.classList.add('active');
        const targetPane = document.getElementById(btn.dataset.tab);
        if (targetPane) targetPane.style.display = 'block';
    });
});

if (provTemplate) {
    provTemplate.addEventListener('change', () => {
        const val = provTemplate.value;
        if (PROVIDER_PRESETS[val]) {
            const p = PROVIDER_PRESETS[val];
            provName.value = p.name;
            provUrl.value = p.url;
            provModels.value = p.models;
        }
    });
}

function renderProvidersList() {
    if (!providersListEl) return;
    if (!currentProviders || currentProviders.length === 0) {
        providersListEl.innerHTML = '<div class="empty-hint">Провайдеры еще не добавлены. Заполните форму ниже для добавления.</div>';
        return;
    }

    providersListEl.innerHTML = currentProviders.map((p, idx) => {
        const hasKey = p.api_key && p.api_key.trim().length > 0;
        const keyDisplay = hasKey ? 'Ключ задан (••••' + p.api_key.slice(-4) + ')' : 'Ключ не указан';
        const modelsList = (p.models || []).join(', ') || 'Все';
        return `
            <div class="provider-item">
                <div class="provider-item-info">
                    <div class="provider-item-title">${escapeHtml(p.name || 'Без названия')}</div>
                    <div class="provider-item-meta font-mono">${escapeHtml(p.base_url || '')}</div>
                    <div class="provider-item-models">${escapeHtml(modelsList)}</div>
                    <div class="provider-item-key ${hasKey ? 'has-key' : ''}">${keyDisplay}</div>
                </div>
                <div class="provider-item-actions">
                    <button type="button" class="btn-icon-subtle" onclick="editProvider(${idx})" title="Редактировать">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
                    </button>
                    <button type="button" class="btn-icon-subtle danger" onclick="deleteProvider(${idx})" title="Удалить">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

window.deleteProvider = function(idx) {
    if (idx >= 0 && idx < currentProviders.length) {
        currentProviders.splice(idx, 1);
        renderProvidersList();
    }
};

window.editProvider = function(idx) {
    if (idx >= 0 && idx < currentProviders.length) {
        const p = currentProviders[idx];
        provName.value = p.name || '';
        provUrl.value = p.base_url || '';
        provKey.value = p.api_key || '';
        provModels.value = (p.models || []).join(', ');
        provName.focus();
    }
};

if (btnSaveProviderItem) {
    btnSaveProviderItem.addEventListener('click', () => {
        const name = (provName.value || '').trim();
        const url = (provUrl.value || '').trim();
        const key = (provKey.value || '').trim();
        const modelsStr = (provModels.value || '').trim();

        if (!name || !url) {
            alert('Укажите название и API Base URL провайдера');
            return;
        }

        const models = modelsStr ? modelsStr.split(',').map(m => m.trim()).filter(Boolean) : [];
        const existingIdx = currentProviders.findIndex(p => p.name.toLowerCase() === name.toLowerCase());

        const newProv = {
            id: 'prov_' + Date.now(),
            name: name,
            base_url: url,
            api_key: key,
            models: models
        };

        if (existingIdx >= 0) {
            currentProviders[existingIdx] = newProv;
        } else {
            currentProviders.push(newProv);
        }

        provName.value = '';
        provUrl.value = '';
        provKey.value = '';
        provModels.value = '';
        renderProvidersList();
    });
}

btnOpenSettings.addEventListener('click', () => {
    hideModelPickerPopover();
    fetch('/api/settings')
        .then(r => r.json())
        .then(cfg => {
            currentProviders = Array.isArray(cfg.custom_providers) ? cfg.custom_providers : [];
            renderProvidersList();

            settingWorkspace.value = cfg.workspace || '';
            settingMaxSteps.value = (cfg.max_steps !== undefined && cfg.max_steps !== null) ? cfg.max_steps : 0;
            settingSystemPrompt.value = cfg.system_prompt || '';
            settingAutoAccept.checked = !!cfg.auto_accept_tools;
            settingsModal.classList.remove('hidden');

            fetchAuthStatus();
            checkForUpdates(true);
        })
        .catch(err => {
            console.error('Failed to load settings:', err);
            settingsModal.classList.remove('hidden');
            fetchAuthStatus();
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
        hideModelPickerPopover();
        if (settingsModal && !settingsModal.classList.contains('hidden')) settingsModal.classList.add('hidden');
        if (workspaceModal && !workspaceModal.classList.contains('hidden')) workspaceModal.classList.add('hidden');
        if (subagentModal && !subagentModal.classList.contains('hidden')) closeSubagentModal();
    }
});

[workspaceModal, subagentModal].forEach(modal => {
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
    const rawSteps = parseInt(settingMaxSteps.value, 10);
    const updates = {
        custom_providers: currentProviders,
        workspace: settingWorkspace.value.trim(),
        max_steps: isNaN(rawSteps) ? 0 : Math.max(0, rawSteps),
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
        loadModelsList();
    }).catch(err => {
        alert('Ошибка при сохранении настроек: ' + err);
    });
});

// ============================================================================
// AUTO-UPDATE FROM GIT
// ============================================================================

function checkForUpdates(silent = false) {
    if (updateCheckStatus) updateCheckStatus.textContent = 'Проверка обновлений...';

    fetch('/api/update/check')
        .then(r => r.json())
        .then(res => {
            if (updateCurrentCommit && res.current_commit) {
                updateCurrentCommit.textContent = res.current_commit;
            }

            if (res.has_update) {
                const dismissedCommit = localStorage.getItem('nonroot_update_dismissed');
                if (updateBanner && (!silent || dismissedCommit !== res.latest_commit)) {
                    if (updateVersionLabel) updateVersionLabel.textContent = res.latest_commit || 'новая версия';
                    if (updateMsgLabel) updateMsgLabel.textContent = res.message || 'Новые коммиты в git';
                    updateBanner.classList.remove('hidden');
                }

                if (updateCheckStatus) {
                    updateCheckStatus.textContent = `Доступно обновление (${res.latest_commit}): ${res.message || ''}`;
                }
                if (btnApplyUpdateModal) {
                    btnApplyUpdateModal.classList.remove('hidden');
                }
            } else {
                if (updateBanner) {
                    updateBanner.classList.add('hidden');
                }
                if (!silent && updateCheckStatus) {
                    if (res.error) {
                        updateCheckStatus.textContent = `Ошибка: ${res.error}`;
                    } else {
                        updateCheckStatus.textContent = `У вас последняя версия (${res.current_commit || ''})`;
                    }
                }
                if (btnApplyUpdateModal) {
                    btnApplyUpdateModal.classList.add('hidden');
                }
            }
        })
        .catch(err => {
            if (!silent && updateCheckStatus) {
                updateCheckStatus.textContent = 'Не удалось проверить обновления: ' + err;
            }
        });
}

function applyUpdate(btnEl) {
    const buttons = [btnApplyUpdate, btnApplyUpdateModal].filter(Boolean);
    buttons.forEach(b => {
        b.disabled = true;
        b.dataset.origText = b.textContent;
        b.textContent = 'Обновление...';
    });

    if (updateMsgLabel) {
        updateMsgLabel.textContent = 'Загрузка и установка обновления...';
    }

    fetch('/api/update/apply', { method: 'POST' })
        .then(r => r.json())
        .then(res => {
            if (res.success) {
                if (updateMsgLabel) {
                    updateMsgLabel.textContent = `Обновление ${res.commit} установлено! Перезапуск...`;
                }
                buttons.forEach(b => {
                    b.textContent = 'Успешно!';
                });
                setTimeout(() => {
                    location.reload();
                }, 1200);
            } else {
                const errMsg = res.error || 'Неизвестная ошибка';
                if (updateMsgLabel) {
                    updateMsgLabel.textContent = `Ошибка: ${errMsg}`;
                } else {
                    alert('Ошибка при обновлении: ' + errMsg);
                }
                buttons.forEach(b => {
                    b.disabled = false;
                    b.textContent = b.dataset.origText || 'Обновить сейчас';
                });
            }
        })
        .catch(err => {
            const errStr = 'Ошибка сети при обновлении: ' + err;
            if (updateMsgLabel) {
                updateMsgLabel.textContent = errStr;
            } else {
                alert(errStr);
            }
            buttons.forEach(b => {
                b.disabled = false;
                b.textContent = b.dataset.origText || 'Обновить сейчас';
            });
        });
}

if (btnDismissUpdate) {
    btnDismissUpdate.addEventListener('click', () => {
        if (updateVersionLabel && updateVersionLabel.textContent) {
            localStorage.setItem('nonroot_update_dismissed', updateVersionLabel.textContent.trim());
        }
        if (updateBanner) updateBanner.classList.add('hidden');
    });
}

if (btnApplyUpdate) {
    btnApplyUpdate.addEventListener('click', function() {
        applyUpdate(this);
    });
}

if (btnCheckUpdateManual) {
    btnCheckUpdateManual.addEventListener('click', () => {
        checkForUpdates(false);
    });
}

if (btnApplyUpdateModal) {
    btnApplyUpdateModal.addEventListener('click', function() {
        applyUpdate(this);
    });
}

// ==========================================
// Custom Model Picker & Popover Management
// ==========================================
let allModelsList = [];

function updateModelLabels(modelId) {
    if (!modelId) return;
    const found = allModelsList.find(m => m.id === modelId);
    const label = found ? (found.name || found.id) : modelId;
    const topLabel = document.getElementById('top-model-label');
    const bottomLabel = document.getElementById('bottom-model-label');
    if (topLabel) topLabel.textContent = label;
    if (bottomLabel) bottomLabel.textContent = label;
}

function renderModelPickerItems(filterQuery = '') {
    const listEl = document.getElementById('model-picker-list');
    if (!listEl) return;

    const q = filterQuery.toLowerCase().trim();
    const filtered = allModelsList.filter(m => {
        if (!q) return true;
        return (m.id && m.id.toLowerCase().includes(q)) ||
               (m.name && m.name.toLowerCase().includes(q)) ||
               (m.desc && m.desc.toLowerCase().includes(q)) ||
               (m.group && m.group.toLowerCase().includes(q));
    });

    if (filtered.length === 0) {
        listEl.innerHTML = '<div class="model-picker-empty">Модели не найдены</div>';
        return;
    }

    // Group models
    const groups = {};
    for (const m of filtered) {
        const grp = m.group || 'Модели';
        if (!groups[grp]) groups[grp] = [];
        groups[grp].push(m);
    }

    const currentVal = modelSelect ? modelSelect.value : 'deepseek-chat';
    let html = '';
    for (const [groupName, groupModels] of Object.entries(groups)) {
        html += `<div class="model-picker-group">`;
        html += `<div class="model-picker-group-title">${escapeHtml(groupName)}</div>`;
        for (const mod of groupModels) {
            const isSelected = mod.id === currentVal;
            const desc = mod.desc || (mod.id === 'deepseek-chat' ? 'DeepSeek-V3 · Универсальная и быстрая модель' : (mod.id === 'deepseek-reasoner' ? 'DeepSeek-R1 · Рассуждения и логика' : ''));
            const isBuiltin = mod.group && mod.group.includes('Встроенный');
            html += `
                <div class="model-picker-item ${isSelected ? 'active' : ''}" onclick="selectModel('${escapeHtml(mod.id)}')">
                    <div class="model-item-info">
                        <div class="model-item-title-row">
                            <span class="model-item-name">${escapeHtml(mod.name || mod.id)}</span>
                            ${isBuiltin ? '<span class="model-item-badge">Встроенная</span>' : ''}
                        </div>
                        ${desc ? `<span class="model-item-desc">${escapeHtml(desc)}</span>` : ''}
                    </div>
                    ${isSelected ? `
                        <div class="model-item-check">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                        </div>
                    ` : ''}
                </div>
            `;
        }
        html += `</div>`;
    }
    listEl.innerHTML = html;
}

window.selectModel = function(modelId) {
    if (modelSelect) {
        modelSelect.value = modelId;
    }
    updateModelLabels(modelId);
    hideModelPickerPopover();
};

function showModelPickerPopover(anchorEl) {
    const popover = document.getElementById('model-picker-popover');
    if (!popover || !anchorEl) return;

    renderModelPickerItems('');
    const searchInput = document.getElementById('model-search-input');
    if (searchInput) searchInput.value = '';

    popover.classList.remove('hidden');

    const rect = anchorEl.getBoundingClientRect();
    const popoverWidth = Math.min(320, window.innerWidth - 24);
    const popoverHeight = Math.min(popover.offsetHeight || 350, 400);

    let left = rect.left;
    if (left + popoverWidth > window.innerWidth - 12) {
        left = window.innerWidth - popoverWidth - 12;
    }
    if (left < 12) left = 12;

    if (rect.bottom + popoverHeight > window.innerHeight - 10) {
        // Open upwards
        let top = rect.top - popoverHeight - 8;
        if (top < 10) top = 10;
        popover.style.top = top + 'px';
    } else {
        // Open downwards
        popover.style.top = (rect.bottom + 6) + 'px';
    }
    popover.style.left = left + 'px';

    if (searchInput) {
        setTimeout(() => searchInput.focus(), 60);
    }
}

function hideModelPickerPopover() {
    const popover = document.getElementById('model-picker-popover');
    if (popover && !popover.classList.contains('hidden')) {
        popover.classList.add('hidden');
    }
}

function loadModelsList() {
    fetch('/api/models')
        .then(r => r.json())
        .then(data => {
            if (data.models && data.models.length > 0) {
                allModelsList = data.models;
                const currentVal = modelSelect.value || 'deepseek-chat';
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
                if (currentVal && allModelsList.some(m => m.id === currentVal)) {
                    modelSelect.value = currentVal;
                } else if (allModelsList.length > 0) {
                    modelSelect.value = allModelsList[0].id;
                }
                updateModelLabels(modelSelect.value);
            }
        })
        .catch(() => {});
}

const btnTopModel = document.getElementById('btn-top-model-trigger');
const btnBottomModel = document.getElementById('btn-bottom-model-trigger');

if (btnTopModel) {
    btnTopModel.addEventListener('click', (e) => {
        e.stopPropagation();
        const popover = document.getElementById('model-picker-popover');
        if (popover && !popover.classList.contains('hidden')) {
            hideModelPickerPopover();
        } else {
            showModelPickerPopover(btnTopModel);
        }
    });
}

if (btnBottomModel) {
    btnBottomModel.addEventListener('click', (e) => {
        e.stopPropagation();
        const popover = document.getElementById('model-picker-popover');
        if (popover && !popover.classList.contains('hidden')) {
            hideModelPickerPopover();
        } else {
            showModelPickerPopover(btnBottomModel);
        }
    });
}

const modelSearchInput = document.getElementById('model-search-input');
if (modelSearchInput) {
    modelSearchInput.addEventListener('input', (e) => {
        renderModelPickerItems(e.target.value);
    });
    modelSearchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') hideModelPickerPopover();
    });
}

document.addEventListener('click', (e) => {
    const popover = document.getElementById('model-picker-popover');
    if (popover && !popover.classList.contains('hidden')) {
        if (!popover.contains(e.target) && 
            (!btnTopModel || !btnTopModel.contains(e.target)) &&
            (!btnBottomModel || !btnBottomModel.contains(e.target))) {
            hideModelPickerPopover();
        }
    }
});

window.addEventListener('resize', hideModelPickerPopover);

// ==========================================
// DeepSeek Auth & Token Management
// ==========================================
const authTokenPreview = document.getElementById('auth-token-preview');
const authStatusBadge = document.getElementById('auth-status-badge');
const authSourceBadge = document.getElementById('auth-source-badge');
const authBackupPreview = document.getElementById('auth-backup-preview');
const btnAuthBrowser = document.getElementById('btn-auth-browser');
const authBrowserStatusText = document.getElementById('auth-browser-status-text');
const btnAuthRevert = document.getElementById('btn-auth-revert');
const btnAuthRestoreDefault = document.getElementById('btn-auth-restore-default');
const authCustomTokenInput = document.getElementById('auth-custom-token-input');
const btnAuthSaveCustom = document.getElementById('btn-auth-save-custom');

let browserAuthPollTimer = null;

function fetchAuthStatus() {
    fetch('/api/auth/status')
        .then(r => r.json())
        .then(data => {
            if (authTokenPreview) {
                authTokenPreview.textContent = data.token_preview || 'Не задан';
            }
            if (authStatusBadge) {
                if (data.has_token) {
                    authStatusBadge.textContent = 'Активен';
                    authStatusBadge.className = 'auth-status-badge badge-active';
                } else {
                    authStatusBadge.textContent = 'Не задан';
                    authStatusBadge.className = 'auth-status-badge';
                }
            }
            if (authSourceBadge) {
                if (data.is_default) {
                    authSourceBadge.textContent = 'Встроенный (заводской)';
                } else {
                    authSourceBadge.textContent = 'Пользовательский';
                }
            }
            if (authBackupPreview) {
                authBackupPreview.textContent = data.backup_preview || 'Нет';
            }
            if (btnAuthRevert) {
                btnAuthRevert.disabled = !data.has_backup;
                btnAuthRevert.title = data.has_backup 
                    ? `Вернуть предыдущий токен (${data.backup_preview})` 
                    : 'Нет сохраненного резервного токена';
            }
        })
        .catch(err => {
            console.error('Failed to load auth status:', err);
        });
}

function pollBrowserAuth() {
    if (browserAuthPollTimer) clearInterval(browserAuthPollTimer);
    
    browserAuthPollTimer = setInterval(() => {
        fetch('/api/auth/browser/status')
            .then(r => r.json())
            .then(st => {
                if (authBrowserStatusText) {
                    authBrowserStatusText.textContent = st.message || 'Ожидание авторизации...';
                }
                if (!st.running) {
                    clearInterval(browserAuthPollTimer);
                    browserAuthPollTimer = null;
                    if (btnAuthBrowser) btnAuthBrowser.disabled = false;
                    fetchAuthStatus();
                    loadModelsList();
                }
            })
            .catch(() => {
                clearInterval(browserAuthPollTimer);
                browserAuthPollTimer = null;
                if (btnAuthBrowser) btnAuthBrowser.disabled = false;
            });
    }, 1500);
}

if (btnAuthBrowser) {
    btnAuthBrowser.addEventListener('click', () => {
        btnAuthBrowser.disabled = true;
        if (authBrowserStatusText) {
            authBrowserStatusText.classList.remove('hidden');
            authBrowserStatusText.textContent = 'Запуск Google Chrome...';
        }
        fetch('/api/auth/browser', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    pollBrowserAuth();
                } else {
                    alert(data.error || 'Не удалось запустить браузер');
                    btnAuthBrowser.disabled = false;
                    if (authBrowserStatusText) authBrowserStatusText.classList.add('hidden');
                }
            })
            .catch(err => {
                alert('Ошибка связи с сервером: ' + err.message);
                btnAuthBrowser.disabled = false;
                if (authBrowserStatusText) authBrowserStatusText.classList.add('hidden');
            });
    });
}

if (btnAuthRevert) {
    btnAuthRevert.addEventListener('click', () => {
        if (!confirm('Вернуть предыдущий сохраненный токен?')) return;
        fetch('/api/auth/revert', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    fetchAuthStatus();
                    alert(data.message || 'Предыдущий токен восстановлен!');
                } else {
                    alert(data.error || 'Не удалось вернуть токен');
                }
            })
            .catch(err => alert('Ошибка: ' + err.message));
    });
}

if (btnAuthRestoreDefault) {
    btnAuthRestoreDefault.addEventListener('click', () => {
        if (!confirm('Восстановить встроенный заводской токен? Текущий токен будет сохранен в резервной копии.')) return;
        fetch('/api/auth/restore-default', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    fetchAuthStatus();
                    alert(data.message || 'Встроенный токен восстановлен!');
                } else {
                    alert(data.error || 'Ошибка восстановления токена');
                }
            })
            .catch(err => alert('Ошибка: ' + err.message));
    });
}

if (btnAuthSaveCustom) {
    btnAuthSaveCustom.addEventListener('click', () => {
        const val = (authCustomTokenInput ? authCustomTokenInput.value : '').trim();
        if (!val) {
            alert('Введите токен или вставьте JSON deepseek-auth.json');
            return;
        }
        fetch('/api/auth/custom', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: val })
        })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    if (authCustomTokenInput) authCustomTokenInput.value = '';
                    fetchAuthStatus();
                    alert(data.message || 'Пользовательский токен успешно применен!');
                } else {
                    alert(data.error || 'Ошибка применения токена');
                }
            })
            .catch(err => alert('Ошибка: ' + err.message));
    });
}

// ============================================================================
// EMBEDDED CHROMIUM BROWSER SUBSYSTEM & AI CURSOR
// ============================================================================

let isBrowserOpen = false;
let currentBrowserUrl = '';
let currentBrowserScreenshot = null;
let aiCursorHideTimeout = null;

function toggleBrowserSidepanel(show = null) {
    if (!browserSidepanel) return;
    const willShow = (show !== null) ? !!show : browserSidepanel.classList.contains('hidden');
    isBrowserOpen = willShow;

    if (willShow) {
        browserSidepanel.classList.remove('hidden');
        if (btnToggleBrowser) btnToggleBrowser.classList.add('active');
        if (!browserScreenImg || !browserScreenImg.src || browserScreenImg.src.endsWith('#') || browserScreenImg.src === window.location.href) {
            fetchBrowserState();
        }
    } else {
        browserSidepanel.classList.add('hidden');
        if (btnToggleBrowser) btnToggleBrowser.classList.remove('active');
    }
}

function fetchBrowserState() {
    fetch('/api/browser/state')
        .then(r => r.json())
        .then(data => {
            if (data) {
                handleBrowserStateEvent(data);
            }
        })
        .catch(err => console.debug('Browser state fetch error:', err));
}

function handleBrowserStateEvent(data) {
    if (!data) return;
    if (data.screenshot || (data.url && data.url !== 'about:blank')) {
        toggleBrowserSidepanel(true);
    }

    if (data.url) {
        currentBrowserUrl = data.url;
        if (browserUrlInput && document.activeElement !== browserUrlInput) {
            browserUrlInput.value = data.url;
        }
        if (browserPulseDot) browserPulseDot.classList.add('active');
    }

    if (data.title) {
        if (browserFooterTitle) browserFooterTitle.textContent = data.title;
    } else if (data.url && browserFooterTitle) {
        browserFooterTitle.textContent = data.url;
    }

    if (data.screenshot) {
        currentBrowserScreenshot = data.screenshot;
        if (browserScreenImg) {
            browserScreenImg.src = data.screenshot;
        }
    }

    if (browserAiStatusText && data.ai_action) {
        browserAiStatusText.textContent = data.ai_action;
    }

    if (browserLoadingOverlay) {
        if (data.loading) {
            browserLoadingOverlay.classList.remove('hidden');
        } else {
            browserLoadingOverlay.classList.add('hidden');
        }
    }
}

function handleBrowserCursorEvent(data) {
    if (!aiCursor || !browserViewportCanvas) return;

    const x = typeof data.x === 'number' ? data.x : 0;
    const y = typeof data.y === 'number' ? data.y : 0;

    const leftPercent = Math.min(100, Math.max(0, (x / 1280) * 100));
    const topPercent = Math.min(100, Math.max(0, (y / 800) * 100));

    aiCursor.style.left = `${leftPercent}%`;
    aiCursor.style.top = `${topPercent}%`;
    aiCursor.classList.remove('hidden');

    if (aiCursorLabel) {
        aiCursorLabel.textContent = data.label || data.action || 'ИИ';
    }

    if (browserAiStatusText) {
        browserAiStatusText.textContent = data.label || data.action || 'ИИ действует';
    }

    if (data.ripple && aiCursorRipple) {
        aiCursorRipple.classList.remove('active');
        void aiCursorRipple.offsetWidth;
        aiCursorRipple.classList.add('active');
    }

    if (aiCursorHideTimeout) clearTimeout(aiCursorHideTimeout);
    aiCursorHideTimeout = setTimeout(() => {
        if (!isRunning && aiCursor) {
            aiCursor.classList.add('hidden');
            if (browserAiStatusText) browserAiStatusText.textContent = 'ИИ готов';
        }
    }, 4000);
}

function navigateBrowser(url) {
    if (!url) return;
    let target = url.trim();
    if (!target.startsWith('http://') && !target.startsWith('https://') && !target.startsWith('about:')) {
        target = 'https://' + target;
    }
    if (browserUrlInput) browserUrlInput.value = target;
    if (browserLoadingOverlay) browserLoadingOverlay.classList.remove('hidden');
    if (browserAiStatusText) browserAiStatusText.textContent = 'Загрузка...';

    fetch('/api/browser/navigate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: target })
    })
    .then(r => r.json())
    .then(data => {
        if (browserLoadingOverlay) browserLoadingOverlay.classList.add('hidden');
        if (data.success) {
            handleBrowserStateEvent(data);
        } else {
            alert('Ошибка загрузки страницы: ' + (data.error || 'неизвестная ошибка'));
        }
    })
    .catch(err => {
        if (browserLoadingOverlay) browserLoadingOverlay.classList.add('hidden');
        alert('Сбой связи с браузером: ' + err.message);
    });
}

function handleViewportClick(e) {
    if (!browserScreenImg) return;
    const rect = browserScreenImg.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;

    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;

    const origX = Math.round((clickX / rect.width) * 1280);
    const origY = Math.round((clickY / rect.height) * 800);

    handleBrowserCursorEvent({
        x: origX,
        y: origY,
        action: 'click',
        label: 'Клик',
        ripple: true
    });

    fetch('/api/browser/click', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ x: origX, y: origY, description: 'Клик пользователя' })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success && data.screenshot) {
            handleBrowserStateEvent(data);
        }
    })
    .catch(err => console.debug('Viewport click error:', err));
}

// Browser UI Event Listeners
if (btnToggleBrowser) {
    btnToggleBrowser.addEventListener('click', () => toggleBrowserSidepanel());
}

if (browserBtnClose) {
    browserBtnClose.addEventListener('click', () => toggleBrowserSidepanel(false));
}

if (browserBtnGo && browserUrlInput) {
    browserBtnGo.addEventListener('click', () => navigateBrowser(browserUrlInput.value));
    browserUrlInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            navigateBrowser(browserUrlInput.value);
        }
    });
}

if (browserBtnReload) {
    browserBtnReload.addEventListener('click', () => {
        const url = currentBrowserUrl || (browserUrlInput ? browserUrlInput.value : '');
        if (url) navigateBrowser(url);
    });
}

if (browserScreenImg) {
    browserScreenImg.addEventListener('click', handleViewportClick);
}

// Quick action: Clone 1-to-1
if (btnBrowserClone) {
    btnBrowserClone.addEventListener('click', () => {
        const url = currentBrowserUrl || (browserUrlInput ? browserUrlInput.value : '');
        if (!url) {
            alert('Сначала откройте страницу в браузере для клонирования');
            return;
        }

        const originalHtml = btnBrowserClone.innerHTML;
        btnBrowserClone.disabled = true;
        btnBrowserClone.innerHTML = '<span>Клонирование 1 в 1...</span>';

        fetch('/api/browser/clone', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url, output_folder: 'cloned_site' })
        })
        .then(r => r.json())
        .then(data => {
            btnBrowserClone.disabled = false;
            btnBrowserClone.innerHTML = originalHtml;
            if (data.success) {
                alert(`Сайт успешно клонирован 1 в 1 в директорию "${data.output_dir || 'cloned_site'}"!\n\nСоздана автономная копия: index.html, style.css, загружены изображения и ассеты.`);
            } else {
                alert('Ошибка при клонировании сайта: ' + (data.error || 'неизвестная ошибка'));
            }
        })
        .catch(err => {
            btnBrowserClone.disabled = false;
            btnBrowserClone.innerHTML = originalHtml;
            alert('Сбой запроса клонирования: ' + err.message);
        });
    });
}

// Quick action: Inspect in Chat (Snapshot)
if (btnBrowserInspectChat) {
    btnBrowserInspectChat.addEventListener('click', () => {
        if (!currentBrowserScreenshot) {
            alert('В браузере пока нет открытой страницы');
            return;
        }
        if (!attachedImages.includes(currentBrowserScreenshot)) {
            attachedImages.push(currentBrowserScreenshot);
            renderImagePreviews();
        }
        if (promptInput) {
            promptInput.value = promptInput.value || 'Внимательно посмотри на скриншот страницы и скопируй её дизайн:';
            promptInput.focus();
        }
    });
}

// Shortcut: Cmd+B or Ctrl+B to toggle browser
window.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'b') {
        // Do not intercept inside textareas unless explicitly requested
        if (document.activeElement && (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA') && document.activeElement !== promptInput) {
            return;
        }
        e.preventDefault();
        toggleBrowserSidepanel();
    }
});

// Initialize on Load
window.addEventListener('DOMContentLoaded', () => {
    initSessions();
    connectSSE();
    loadModelsList();
    fetchAuthStatus();
    setTimeout(() => checkForUpdates(true), 2000);
    setInterval(() => checkForUpdates(true), 15 * 60 * 1000); // Check every 15 minutes
});

