// ==================== CONFIG ====================
const API_BASE = '';  // Same origin
const MAX_HISTORY = 20;
const IMAGE_GENERATION_TRIGGERS = ['tạo ảnh', 'vẽ ảnh', 'generate image', 'create image', 'vẽ cho tôi', 'tạo hình'];

// ==================== STATE ====================
let currentProfile = 'default';
let chatHistory = [];
let isLoading = false;
let selectedFiles = [];
let isGeneratingImage = false;

// ==================== DOM ELEMENTS ====================
const chatContainer = document.getElementById('chatContainer');
const chatMessages = document.getElementById('chatMessages');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const typingIndicator = document.getElementById('typingIndicator');
const profilesList = document.getElementById('profilesList');
const currentProfileDisplay = document.getElementById('currentProfile');
const darkModeToggle = document.getElementById('darkModeToggle');
const clearHistoryBtn = document.getElementById('clearHistoryBtn');
const menuBtn = document.getElementById('menuBtn');
const sidebar = document.getElementById('sidebar');
const sidebarClose = document.getElementById('sidebarClose');
const toastContainer = document.getElementById('toastContainer');

// New elements for file upload and image generation
const attachBtn = document.getElementById('attachBtn');
const generateBtn = document.getElementById('generateBtn');
const fileInput = document.getElementById('fileInput');
const filePreview = document.getElementById('filePreview');
const imageModal = document.getElementById('imageModal');
const modalOverlay = document.getElementById('modalOverlay');
const modalClose = document.getElementById('modalClose');
const modalImage = document.getElementById('modalImage');
const modalDownload = document.getElementById('modalDownload');
const sidebarOverlay = document.getElementById('sidebarOverlay');

// ==================== INIT ====================
document.addEventListener('DOMContentLoaded', () => {
    loadProfiles();
    loadSettings();
    loadChatHistory();
    setupEventListeners();
    setupVisualEffects();
    autoResizeTextarea();
});

// ==================== PROFILES ====================
async function loadProfiles() {
    try {
        const response = await fetch(`${API_BASE}/api/profiles`);
        const data = await response.json();

        if (data.profiles) {
            renderProfiles(data.profiles);
            currentProfile = data.current || 'default';
            updateProfileDisplay();
        }
    } catch (error) {
        console.error('Error loading profiles:', error);
        const fallbackProfiles = [
            { id: 'default', name: 'Chatbot', description: 'Trợ lý AI bình thường' },
            { id: 'duy', name: 'Duy', description: 'Profile Duy' },
            { id: 'vy', name: 'Tiểu Vy', description: 'Profile Tiểu Vy' }
        ];
        renderProfiles(fallbackProfiles);
    }
}

function renderProfiles(profiles) {
    profilesList.innerHTML = profiles.map(p => `
        <div class="profile-item ${p.id === currentProfile ? 'active' : ''}" 
             data-profile="${p.id}">
            <div class="profile-name">${p.name}</div>
            <div class="profile-desc">${p.description}</div>
        </div>
    `).join('');

    document.querySelectorAll('.profile-item').forEach(item => {
        item.addEventListener('click', () => selectProfile(item.dataset.profile));
    });
}

async function selectProfile(profileId) {
    try {
        const response = await fetch(`${API_BASE}/api/profile`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ profile: profileId })
        });

        const data = await response.json();

        if (data.success) {
            currentProfile = profileId;
            updateProfileDisplay();
            document.querySelectorAll('.profile-item').forEach(item => {
                item.classList.toggle('active', item.dataset.profile === profileId);
            });
            showToast(`Đã đổi sang profile: ${data.name || profileId}`, 'success');
            closeSidebar();
        } else {
            showToast(data.error || 'Không thể đổi profile', 'error');
        }
    } catch (error) {
        console.error('Error changing profile:', error);
        currentProfile = profileId;
        updateProfileDisplay();
        closeSidebar();
    }
}

function updateProfileDisplay() {
    currentProfileDisplay.textContent = `Profile: ${currentProfile.charAt(0).toUpperCase() + currentProfile.slice(1)}`;
}

