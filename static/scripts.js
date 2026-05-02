/* scripts.js — Agentic AI frontend */
"use strict";

// ─── DOM references ───────────────────────────────────────────
const taskInput      = document.getElementById("task-input");
const runBtn         = document.getElementById("run-btn");
const runIcon        = document.getElementById("run-icon");
const stepsFeed      = document.getElementById("steps-feed");
const emptyState     = document.getElementById("empty-state");
const statsBar       = document.getElementById("stats-bar");
const statStepsVal   = document.getElementById("stat-steps-val");
const statToolsVal   = document.getElementById("stat-tools-val");
const statTimeVal    = document.getElementById("stat-time-val");
const clearRunBtn    = document.getElementById("clear-run-btn");
const apiKeyInput    = document.getElementById("api-key-input");
const exampleItems   = document.querySelectorAll(".example-item");
const toolItems      = document.querySelectorAll(".tool-item");

// ─── State ───────────────────────────────────────────────────
let isRunning    = false;
let stepCount    = 0;
let toolCount    = 0;
let startTime    = null;
let timerHandle  = null;
let currentEs    = null;

// ─── Auto-resize textarea ─────────────────────────────────────
taskInput.addEventListener("input", () => {
  taskInput.style.height = "auto";
  taskInput.style.height = Math.min(taskInput.scrollHeight, 180) + "px";
});

// ─── Enter to submit (Shift+Enter = newline) ──────────────────
taskInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    if (!isRunning) startRun();
  }
});

// ─── Run button ───────────────────────────────────────────────
runBtn.addEventListener("click", () => {
  if (isRunning) return;
  startRun();
});

// ─── Clear button ─────────────────────────────────────────────
clearRunBtn.addEventListener("click", clearWorkspace);

// ─── Example tasks ────────────────────────────────────────────
exampleItems.forEach((el) => {
  const activate = () => {
    if (isRunning) return;
    taskInput.value = el.textContent.trim();
    taskInput.style.height = "auto";
    taskInput.style.height = Math.min(taskInput.scrollHeight, 180) + "px";
    taskInput.focus();
  };
  el.addEventListener("click", activate);
  el.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") activate(); });
});

// ─── Main: start the agentic run ─────────────────────────────
function startRun() {
  const task = taskInput.value.trim();
  if (!task) return;

  const apiKey = apiKeyInput ? apiKeyInput.value.trim() : "";

  clearWorkspace();
  hideEmpty();
  setRunning(true);
  startTimer();

  // Optimistic "thinking" card
  appendThinkingCard();

  currentEs = null;

  fetch("/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task, api_key: apiKey }),
  })
    .then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      // Remove the optimistic thinking card once real data starts
      let firstEvent = true;

      function pump() {
        return reader.read().then(({ done, value }) => {
          if (done) {
            finishRun();
            return;
          }
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n\n");
          buffer = lines.pop(); // keep incomplete chunk

          lines.forEach((line) => {
            if (!line.startsWith("data:")) return;
            const raw = line.slice(5).trim();
            if (!raw) return;
            try {
              const event = JSON.parse(raw);
              if (firstEvent) {
                removeThinkingCard();
                firstEvent = false;
              }
              handleEvent(event);
            } catch (_) { /* ignore malformed */ }
          });

          return pump();
        });
      }
      return pump();
    })
    .catch((err) => {
      removeThinkingCard();
      appendErrorCard(`Connection error: ${err.message}`);
      finishRun();
    });
}

// ─── Handle SSE events ────────────────────────────────────────
function handleEvent(event) {
  stepCount++;
  statStepsVal.textContent = stepCount;

  switch (event.type) {
    case "thought":
      appendThoughtCard(event.content);
      break;
    case "tool_call":
      toolCount++;
      statToolsVal.textContent = toolCount;
      highlightTool(event.tool, true);
      appendToolCallCard(event.tool, event.args);
      break;
    case "tool_result":
      highlightTool(event.tool, false);
      appendToolResultCard(event.tool, event.content);
      break;
    case "answer":
      appendAnswerCard(event.content);
      break;
    case "error":
      appendErrorCard(event.content);
      break;
    case "done":
      finishRun();
      break;
    default:
      break;
  }
  scrollFeedToBottom();
}

// ─── Card builders ────────────────────────────────────────────
function appendThinkingCard() {
  const card = makeCard("thought", "thinking-placeholder");
  const header = makeHeader("thought", "💭 Thinking");
  const body = document.createElement("div");
  body.className = "step-body";
  body.innerHTML = `<span class="step-text">Starting up<span class="thinking-dots"><span></span><span></span><span></span></span></span>`;
  card.appendChild(header);
  card.appendChild(body);
  stepsFeed.appendChild(card);
}

function removeThinkingCard() {
  const card = document.getElementById("thinking-placeholder");
  if (card) card.remove();
}

function appendThoughtCard(content) {
  const card = makeCard("thought");
  card.appendChild(makeHeader("thought", "💭 Thought"));
  const body = document.createElement("div");
  body.className = "step-body";
  const text = document.createElement("div");
  text.className = "step-text";
  text.innerHTML = renderMarkdown(content);
  body.appendChild(text);
  card.appendChild(body);
  stepsFeed.appendChild(card);
}

