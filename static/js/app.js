const socket = io();

const el = {
  statusDot: document.getElementById('statusDot'),
  statusText: document.getElementById('statusText'),
  powerBtn: document.getElementById('powerBtn'),
  micBtn: document.getElementById('micBtn'),
  textInput: document.getElementById('textInput'),
  console: document.getElementById('console'),
  toolLog: document.getElementById('toolLog'),
  timeline: document.getElementById('timeline'),
  coreCaption: document.getElementById('coreCaption'),
  coreCenter: document.querySelector('.core-center'),
  pulseBars: document.getElementById('pulseBars'),
  cpuRing: document.getElementById('cpuRing'),
  ramRing: document.getElementById('ramRing'),
  cpuVal: document.getElementById('cpuVal'),
  ramVal: document.getElementById('ramVal'),
  gearBtn: document.getElementById('gearBtn'),
  settingsOverlay: document.getElementById('settingsOverlay'),
  apiKeyInput: document.getElementById('apiKeyInput'),
  modalMaskedNote: document.getElementById('modalMaskedNote'),
  modalError: document.getElementById('modalError'),
  modalSave: document.getElementById('modalSave'),
  modalCancel: document.getElementById('modalCancel'),
  sendBtn: document.getElementById('sendBtn'),
  lensBtn: document.getElementById('lensBtn'),
  screenshotPreview: document.getElementById('screenshotPreview'),
  screenshotImg: document.getElementById('screenshotImg'),
  screenshotClose: document.getElementById('screenshotClose'),
  gamesHubBtn: document.getElementById('gamesHubBtn'),
  personaSelect: document.getElementById('personaSelect'),
  voiceModeSelect: document.getElementById('voiceModeSelect'),
  emailAddressInput: document.getElementById('emailAddressInput'),
  emailPasswordInput: document.getElementById('emailPasswordInput'),
  emailProviderSelect: document.getElementById('emailProviderSelect'),
};

let engineOn = false;
let keyConfigured = false;
const RING_CIRC = 314; // 2 * PI * 50

function ts() {
  return new Date().toLocaleTimeString('en-GB');
}

function clearEmpty(container) {
  const note = container.querySelector('.empty-note');
  if (note) note.remove();
}

let _lastConsoleSpeaker = null;
let _lastConsoleLine = null;
let _lastConsoleTextEl = null;

function logConsole(speaker, text) {
  clearEmpty(el.console);
  // Gemini streams transcription in small chunks — appending each chunk
  // as its own line made ARIA's replies look like scattered one-word
  // messages instead of one flowing sentence. Keep appending to the
  // SAME line while the speaker doesn't change; only start a new line
  // when the speaker actually switches (you ↔ ARIA).
  if (speaker === _lastConsoleSpeaker && _lastConsoleTextEl) {
    _lastConsoleTextEl.textContent += (text.startsWith(' ') || _lastConsoleTextEl.textContent.endsWith(' ') ? '' : ' ') + text;
  } else {
    const line = document.createElement('p');
    line.className = `console-line ${speaker}`;
    const who = speaker === 'you' ? 'You' : 'ARIA';
    const tsEl = document.createElement('span');
    tsEl.className = 'ts';
    tsEl.textContent = ts();
    const whoEl = document.createElement('b');
    whoEl.textContent = `${who}: `;
    const textEl = document.createElement('span');
    textEl.textContent = text;
    line.appendChild(tsEl);
    line.appendChild(whoEl);
    line.appendChild(textEl);
    el.console.appendChild(line);
    _lastConsoleSpeaker = speaker;
    _lastConsoleLine = line;
    _lastConsoleTextEl = textEl;
  }
  el.console.scrollTop = el.console.scrollHeight;
}

// A new engine turn (reconnect, tool call, etc.) should start a fresh
// line next time instead of appending to a possibly-stale old one.
function resetConsoleAccumulator() {
  _lastConsoleSpeaker = null;
  _lastConsoleLine = null;
  _lastConsoleTextEl = null;
}

function logTool(kind, name, detail) {
  clearEmpty(el.toolLog);
  const entry = document.createElement('div');
  entry.className = `tool-entry ${kind}`;
  const marker = kind === 'started' ? '▶' : '✔';
  // Display-only cap — some tools (list_processes, disk_usage_report)
  // can return a genuinely long multi-line result; the underlying data
  // stays intact (this only affects what's rendered in the log), just
  // keeps one entry from visually dominating the whole panel.
  const displayDetail = detail && detail.length > 600 ? detail.slice(0, 600) + '… (truncated in log)' : detail;
  entry.innerHTML = `<span class="ts">${ts()}</span><span class="name">${marker} ${escapeHtml(name)}</span><span class="detail">${escapeHtml(displayDetail)}</span>`;
  el.toolLog.prepend(entry);
}

function logTimeline(label) {
  clearEmpty(el.timeline);
  const item = document.createElement('div');
  item.className = 'timeline-item';
  item.innerHTML = `<span class="ts">${ts()}</span>${escapeHtml(label)}`;
  el.timeline.prepend(item);
}