// ==================== FILE UPLOAD ====================
function handleFileSelect(event) {
    const files = Array.from(event.target.files);
    files.forEach(file => {
        if (file.size > 10 * 1024 * 1024) {
            showToast(`File ${file.name} quá lớn (max 10MB)`, 'error');
            return;
        }
        selectedFiles.push(file);
    });
    updateFilePreview();
    fileInput.value = '';
}

function updateFilePreview() {
    if (selectedFiles.length === 0) {
        filePreview.classList.remove('active');
        filePreview.innerHTML = '';
        return;
    }

    filePreview.classList.add('active');
    filePreview.innerHTML = selectedFiles.map((file, index) => {
        if (file.type.startsWith('image/')) {
            const url = URL.createObjectURL(file);
            return `
                <div class="preview-item" data-index="${index}">
                    <img src="${url}" alt="${file.name}">
                    <button class="remove-btn" onclick="removeFile(${index})">✕</button>
                </div>
            `;
        } else {
            const icon = getFileIcon(file.name);
            return `
                <div class="preview-item" data-index="${index}">
                    <div class="file-icon">
                        ${icon}
                        <span>${file.name.slice(0, 10)}...</span>
                    </div>
                    <button class="remove-btn" onclick="removeFile(${index})">✕</button>
                </div>
            `;
        }
    }).join('');
}

function getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const icons = {
        pdf: '📄',
        txt: '📝',
        doc: '📃',
        docx: '📃'
    };
    return icons[ext] || '📁';
}

function removeFile(index) {
    selectedFiles.splice(index, 1);
    updateFilePreview();
}

function clearFiles() {
    selectedFiles = [];
    updateFilePreview();
}

// ==================== OCR (TEXT FROM IMAGE) ====================
async function extractTextFromImage(file) {
    try {
        showToast('Đang đọc text từ ảnh...', 'info');
        const result = await Tesseract.recognize(file, 'vie+eng', {
            logger: m => console.log(m)
        });
        return result.data.text.trim();
    } catch (error) {
        console.error('OCR Error:', error);
        return null;
    }
}

// ==================== IMAGE GENERATION ====================
function isImageGenerationRequest(message) {
    const lowerMsg = message.toLowerCase();
    return IMAGE_GENERATION_TRIGGERS.some(trigger => lowerMsg.includes(trigger));
}

function extractImagePrompt(message) {
    let prompt = message;
    IMAGE_GENERATION_TRIGGERS.forEach(trigger => {
        prompt = prompt.replace(new RegExp(trigger, 'gi'), '').trim();
    });
    return prompt || message;
}

async function generateImage(prompt) {
    if (isGeneratingImage) return;
    isGeneratingImage = true;

    addMessage(`🎨 Tạo ảnh: "${prompt}"`, 'user');

    // Show generating indicator
    const generatingHTML = `
        <div class="message bot-message" id="generatingMsg">
            <div class="message-avatar">🤖</div>
            <div class="message-content">
                <div class="message-bubble">
                    <div class="generating-indicator">
                        <div class="spinner"></div>
                        <span>Đang tạo ảnh AI... (có thể mất 10-30 giây)</span>
                    </div>
                </div>
            </div>
        </div>
    `;
    chatMessages.insertAdjacentHTML('beforeend', generatingHTML);
    scrollToBottom();

    try {
        // Check if puter is available
        if (typeof puter === 'undefined') {
            throw new Error('Puter.js chưa được tải. Vui lòng tải lại trang.');
        }

        const result = await puter.ai.txt2img(prompt);

        // Remove generating indicator
        const generatingMsg = document.getElementById('generatingMsg');
        if (generatingMsg) generatingMsg.remove();

        // Create image URL from blob
        let imageUrl;
        if (result instanceof Blob) {
            imageUrl = URL.createObjectURL(result);
        } else if (result.src) {
            imageUrl = result.src;
        } else if (typeof result === 'string') {
            imageUrl = result;
        }

        // Add image message
        addImageMessage(imageUrl, prompt);
        showToast('Đã tạo ảnh thành công!', 'success');

    } catch (error) {
        console.error('Image generation error:', error);
        const generatingMsg = document.getElementById('generatingMsg');
        if (generatingMsg) generatingMsg.remove();

        addMessage(`Không thể tạo ảnh: ${error.message}. Vui lòng thử lại.`, 'bot');
        showToast('Lỗi tạo ảnh: ' + error.message, 'error');
    } finally {
        isGeneratingImage = false;
    }
}