function appendToolCallCard(tool, args) {
  const card = makeCard("tool-call");
  const header = makeHeader("tool-call", "⚡ Tool Call");
  const toolLabel = document.createElement("span");
  toolLabel.className = "step-tool-name";
  toolLabel.textContent = tool;
  header.appendChild(toolLabel);
  card.appendChild(header);

  const body = document.createElement("div");
  body.className = "step-body";
  if (args && Object.keys(args).length > 0) {
    const pre = document.createElement("pre");
    pre.className = "tool-args";
    pre.textContent = JSON.stringify(args, null, 2);
    body.appendChild(pre);
  }
  card.appendChild(body);
  stepsFeed.appendChild(card);
}

function appendToolResultCard(tool, content) {
  const card = makeCard("tool-result");
  const header = makeHeader("tool-result", "✅ Result");
  const toolLabel = document.createElement("span");
  toolLabel.className = "step-tool-name";
  toolLabel.textContent = tool;
  header.appendChild(toolLabel);
  card.appendChild(header);

  const body = document.createElement("div");
  body.className = "step-body";
  const pre = document.createElement("pre");
  pre.className = "tool-result-text";
  pre.textContent = content;
  body.appendChild(pre);
  card.appendChild(body);
  stepsFeed.appendChild(card);
}

function appendAnswerCard(content) {
  const card = makeCard("answer");
  card.appendChild(makeHeader("answer", "✦ Final Answer"));
  const body = document.createElement("div");
  body.className = "step-body";
  const text = document.createElement("div");
  text.className = "step-text";
  text.innerHTML = renderMarkdown(content);

  const copyBtn = document.createElement("button");
  copyBtn.className = "copy-answer-btn";
  copyBtn.id = "copy-answer-btn";
  copyBtn.textContent = "⎘ Copy answer";
  copyBtn.addEventListener("click", () => {
    navigator.clipboard.writeText(content).then(() => {
      copyBtn.textContent = "✓ Copied!";
      setTimeout(() => { copyBtn.textContent = "⎘ Copy answer"; }, 2000);
    });
  });

  body.appendChild(text);
  body.appendChild(copyBtn);
  card.appendChild(body);
  stepsFeed.appendChild(card);
}

function appendErrorCard(content) {
  const card = makeCard("error");
  card.appendChild(makeHeader("error", "⚠ Error"));
  const body = document.createElement("div");
  body.className = "step-body";
  const text = document.createElement("div");
  text.className = "step-text";
  text.textContent = content;
  body.appendChild(text);
  card.appendChild(body);
  stepsFeed.appendChild(card);
}

// ─── Helpers ─────────────────────────────────────────────────
function makeCard(type, id) {
  const card = document.createElement("div");
  card.className = `step-card type-${type}`;
  if (id) card.id = id;
  return card;
}

function makeHeader(type, label) {
  const header = document.createElement("div");
  header.className = "step-header";
  const chip = document.createElement("span");
  chip.className = "step-chip";
  chip.textContent = label;
  header.appendChild(chip);
  return header;
}

function highlightTool(toolName, active) {
  toolItems.forEach((item) => {
    if (item.dataset.tool === toolName) {
      if (active) item.classList.add("active");
      else item.classList.remove("active");
    }
  });
}

function scrollFeedToBottom() {
  const ws = document.querySelector(".workspace");
  if (ws) ws.scrollTop = ws.scrollHeight;
}

function clearWorkspace() {
  stepsFeed.innerHTML = "";
  stepCount = 0; toolCount = 0;
  statStepsVal.textContent = "0";
  statToolsVal.textContent = "0";
  statTimeVal.textContent  = "0s";
  statsBar.style.display = "none";
  toolItems.forEach((el) => el.classList.remove("active"));
}

function hideEmpty() {
  emptyState.classList.add("hidden");
}
function showEmpty() {
  emptyState.classList.remove("hidden");
}

function setRunning(val) {
  isRunning = val;
  runBtn.disabled = val;
  taskInput.disabled = val;
  if (val) {
    runIcon.textContent = "◌";
    runBtn.classList.add("loading");
  } else {
    runIcon.textContent = "▶";
    runBtn.classList.remove("loading");
  }
}

function startTimer() {
  startTime = Date.now();
  statsBar.style.display = "flex";
  timerHandle = setInterval(() => {
    const s = ((Date.now() - startTime) / 1000).toFixed(1);
    statTimeVal.textContent = `${s}s`;
  }, 200);
}

function finishRun() {
  clearInterval(timerHandle);
  setRunning(false);
  taskInput.disabled = false;
  if (stepCount === 0) showEmpty();
}

// ─── Simple markdown renderer ─────────────────────────────────
function renderMarkdown(text) {
  if (!text) return "";
  return text
    // Code blocks
    .replace(/```[\w]*\n?([\s\S]*?)```/g, (_, code) =>
      `<pre class="tool-args">${escHtml(code.trim())}</pre>`)
    // Inline code
    .replace(/`([^`]+)`/g, (_, c) => `<code>${escHtml(c)}</code>`)
    // Bold
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    // Italic
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    // Headers
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm,  "<h2>$1</h2>")
    .replace(/^# (.+)$/gm,   "<h1>$1</h1>")
    // HR
    .replace(/^---$/gm, "<hr />")
    // Bullet points
    .replace(/^[-*] (.+)$/gm, "<li>$1</li>")
    .replace(/(<li>.*<\/li>\n?)+/g, (m) => `<ul>${m}</ul>`)
    // Numbered lists
    .replace(/^\d+\. (.+)$/gm, "<li>$1</li>")
    // URLs
    .replace(/(https?:\/\/[^\s<>"]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>')
    // Paragraphs
    .replace(/\n{2,}/g, "</p><p>")
    .replace(/\n/g, "<br />");
}

function escHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