function escapeHtml(s) {
  const d = document.createElement('div');
  d.innerText = String(s);
  return d.innerHTML;
}

function setStatus(state, detail) {
  if (state === 'connecting') resetConsoleAccumulator();
  el.statusDot.className = `status-dot ${state}`;
  el.statusText.textContent = state.toUpperCase();
  const captions = {
    idle: 'STANDBY', connecting: 'LINKING…', connected: 'ONLINE', disconnected: 'OFFLINE',
  };
  el.coreCaption.textContent = captions[state] || state.toUpperCase();
  if (detail) logTimeline(`Status → ${state}: ${detail}`);
  // The backend auto-starts the engine once a key is configured, so
  // reflect that in the ENGAGE button instead of requiring a manual click.
  engineOn = (state === 'connected' || state === 'connecting');
  el.powerBtn.classList.toggle('active', engineOn);
  el.powerBtn.textContent = engineOn ? 'DISENGAGE' : 'ENGAGE';
}

function setRing(ringEl, valEl, pct) {
  const offset = RING_CIRC - (RING_CIRC * Math.min(100, pct)) / 100;
  ringEl.style.strokeDashoffset = offset;
  valEl.textContent = `${Math.round(pct)}%`;
}

// ── Reactive core: circular bars around the ring, driven by mic level ──
const BAR_COUNT = 40;
const svgns = 'http://www.w3.org/2000/svg';
const bars = [];
for (let i = 0; i < BAR_COUNT; i++) {
  const angle = (i / BAR_COUNT) * Math.PI * 2;
  const bar = document.createElementNS(svgns, 'rect');
  bar.setAttribute('class', 'pulse-bar');
  bar.setAttribute('width', 3);
  bar.setAttribute('height', 6);
  bar.dataset.angle = angle;
  el.pulseBars.appendChild(bar);
  bars.push(bar);
}

function drawBars(level) {
  const base = 90;
  bars.forEach((bar, i) => {
    const angle = parseFloat(bar.dataset.angle);
    const jitter = 0.5 + Math.random() * 0.5;
    const len = 6 + level * 22 * jitter;
    const x1 = 200 + Math.cos(angle) * base;
    const y1 = 200 + Math.sin(angle) * base;
    bar.setAttribute('x', x1 - 1.5);
    bar.setAttribute('y', y1 - len);
    bar.setAttribute('height', len);
    bar.setAttribute('transform', `rotate(${(angle * 180) / Math.PI + 90} ${x1} ${y1})`);
  });
}
drawBars(0.05);
setInterval(() => { if (!engineOn) drawBars(0.05 + Math.random() * 0.05); }, 300);

// ── Socket events ────────────────────────────────────────────────────
socket.on('status', (d) => setStatus(d.state, d.detail));
socket.on('mic_level', (d) => drawBars(d.level));
socket.on('speaking', (d) => el.coreCenter.classList.toggle('speaking', d.state));
socket.on('transcript', (d) => logConsole(d.speaker, d.text));
socket.on('tool_started', (d) => logTool('started', d.name, JSON.stringify(d.args)));
socket.on('tool_finished', (d) => {
  let detail = d.result;
  if (d.name === 'take_screenshot' || d.name === 'generate_image') {
    try {
      const parsed = JSON.parse(d.result);
      detail = parsed.message || detail;
      if (parsed.image_base64) {
        el.screenshotImg.src = `data:image/png;base64,${parsed.image_base64}`;
        el.screenshotPreview.style.display = 'flex';
      }
    } catch (e) { /* not JSON, just show raw text */ }
  }
  logTool('finished', d.name, detail);
});
socket.on('reminder_fired', (d) => {
  logConsole('aria', `⏰ Reminder: ${d.message}`);
  if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
    new Notification('ARIA Reminder', { body: d.message });
  }
});

socket.on('update_available', (d) => {
  const banner = document.createElement('div');
  banner.className = 'update-banner';
  banner.innerHTML = `New ARIA version ${d.latest} available. ` +
    (d.download_url ? `<a href="${d.download_url}" target="_blank">Download</a>` : '') +
    ` <button id="dismissUpdate">✕</button>`;
  document.body.appendChild(banner);
  document.getElementById('dismissUpdate').addEventListener('click', () => banner.remove());
});

socket.on('sysinfo', (d) => {
  setRing(el.cpuRing, el.cpuVal, d.cpu);
  setRing(el.ramRing, el.ramVal, d.ram);
});

// ── Controls ─────────────────────────────────────────────────────────
function toggleEngine() {
  if (!keyConfigured) {
    openSettings();
    return;
  }
  engineOn = !engineOn;
  el.powerBtn.classList.toggle('active', engineOn);
  el.powerBtn.textContent = engineOn ? 'DISENGAGE' : 'ENGAGE';
  socket.emit(engineOn ? 'start_engine' : 'stop_engine');
  logTimeline(engineOn ? 'Engine started' : 'Engine stopped');
}
el.powerBtn.addEventListener('click', toggleEngine);
el.micBtn.addEventListener('click', toggleEngine);