function addImageMessage(imageUrl, prompt) {
    const time = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });

    const messageHTML = `
        <div class="message bot-message">
            <div class="message-avatar">🤖</div>
            <div class="message-content">
                <div class="message-bubble">
                    <p>Đây là ảnh AI được tạo từ: "${prompt}"</p>
                    <img src="${imageUrl}" alt="AI Generated: ${prompt}" class="message-image" onclick="openImageModal('${imageUrl}')">
                </div>
                <span class="message-time">${time}</span>
            </div>
        </div>
    `;

    chatMessages.insertAdjacentHTML('beforeend', messageHTML);
    scrollToBottom();

    chatHistory.push({ role: 'bot', content: `[Ảnh AI: ${prompt}]`, time, imageUrl });
    saveChatHistory();
}

// ==================== IMAGE MODAL ====================
function openImageModal(imageUrl) {
    modalImage.src = imageUrl;
    modalDownload.href = imageUrl;
    imageModal.classList.add('active');
}

function closeImageModal() {
    imageModal.classList.remove('active');
}

// ==================== CHAT ====================
async function sendMessage() {
    const message = messageInput.value.trim();
    if ((!message && selectedFiles.length === 0) || isLoading) return;

    // Check if this is an image generation request
    if (message && isImageGenerationRequest(message) && selectedFiles.length === 0) {
        messageInput.value = '';
        const prompt = extractImagePrompt(message);
        await generateImage(prompt);
        return;
    }

    // Process files if any
    let fileContext = '';
    let imageUrls = [];

    if (selectedFiles.length > 0) {
        for (const file of selectedFiles) {
            if (file.type.startsWith('image/')) {
                imageUrls.push(URL.createObjectURL(file));
                // Try OCR on images
                const ocrText = await extractTextFromImage(file);
                if (ocrText) {
                    fileContext += `\n[Đọc từ ảnh "${file.name}"]: ${ocrText}`;
                } else {
                    fileContext += `\n[Ảnh đính kèm: ${file.name}]`;
                }
            } else if (file.type === 'text/plain') {
                const text = await file.text();
                fileContext += `\n[Nội dung file "${file.name}"]: ${text}`;
            } else {
                fileContext += `\n[File đính kèm: ${file.name}]`;
            }
        }
    }

    // Build message with files
    const fullMessage = message + fileContext;

    // Add user message with images
    addMessageWithFiles(message, 'user', imageUrls, selectedFiles);

    messageInput.value = '';
    autoResizeTextarea();
    clearFiles();

    // Show typing indicator
    setLoading(true);

    try {
        const response = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: fullMessage,
                history: chatHistory.slice(-10).map(m => `${m.role}: ${m.content}`).join('\n')
            })
        });

        const data = await response.json();

        if (data.reply) {
            addMessage(data.reply, 'bot');
        } else if (data.error) {
            addMessage(`Lỗi: ${data.error}`, 'bot');
        }
    } catch (error) {
        console.error('Error sending message:', error);
        addMessage('Không thể kết nối server. Vui lòng kiểm tra kết nối.', 'bot');
    } finally {
        setLoading(false);
    }
}

function addMessage(content, role) {
    const time = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
    const avatar = role === 'bot' ? '🤖' : '👤';

    const messageHTML = `
        <div class="message ${role}-message">
            <div class="message-avatar">${avatar}</div>
            <div class="message-content">
                <div class="message-bubble">
                    ${formatMessage(content)}
                </div>
                <span class="message-time">${time}</span>
            </div>
        </div>
    `;

    chatMessages.insertAdjacentHTML('beforeend', messageHTML);
    scrollToBottom();

    chatHistory.push({ role, content, time });
    if (chatHistory.length > MAX_HISTORY) {
        chatHistory = chatHistory.slice(-MAX_HISTORY);
    }
    saveChatHistory();
}

