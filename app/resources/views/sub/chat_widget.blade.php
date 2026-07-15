{{-- Databook Chat Widget --}}
<style>
    #chatbot-widget {
        position: fixed;
        bottom: 20px;
        right: 20px;
        z-index: 9999;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    #chatbot-toggle {
        width: 70px;
        height: 70px;
        border-radius: 50%;
        background: linear-gradient(135deg, #F5A623 0%, #D4790E 100%);
        border: 3px solid white;
        cursor: pointer;
        box-shadow: 0 4px 15px rgba(212, 121, 14, 0.4);
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0;
        overflow: hidden;
        transition: transform 0.2s, box-shadow 0.2s;
    }

    #chatbot-toggle:hover {
        transform: scale(1.08);
        box-shadow: 0 6px 20px rgba(212, 121, 14, 0.5);
    }

    #chatbot-toggle img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }

    #chatbot-window {
        display: none;
        position: absolute;
        bottom: 70px;
        right: 0;
        width: 380px;
        height: 500px;
        background: white;
        border-radius: 16px;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
        flex-direction: column;
        overflow: hidden;
    }

    #chatbot-window.open {
        display: flex;
    }

    #chatbot-header {
        background: linear-gradient(135deg, #162E51 0%, #0B1D2E 100%);
        color: white;
        padding: 16px;
        font-weight: 600;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    #chatbot-header button {
        background: none;
        border: none;
        color: white;
        font-size: 20px;
        cursor: pointer;
        opacity: 0.8;
    }

    #chatbot-header button:hover {
        opacity: 1;
    }

    #chatbot-messages {
        flex: 1;
        overflow-y: auto;
        padding: 16px;
        background: #f8f9fa;
    }

    .chat-message {
        margin-bottom: 12px;
        max-width: 85%;
    }

    .chat-message.user {
        margin-left: auto;
    }

    .chat-message .bubble {
        padding: 10px 14px;
        border-radius: 16px;
        font-size: 14px;
        line-height: 1.4;
    }

    .chat-message.user .bubble {
        background: linear-gradient(135deg, #162E51 0%, #0B1D2E 100%);
        color: white;
        border-bottom-right-radius: 4px;
    }

    .chat-message.assistant .bubble {
        background: white;
        color: #333;
        border: 1px solid #e0e0e0;
        border-bottom-left-radius: 4px;
    }

    .chat-message.assistant .bubble strong {
        color: #162E51;
    }

    #chatbot-input-area {
        padding: 12px;
        border-top: 1px solid #e0e0e0;
        background: white;
        display: flex;
        gap: 8px;
    }

    #chatbot-input {
        flex: 1;
        padding: 10px 14px;
        border: 1px solid #e0e0e0;
        border-radius: 20px;
        font-size: 14px;
        outline: none;
    }

    #chatbot-input:focus {
        border-color: #162E51;
    }

    #chatbot-send {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: linear-gradient(135deg, #162E51 0%, #0B1D2E 100%);
        border: none;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    #chatbot-send:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }

    #chatbot-send svg {
        width: 18px;
        height: 18px;
        fill: white;
    }

    .typing-indicator {
        display: flex;
        gap: 4px;
        padding: 10px 14px;
    }

    .typing-indicator span {
        width: 8px;
        height: 8px;
        background: #162E51;
        border-radius: 50%;
        animation: typing 1.4s ease-in-out infinite;
    }

    .typing-indicator span:nth-child(2) {
        animation-delay: 0.2s;
    }

    .typing-indicator span:nth-child(3) {
        animation-delay: 0.4s;
    }

    @keyframes typing {
        0%, 60%, 100% {
            transform: translateY(0);
        }
        30% {
            transform: translateY(-8px);
        }
    }
</style>

<div id="chatbot-widget">
    <div id="chatbot-window">
        <div id="chatbot-header">
            <span>
                <img src="/img/chat-squirrel.png" alt="" style="width: 24px; height: 24px; border-radius: 50%; vertical-align: middle; margin-right: 8px;">
                Ask about NYC Government
            </span>
            <button onclick="toggleChat()" title="Close">&times;</button>
        </div>
        <div id="chatbot-messages">
            <div class="chat-message assistant">
                <div class="bubble">
                    Hi! I can help you explore NYC government data. Try asking:
                    <br><br>
                    • "How many capital projects does Parks have?"<br>
                    • "Search for Health department"<br>
                    • "Find civil service titles for engineer"
                </div>
            </div>
        </div>
        <div id="chatbot-input-area">
            <input type="text" id="chatbot-input" placeholder="Ask about agencies, projects, people..."
                onkeypress="if(event.key==='Enter')sendChat()">
            <button id="chatbot-send" onclick="sendChat()">
                <svg viewBox="0 0 24 24">
                    <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
                </svg>
            </button>
        </div>
    </div>
    <button id="chatbot-toggle" onclick="toggleChat()" title="Chat with AI">
        <img src="/img/chat-squirrel.png" alt="Chat">
    </button>
</div>

<script>
    const chatHistory = [];

    function toggleChat() {
        const window = document.getElementById('chatbot-window');
        window.classList.toggle('open');
        if (window.classList.contains('open')) {
            document.getElementById('chatbot-input').focus();
        }
    }

    function addMessage(text, role) {
        const messages = document.getElementById('chatbot-messages');
        const div = document.createElement('div');
        div.className = `chat-message ${role}`;

        // Regular message - simple markdown-like formatting
        let formatted = text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br>');

        div.innerHTML = `<div class="bubble">${formatted}</div>`;
        messages.appendChild(div);
        messages.scrollTop = messages.scrollHeight;
    }

    function showTyping() {
        const messages = document.getElementById('chatbot-messages');
        const div = document.createElement('div');
        div.className = 'chat-message assistant';
        div.id = 'typing-indicator';
        div.innerHTML = '<div class="bubble"><div class="typing-indicator"><span></span><span></span><span></span></div></div>';
        messages.appendChild(div);
        messages.scrollTop = messages.scrollHeight;
    }

    function hideTyping() {
        const el = document.getElementById('typing-indicator');
        if (el) el.remove();
    }

    async function sendChat() {
        const input = document.getElementById('chatbot-input');
        const sendBtn = document.getElementById('chatbot-send');
        const message = input.value.trim();

        if (!message) return;

        // Add user message
        addMessage(message, 'user');
        chatHistory.push({ role: 'user', content: message });
        input.value = '';
        sendBtn.disabled = true;

        showTyping();

        try {
            // Use the Databook API directly via the Laravel backend proxy
            const response = await fetch('{{ env("DATABOOK_API_URL", "https://api.databook.nyc") }}/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message, history: chatHistory.slice(-10) })
            });

            hideTyping();

            if (!response.ok) {
                throw new Error('Chat request failed');
            }

            const data = await response.json();

            if (data.error) {
                addMessage('Sorry, something went wrong. Please try again.', 'assistant');
            } else {
                addMessage(data.response, 'assistant');
                chatHistory.push({ role: 'assistant', content: data.response });
            }
        } catch (error) {
            hideTyping();
            addMessage('Sorry, I couldn\'t connect. Please try again.', 'assistant');
            console.error('Chat error:', error);
        }

        sendBtn.disabled = false;
        input.focus();
    }
</script>
