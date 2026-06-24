// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  let conversationHistory = [];

  const chatForm = document.querySelector("#chatForm");
  const userInput = document.querySelector("#userInput");
  const chatMessages = document.querySelector("#chatMessages");
  const newChatBtn = document.querySelector("#newChatBtn");
  const clearHistoryBtn = document.querySelector("#clearHistoryBtn");

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

      // Add wordplay suggestions
      addWordplaySuggestions(message);

      // Show action steps if available
      if (data.answer.action_steps && data.answer.action_steps.length > 0) {
        addActionSteps(data.answer.action_steps);
      }
    } catch (error) {
      typingIndicator.remove();
      addMessage("assistant", `Error: ${error.message}`);
    }
  });

  function addWordplaySuggestions(query) {
    const suggestionsDiv = document.createElement("div");
    suggestionsDiv.className = "wordplay-suggestions";
    
    const sportsTerms = [
      "slam dunk", "hat trick", "home run", "touchdown", "goal", 
      "ace", "birdie", "bogey", "par", "strike", "spare",
      "penalty", "foul", "offside", "timeout", "overtime",
      "quarterback", "striker", "pitcher", "goalkeeper", "defender"
    ];
    
    const relatedTerms = sportsTerms.filter(term => 
      query.toLowerCase().includes(term.split(" ")[0]) || 
      term.split(" ").some(word => query.toLowerCase().includes(word))
    );
    
    if (relatedTerms.length > 0) {
      const suggestionsTitle = document.createElement("div");
      suggestionsTitle.className = "suggestions-title";
      suggestionsTitle.textContent = "Related terms:";
      suggestionsDiv.appendChild(suggestionsTitle);
      
      relatedTerms.forEach(term => {
        const suggestion = document.createElement("span");
        suggestion.className = "suggestion-tag";
        suggestion.textContent = term;
        suggestion.addEventListener("click", () => {
          userInput.value = term;
          chatForm.dispatchEvent(new Event("submit"));
        });
        suggestionsDiv.appendChild(suggestion);
      });
      
      chatMessages.appendChild(suggestionsDiv);
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }
  }

  newChatBtn.addEventListener("click", () => {
    conversationHistory = [];
    chatMessages.innerHTML = `
      <div class="message assistant">
        <div class="message-content">
          <p>Hello! I'm Sportly, your AI-powered sports prediction assistant. I can help you with predictions, match analysis, player stats, and information about all sports including football, basketball, cricket, tennis, and more. Ask me about upcoming games, team performance, or any sports-related questions!</p>
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
            <p>Hello! I'm Sportly, your AI-powered sports prediction assistant. I can help you with predictions, match analysis, player stats, and information about all sports including football, basketball, cricket, tennis, and more. Ask me about upcoming games, team performance, or any sports-related questions!</p>
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

  function addWebResults(results) {
    const resultsDiv = document.createElement("div");
    resultsDiv.className = "message assistant";
    resultsDiv.innerHTML = `
      <div class="message-content">
        <p class="web-results-label">Web Search Results:</p>
        <div class="web-results-list">
          ${results.map((result) => `
            <div class="web-result-item">
              <a href="${escapeHtml(result.url)}" target="_blank" class="web-result-title">${escapeHtml(result.title)}</a>
              <p class="web-result-snippet">${escapeHtml(result.snippet)}</p>
              <small class="web-result-url">${escapeHtml(result.url)}</small>
            </div>
          `).join("")}
        </div>
      </div>
    `;
    chatMessages.appendChild(resultsDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
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
});