function addMessageWithFiles(content, role, imageUrls = [], files = []) {
    const time = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
    const avatar = role === 'bot' ? '🤖' : '👤';

    let imagesHTML = imageUrls.map(url =>
        `<img src="${url}" alt="Uploaded" class="message-image" onclick="openImageModal('${url}')">`
    ).join('');

    let filesHTML = files.filter(f => !f.type.startsWith('image/')).map(f =>
        `<span class="message-file">${getFileIcon(f.name)} ${f.name}</span>`
    ).join('');

    const messageHTML = `
        <div class="message ${role}-message">
            <div class="message-avatar">${avatar}</div>
            <div class="message-content">
                <div class="message-bubble">
                    ${content ? formatMessage(content) : ''}
                    ${imagesHTML}
                    ${filesHTML ? `<div class="message-files">${filesHTML}</div>` : ''}
                </div>
                <span class="message-time">${time}</span>
            </div>
        </div>
    `;

    chatMessages.insertAdjacentHTML('beforeend', messageHTML);
    scrollToBottom();

    chatHistory.push({ role, content: content + (files.length ? ` [+${files.length} files]` : ''), time });
    saveChatHistory();
}

function formatMessage(content) {
    return content
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code>$1</code>');
}

function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function setLoading(loading) {
    isLoading = loading;
    sendBtn.disabled = loading;
    typingIndicator.classList.toggle('active', loading);
    if (loading) scrollToBottom();
}

// ==================== STORAGE ====================
function saveChatHistory() {
    try {
        localStorage.setItem('bongx_chat_history', JSON.stringify(chatHistory));
    } catch (e) {
        console.error('Error saving chat history:', e);
    }
}

function loadChatHistory() {
    try {
        const saved = localStorage.getItem('bongx_chat_history');
        if (saved) {
            chatHistory = JSON.parse(saved);
            const recentMessages = chatHistory.slice(-10);
            recentMessages.forEach(msg => {
                const avatar = msg.role === 'bot' ? '🤖' : '👤';
                const messageHTML = `
                    <div class="message ${msg.role}-message">
                        <div class="message-avatar">${avatar}</div>
                        <div class="message-content">
                            <div class="message-bubble">
                                ${formatMessage(msg.content)}
                            </div>
                            <span class="message-time">${msg.time || ''}</span>
                        </div>
                    </div>
                `;
                chatMessages.insertAdjacentHTML('beforeend', messageHTML);
            });
            scrollToBottom();
        }
    } catch (e) {
        console.error('Error loading chat history:', e);
    }
}

function clearChatHistory() {
    chatHistory = [];
    localStorage.removeItem('bongx_chat_history');
    const welcomeMessage = chatMessages.querySelector('.bot-message');
    chatMessages.innerHTML = '';
    if (welcomeMessage) {
        chatMessages.appendChild(welcomeMessage);
    } else {
        addMessage('Xin chào! Mình là Bóng X AI 🎉 Hãy chat với mình nhé!', 'bot');
    }
    showToast('Đã xóa lịch sử chat', 'success');
}

// ==================== SETTINGS ====================
function loadSettings() {
    const darkMode = localStorage.getItem('bongx_dark_mode');
    if (darkMode === 'false') {
        document.body.classList.add('light-mode');
        darkModeToggle.checked = false;
    }
}

function toggleDarkMode() {
    const isLight = document.body.classList.toggle('light-mode');
    localStorage.setItem('bongx_dark_mode', !isLight);
}

// ==================== SIDEBAR ====================
function openSidebar() {
    sidebar.classList.add('open');
    if (sidebarOverlay) sidebarOverlay.classList.add('active');
}

function closeSidebar() {
    sidebar.classList.remove('open');
    if (sidebarOverlay) sidebarOverlay.classList.remove('active');
}

// ==================== TOAST ====================
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    toastContainer.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// ==================== TEXTAREA AUTO-RESIZE ====================
function autoResizeTextarea() {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
}

