/**
 * Chatbot Logic - DEB's Health Assistant
 * Handles RAG interactions, streaming, voice STT/TTS, and UI state
 */

let currentSessionId = localStorage.getItem('currentSessionId') || 'new';
let isVoiceEnabled = localStorage.getItem('voiceEnabled') === 'true';
let recognition = null;
let synth = window.speechSynthesis;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadSessions();
    if (currentSessionId !== 'new') {
        loadHistory(currentSessionId);
    }
    updateVoiceUI();
    initVoiceRecognition();
});

// UI Toggles
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('mainContent');
    sidebar.classList.toggle('closed');
    mainContent.classList.toggle('expanded');
    localStorage.setItem('sidebarClosed', sidebar.classList.contains('closed'));
}

function newChat() {
    currentSessionId = 'new';
    document.getElementById('chatMessages').innerHTML = '';
    document.getElementById('greetingText').classList.remove('hidden');
    document.getElementById('chatTitle').textContent = 'New Chat';
    document.getElementById('inputArea').classList.remove('at-bottom');
    document.getElementById('inputArea').classList.add('input-area-centered');
}

// Messaging
async function sendMessage() {
    const input = document.getElementById('messageInput');
    const query = input.value.trim();
    if (!query) return;

    // Reset input
    input.value = '';
    input.style.height = 'auto';

    // Hide greeting on first message
    document.getElementById('greetingText').classList.add('hidden');
    document.getElementById('inputArea').classList.remove('input-area-centered');
    document.getElementById('inputArea').classList.add('at-bottom');

    // Add user message to UI
    appendMessage('user', query);

    // Prepare assistant message container
    const messageId = 'msg-' + Date.now();
    appendMessage('assistant', '', messageId, true); // Typing state

    try {
        const lang = StorageService.get('selectedLanguage')?.name || 'English';
        const response = await fetch('/api/v1/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: query,
                session_id: currentSessionId,
                language: lang
            })
        });

        if (!response.ok) throw new Error('Failed to connect to assistant');

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let assistantText = '';
        const contentEl = document.querySelector(`#${messageId} .message-content`);
        const statusEl = document.querySelector(`#${messageId} .status-indicator`);

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const data = JSON.parse(line);
                    
                    if (data.type === 'session_init') {
                        currentSessionId = data.session_id;
                        localStorage.setItem('currentSessionId', currentSessionId);
                        loadSessions();
                    } else if (data.type === 'status') {
                        statusEl.textContent = data.content;
                    } else if (data.type === 'token') {
                        statusEl.classList.add('hidden');
                        assistantText += data.content;
                        contentEl.innerHTML = formatMarkdown(assistantText);
                        scrollToBottom();
                    }
                } catch (e) {
                    console.error("Error parsing stream chunk:", e);
                }
            }
        }

        // Finalize
        if (isVoiceEnabled) {
            readAloud(assistantText);
        }

    } catch (err) {
        console.error(err);
        const contentEl = document.querySelector(`#${messageId} .message-content`);
        contentEl.innerHTML = `<span class="text-red-500">Error: ${err.message}</span>`;
    }
}