document.querySelectorAll('.qa-btn[data-tool]').forEach((btn) => {
  btn.addEventListener('click', () => {
    const tool = btn.dataset.tool;
    const args = JSON.parse(btn.dataset.args || '{}');
    socket.emit('quick_action', { tool, args });
    logTool('started', tool, JSON.stringify(args));
  });
});

// Template buttons — for tools that need free-text args (a name, a
// prompt, a path...) instead of firing blind, fill the text dock with
// an editable template and select the first [bracketed] part so the
// user can just type over it.
document.querySelectorAll('.qa-btn.tpl-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    const tpl = btn.dataset.template;
    el.textInput.value = tpl;
    el.textInput.focus();
    const start = tpl.indexOf('[');
    const end = tpl.indexOf(']');
    if (start !== -1 && end !== -1) el.textInput.setSelectionRange(start, end + 1);
  });
});

// ── Text command dock — was previously disabled/unwired ───────────────
function sendTextCommand() {
  const text = el.textInput.value.trim();
  if (!text) return;
  socket.emit('text_command', { text });
  el.textInput.value = '';
}
el.sendBtn.addEventListener('click', sendTextCommand);
el.textInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') sendTextCommand();
});

// ── Screenshot lens button + preview close ─────────────────────────────
el.lensBtn.addEventListener('click', () => {
  socket.emit('quick_action', { tool: 'take_screenshot', args: {} });
  logTool('started', 'take_screenshot', '{}');
});
el.screenshotClose.addEventListener('click', () => {
  el.screenshotPreview.style.display = 'none';
});

// ── Games Hub ───────────────────────────────────────────────────────────
el.gamesHubBtn.addEventListener('click', () => {
  window.open('/games/', '_blank');
});

// ── Settings / API key (each install keeps its own key locally) ───────
function openSettings() {
  el.modalError.textContent = '';
  el.apiKeyInput.value = '';
  el.settingsOverlay.classList.add('open');
  el.apiKeyInput.focus();
  fetch('/api/persona').then(r => r.json()).then(d => { el.personaSelect.value = d.persona; }).catch(() => {});
  fetch('/api/voice_mode').then(r => r.json()).then(d => { el.voiceModeSelect.value = d.mode; }).catch(() => {});
}
function closeSettings() {
  el.settingsOverlay.classList.remove('open');
}

async function refreshKeyStatus() {
  try {
    const res = await fetch('/api/key/status');
    const d = await res.json();
    keyConfigured = d.configured;
    el.powerBtn.disabled = !keyConfigured;
    el.modalMaskedNote.textContent = d.configured ? `Currently saved: ${d.masked}` : '';
    if (d.env_override) {
      el.modalMaskedNote.textContent +=
        ' ⚠ ARIA_API_KEY environment variable is set on this machine and overrides whatever you save here — remove it if the key below never seems to match.';
    }
    if (!keyConfigured) {
      setStatus('idle');
      el.coreCaption.textContent = 'SETUP REQUIRED';
      openSettings();
    }
  } catch (e) {
    // server not reachable yet — ignore, page will retry on next load
  }
}

el.gearBtn.addEventListener('click', openSettings);
el.modalCancel.addEventListener('click', () => {
  if (keyConfigured) closeSettings();
});

el.modalSave.addEventListener('click', async () => {
  const key = el.apiKeyInput.value.trim();
  // Key is only required the very first time (before any key is saved).
  // Once configured, reopening Settings to change persona/voice alone
  // shouldn't force retyping the key.
  if (!key && !keyConfigured) {
    el.modalError.textContent = 'Paste a key first.';
    return;
  }
  el.modalSave.disabled = true;
  try {
    if (key) {
      const res = await fetch('/api/key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key }),
      });
      const d = await res.json();
      if (!res.ok || !d.ok) {
        el.modalError.textContent = d.error || 'Could not save the key.';
        return;
      }
      logTimeline(`API key saved (${d.masked})`);
    }

    await fetch('/api/persona', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ persona: el.personaSelect.value }),
    });
    await fetch('/api/voice_mode', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: el.voiceModeSelect.value }),
    });

    if (el.emailAddressInput.value.trim() && el.emailPasswordInput.value.trim()) {
      await fetch('/api/email', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          address: el.emailAddressInput.value.trim(),
          app_password: el.emailPasswordInput.value.trim(),
          provider: el.emailProviderSelect.value,
        }),
      });
      logTimeline('Email account saved');
      el.emailPasswordInput.value = '';
    }

    logTimeline(`Persona: ${el.personaSelect.options[el.personaSelect.selectedIndex].text}, Voice: ${el.voiceModeSelect.options[el.voiceModeSelect.selectedIndex].text}`);

    keyConfigured = true;
    el.powerBtn.disabled = false;
    el.coreCaption.textContent = 'STANDBY';
    closeSettings();
  } catch (e) {
    el.modalError.textContent = 'Could not reach the server.';
  } finally {
    el.modalSave.disabled = false;
  }
});

refreshKeyStatus();