// ==================== EVENT LISTENERS ====================
function setupEventListeners() {
    // Send message
    sendBtn.addEventListener('click', sendMessage);
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    messageInput.addEventListener('input', autoResizeTextarea);

    // File upload
    attachBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', handleFileSelect);

    // Image generation button
    generateBtn.addEventListener('click', () => {
        const prompt = window.prompt('Mô tả ảnh bạn muốn tạo:', 'một con mèo dễ thương');
        if (prompt) {
            generateImage(prompt);
        }
    });

    // Image modal
    modalOverlay.addEventListener('click', closeImageModal);
    modalClose.addEventListener('click', closeImageModal);
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeImageModal();
    });

    // Settings
    darkModeToggle.addEventListener('change', toggleDarkMode);
    clearHistoryBtn.addEventListener('click', clearChatHistory);

    // Sidebar
    menuBtn.addEventListener('click', openSidebar);
    sidebarClose.addEventListener('click', closeSidebar);
    if (sidebarOverlay) sidebarOverlay.addEventListener('click', closeSidebar);

    // Close sidebar on outside click
    document.addEventListener('click', (e) => {
        if (sidebar.classList.contains('open') &&
            !sidebar.contains(e.target) &&
            !menuBtn.contains(e.target)) {
            closeSidebar();
        }
    });

    // Drag and drop for files
    const inputArea = document.querySelector('.input-area');
    inputArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        inputArea.style.borderColor = 'var(--accent-primary)';
    });
    inputArea.addEventListener('dragleave', () => {
        inputArea.style.borderColor = '';
    });
    inputArea.addEventListener('drop', (e) => {
        e.preventDefault();
        inputArea.style.borderColor = '';
        const files = Array.from(e.dataTransfer.files);
        files.forEach(file => {
            if (file.size <= 10 * 1024 * 1024) {
                selectedFiles.push(file);
            }
        });
        updateFilePreview();
    });
}

// ==================== VISUAL EFFECTS ====================
function setupVisualEffects() {
    // Custom Cursor
    const cursor = document.getElementById('customCursor');
    if (matchMedia('(pointer:fine)').matches) {
        document.addEventListener('mousemove', (e) => {
            cursor.style.left = e.clientX + 'px';
            cursor.style.top = e.clientY + 'px';
        });

        document.querySelectorAll('a, button, input, textarea, .message-image, .profile-item').forEach(el => {
            el.addEventListener('mouseenter', () => cursor.classList.add('hover'));
            el.addEventListener('mouseleave', () => cursor.classList.remove('hover'));
        });

        // Dynamic binding for future elements
        document.addEventListener('mouseover', (e) => {
            if (e.target.closest('a, button, input, textarea, .message-image, .profile-item')) {
                cursor.classList.add('hover');
            } else {
                cursor.classList.remove('hover');
            }
        });
    } else {
        cursor.style.display = 'none';
    }

    // Ripple Effect
    document.addEventListener('click', (e) => {
        const ripple = document.createElement('div');
        ripple.className = 'ripple';
        ripple.style.left = e.pageX + 'px';
        ripple.style.top = e.pageY + 'px';
        document.body.appendChild(ripple);

        setTimeout(() => {
            ripple.remove();
        }, 600);
    });

    // 3D Tilt Effect for Profile Items
    const profileItems = document.querySelectorAll('.profile-item');
    profileItems.forEach(item => {
        item.classList.add('tilt-card');
        item.addEventListener('mousemove', handleTilt);
        item.addEventListener('mouseleave', resetTilt);
    });
}

function handleTilt(e) {
    const el = e.currentTarget;
    const rect = el.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const centerX = rect.width / 2;
    const centerY = rect.height / 2;

    const rotateX = ((y - centerY) / centerY) * -10; // Max 10deg rotation
    const rotateY = ((x - centerX) / centerX) * 10;

    el.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale(1.02)`;
}

function resetTilt(e) {
    e.currentTarget.style.transform = 'perspective(1000px) rotateX(0) rotateY(0) scale(1)';
}
