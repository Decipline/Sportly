const chatForm = document.querySelector("#chatForm");
const userInput = document.querySelector("#userInput");
const chatMessages = document.querySelector("#chatMessages");
const dbStatus = document.querySelector("#dbStatus");
const newChatBtn = document.querySelector("#newChatBtn");
const clearHistoryBtn = document.querySelector("#clearHistoryBtn");

let conversationHistory = [];

loadHealth();

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = userInput.value.trim();
  if (!message) return;

  // Add user message to chat
  addMessage("user", message);
  userInput.value = "";
  userInput.style.height = "auto";

  // Add to conversation history
  conversationHistory.push({ role: "user", content: message });

  // Show typing indicator
  const typingIndicator = addTypingIndicator();

  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query: message,
        conversation_history: conversationHistory,
      }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Request failed.");
    }

    // Remove typing indicator
    typingIndicator.remove();

    // Add assistant response
    const assistantMessage = data.answer.direct_answer;
    addMessage("assistant", assistantMessage);

    // Add to conversation history
    conversationHistory.push({ role: "assistant", content: assistantMessage });

    // Show sources if available
    if (data.answer.sources && data.answer.sources.length > 0) {
      addSources(data.answer.sources);
    }

    // Show action steps if available
    if (data.answer.action_steps && data.answer.action_steps.length > 0) {
      addActionSteps(data.answer.action_steps);
    }
  } catch (error) {
    typingIndicator.remove();
    addMessage("assistant", `Error: ${error.message}`);
  }
});

newChatBtn.addEventListener("click", () => {
  conversationHistory = [];
  chatMessages.innerHTML = `
    <div class="message assistant">
      <div class="message-content">
        <p>Hello! I'm your AI assistant. I can help you with coding, writing, research, and general questions. How can I assist you today?</p>
      </div>
    </div>
  `;
});

clearHistoryBtn.addEventListener("click", () => {
  if (confirm("Are you sure you want to clear the conversation history?")) {
    conversationHistory = [];
    chatMessages.innerHTML = `
      <div class="message assistant">
        <div class="message-content">
          <p>Hello! I'm your AI assistant. I can help you with coding, writing, research, and general questions. How can I assist you today?</p>
        </div>
      </div>
    `;
  }
});

// Auto-resize textarea
userInput.addEventListener("input", () => {
  userInput.style.height = "auto";
  userInput.style.height = userInput.scrollHeight + "px";
});

// Send message on Enter (Shift+Enter for new line)
userInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    chatForm.dispatchEvent(new Event("submit"));
  }
});

function addMessage(role, content) {
  const messageDiv = document.createElement("div");
  messageDiv.className = `message ${role}`;
  messageDiv.innerHTML = `
    <div class="message-content">
      <p>${escapeHtml(content)}</p>
    </div>
  `;
  chatMessages.appendChild(messageDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return messageDiv;
}

function addTypingIndicator() {
  const typingDiv = document.createElement("div");
  typingDiv.className = "message assistant typing";
  typingDiv.innerHTML = `
    <div class="message-content">
      <div class="typing-indicator">
        <span></span>
        <span></span>
        <span></span>
      </div>
    </div>
  `;
  chatMessages.appendChild(typingDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return typingDiv;
}

function addSources(sources) {
  const sourcesDiv = document.createElement("div");
  sourcesDiv.className = "message assistant";
  sourcesDiv.innerHTML = `
    <div class="message-content">
      <p class="sources-label">Sources:</p>
      <ul>
        ${sources.map((source) => `<li>${escapeHtml(source)}</li>`).join("")}
      </ul>
    </div>
  `;
  chatMessages.appendChild(sourcesDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addActionSteps(steps) {
  const stepsDiv = document.createElement("div");
  stepsDiv.className = "message assistant";
  stepsDiv.innerHTML = `
    <div class="message-content">
      <p class="steps-label">Action Steps:</p>
      <ol>
        ${steps.map((step) => `<li>${escapeHtml(step)}</li>`).join("")}
      </ol>
    </div>
  `;
  chatMessages.appendChild(stepsDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function loadHealth() {
  try {
    const data = await fetchJson("/api/health");
    if (data.database.enabled) {
      dbStatus.textContent = data.openai.enabled ? "Online + OpenAI" : "Online";
      dbStatus.className = "status-pill connected";
    } else {
      dbStatus.textContent = "Demo mode";
      dbStatus.className = "status-pill offline";
    }
  } catch {
    dbStatus.textContent = "Server offline";
    dbStatus.className = "status-pill offline";
  }
}

async function fetchJson(url) {
  const response = await fetch(url);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Request failed.");
  }
  return data;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