function appendMessage(role, content, id = null, isStreaming = false) {
    const container = document.getElementById('chatMessages');
    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-message flex ${role === 'user' ? 'justify-end' : 'justify-start'} mb-6`;
    if (id) msgDiv.id = id;

    const innerDiv = document.createElement('div');
    innerDiv.className = `max-w-[85%] rounded-2xl p-4 ${
        role === 'user' 
        ? 'bg-blue-600 text-white rounded-tr-none' 
        : 'bg-gray-800 text-gray-100 border border-gray-700 rounded-tl-none'
    }`;

    if (role === 'assistant') {
        innerDiv.innerHTML = `
            <div class="status-indicator text-xs text-blue-400 mb-2 animate-pulse ${!isStreaming ? 'hidden' : ''}">Thinking...</div>
            <div class="message-content text-sm leading-relaxed">${formatMarkdown(content)}</div>
            <div class="flex items-center gap-2 mt-3 pt-2 border-t border-gray-700/50">
                <button onclick="readAloudFromEl(this)" class="text-gray-500 hover:text-white transition" title="Listen">
                    <i class="fas fa-volume-up text-xs"></i>
                </button>
                <button onclick="copyToClipboard(this)" class="text-gray-500 hover:text-white transition" title="Copy">
                    <i class="fas fa-copy text-xs"></i>
                </button>
            </div>
        `;
    } else {
        innerDiv.innerHTML = `<div class="message-content text-sm">${content}</div>`;
    }

    msgDiv.appendChild(innerDiv);
    container.appendChild(msgDiv);
    scrollToBottom();
}

// Voice Logic
function initVoiceRecognition() {
    if (!('webkitSpeechRecognition' in window)) {
        console.warn("Speech recognition not supported");
        return;
    }
    recognition = new webkitSpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onstart = () => {
        const micBtn = document.querySelector('[onclick="startVoiceInput()"]');
        micBtn.classList.add('recording-pulse');
        micBtn.querySelector('i').classList.add('text-red-500');
    };

    recognition.onresult = (event) => {
        const text = event.results[0][0].transcript;
        document.getElementById('messageInput').value = text;
        sendMessage();
    };

    recognition.onend = () => {
        const micBtn = document.querySelector('[onclick="startVoiceInput()"]');
        micBtn.classList.remove('recording-pulse');
        micBtn.querySelector('i').classList.remove('text-red-500');
    };

    recognition.onerror = (event) => {
        console.error("Recognition error:", event.error);
    };
}

function startVoiceInput() {
    if (!recognition) {
        alert("Speech recognition is not supported in this browser.");
        return;
    }
    const langCode = StorageService.get('selectedLanguage')?.code || 'en-US';
    recognition.lang = langCode;
    recognition.start();
}

function toggleVoice() {
    isVoiceEnabled = !isVoiceEnabled;
    localStorage.setItem('voiceEnabled', isVoiceEnabled);
    updateVoiceUI();
}

function updateVoiceUI() {
    const btn = document.getElementById('voiceBtn');
    const icon = btn.querySelector('i');
    if (isVoiceEnabled) {
        icon.className = 'fas fa-volume-up text-blue-400';
        btn.title = "Voice Recitation: ON";
    } else {
        icon.className = 'fas fa-volume-mute text-gray-500';
        btn.title = "Voice Recitation: OFF";
    }
}

function readAloud(text) {
    if (!synth) return;
    synth.cancel(); // Stop any current speech
    
    const utterance = new SpeechSynthesisUtterance(text);
    const langCode = StorageService.get('selectedLanguage')?.code || 'en-US';
    utterance.lang = langCode;
    
    // Try to find a matching voice
    const voices = synth.getVoices();
    const voice = voices.find(v => v.lang.startsWith(langCode.split('-')[0]));
    if (voice) utterance.voice = voice;

    synth.speak(utterance);
}

function readAloudFromEl(btn) {
    const text = btn.closest('.chat-message').querySelector('.message-content').textContent;
    readAloud(text);
}

// Helpers
function formatMarkdown(text) {
    if (!text) return '';
    // Basic Markdown support (can be extended or use a library like marked.js)
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br>');
}

function scrollToBottom() {
    const container = document.getElementById('messagesContainer');
    container.scrollTop = container.scrollHeight;
}

function handleKeyPress(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

function copyToClipboard(btn) {
    const text = btn.closest('.chat-message').querySelector('.message-content').textContent;
    navigator.clipboard.writeText(text).then(() => {
        const icon = btn.querySelector('i');
        icon.className = 'fas fa-check text-green-500';
        setTimeout(() => icon.className = 'fas fa-copy text-xs', 2000);
    });
}

// History Management
async function loadSessions() {
    try {
        const response = await fetch('/api/v1/chat/sessions?limit=10');
        const resData = await response.json();
        const sessions = resData.sessions || [];
        const list = document.getElementById('historyList');
        list.innerHTML = '';

        sessions.forEach(s => {
            const div = document.createElement('div');
            div.className = `history-item p-3 cursor-pointer text-sm flex items-center justify-between ${currentSessionId === s.id ? 'active' : ''}`;
            div.onclick = () => switchSession(s.id);
            div.innerHTML = `
                <div class="flex items-center gap-2 overflow-hidden">
                    <i class="far fa-comment text-gray-500 flex-shrink-0"></i>
                    <span class="truncate">${s.title || 'New Chat'}</span>
                </div>
            `;
            list.appendChild(div);
        });
    } catch (err) {
        console.error("Failed to load sessions:", err);
    }
}

async function switchSession(id) {
    currentSessionId = id;
    localStorage.setItem('currentSessionId', id);
    document.getElementById('chatMessages').innerHTML = '';
    document.getElementById('greetingText').classList.add('hidden');
    document.getElementById('inputArea').classList.remove('input-area-centered');
    document.getElementById('inputArea').classList.add('at-bottom');
    loadHistory(id);
    loadSessions();
}

async function loadHistory(id) {
    try {
        const response = await fetch(`/api/v1/chat/sessions/${id}`);
        const data = await response.json();
        document.getElementById('chatTitle').textContent = data.title || 'New Chat';
        data.messages.forEach(m => appendMessage(m.role, m.content));
    } catch (err) {
        console.error("Failed to load history:", err);
    }
}

function editChatTitle() {
    const newTitle = prompt("Enter new chat title:", document.getElementById('chatTitle').textContent);
    if (newTitle && currentSessionId !== 'new') {
        fetch(`/api/v1/chat/sessions/${currentSessionId}/title`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: newTitle })
        }).then(() => {
            document.getElementById('chatTitle').textContent = newTitle;
            loadSessions();
        });
    }
}

// Placeholder functions for expected index.html calls
function attachFile() { document.getElementById('fileInput').click(); }
function insertImage() { document.getElementById('fileInput').click(); }
function handleFileUpload(e) { console.log("File uploaded:", e.target.files[0]); }
function closeArtifact() { document.getElementById('artifactPanel').classList.remove('show'); }
