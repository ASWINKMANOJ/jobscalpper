/* ── Toast system ─────────────────────────────────────── */
function showToast(msg, type = 'success') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${type === 'success' ? '✓' : '✗'}</span> <span>${msg}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.animation = 'fadeOut 0.3s ease forwards';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

/* ── Scrape Now ───────────────────────────────────────── */
async function triggerScrape() {
  const btn = document.getElementById('scrape-btn');
  if (!btn) return;
  btn.disabled = true;
  btn.textContent = '⏳ Running…';

  try {
    const res = await fetch('/api/scrape', { method: 'POST' });
    const data = await res.json();
    if (data.ok) {
      showToast('Scrape started — this takes a few minutes.', 'success');
      pollScrapeStatus(btn);
    } else {
      showToast(data.message || 'Scrape already running', 'error');
      btn.disabled = false;
      btn.innerHTML = '<span>⚡</span> Scrape Now';
    }
  } catch (e) {
    showToast('Failed to start scrape.', 'error');
    btn.disabled = false;
    btn.innerHTML = '<span>⚡</span> Scrape Now';
  }
}

function pollScrapeStatus(btn) {
  const interval = setInterval(async () => {
    try {
      const res = await fetch('/api/scrape/status');
      const data = await res.json();
      if (!data.running) {
        clearInterval(interval);
        showToast(data.message, 'success');
        btn.disabled = false;
        btn.innerHTML = '<span>⚡</span> Scrape Now';
        // Refresh stats
        setTimeout(() => location.reload(), 1200);
      }
    } catch (_) { clearInterval(interval); }
  }, 2500);
}

/* ── Application actions ──────────────────────────────── */
async function approveApp(id) {
  const res = await fetch(`/api/applications/${id}/approve`, { method: 'POST' });
  const data = await res.json();
  if (data.ok) {
    showToast('Application approved ✓', 'success');
    updateRowStatus(id, 'approved');
  } else {
    showToast(data.error || 'Failed', 'error');
  }
}

async function rejectApp(id) {
  const res = await fetch(`/api/applications/${id}/reject`, { method: 'POST' });
  const data = await res.json();
  if (data.ok) {
    showToast('Application rejected', 'success');
    updateRowStatus(id, 'rejected');
  } else {
    showToast(data.error || 'Failed', 'error');
  }
}

async function sendApp(id, dryRun = false) {
  const label = dryRun ? 'dry-run preview' : 'send';
  const btn = document.getElementById(`send-btn-${id}`);
  if (btn) { btn.disabled = true; btn.textContent = '…'; }

  const res = await fetch(`/api/applications/${id}/send`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dry_run: dryRun }),
  });
  const data = await res.json();

  if (btn) { btn.disabled = false; btn.textContent = dryRun ? 'Preview' : 'Send'; }

  if (data.ok) {
    if (dryRun) {
      openModal('Email Preview', data.result);
    } else {
      showToast('Email sent! ✓', 'success');
      updateRowStatus(id, 'sent');
    }
  } else {
    showToast(data.error || 'Send failed', 'error');
  }
}

async function viewCoverLetter(id, title) {
  const res = await fetch(`/api/applications/${id}/cover_letter`);
  const data = await res.json();
  if (data.ok) {
    openModal(`Cover Letter — ${title}`, data.cover_letter);
  } else {
    showToast('Could not load cover letter', 'error');
  }
}

/* ── Row status updates ───────────────────────────────── */
function updateRowStatus(id, newStatus) {
  const badge = document.getElementById(`badge-${id}`);
  const row   = document.getElementById(`row-${id}`);
  if (badge) {
    badge.className = `badge badge-${newStatus}`;
    badge.textContent = newStatus;
  }
  // Re-render action buttons
  const actions = document.getElementById(`actions-${id}`);
  if (actions) {
    actions.innerHTML = renderActions(id, newStatus, '');
  }
  // Brief highlight
  if (row) {
    row.style.transition = 'background 0.5s';
    row.style.background = 'rgba(124,111,255,0.08)';
    setTimeout(() => row.style.background = '', 800);
  }
}

function renderActions(id, status, title) {
  if (status === 'pending') {
    return `
      <button class="btn btn-success btn-sm" onclick="approveApp('${id}')">✓ Approve</button>
      <button class="btn btn-ghost btn-sm" onclick="viewCoverLetter('${id}', '${title}')">Letter</button>
      <button class="btn btn-error btn-sm" onclick="rejectApp('${id}')">✗</button>`;
  }
  if (status === 'approved') {
    return `
      <button class="btn btn-primary btn-sm" id="send-btn-${id}" onclick="sendApp('${id}')">Send</button>
      <button class="btn btn-ghost btn-sm" id="send-btn-${id}" onclick="sendApp('${id}', true)">Preview</button>
      <button class="btn btn-ghost btn-sm" onclick="viewCoverLetter('${id}', '${title}')">Letter</button>`;
  }
  return `<button class="btn btn-ghost btn-sm" onclick="viewCoverLetter('${id}', '${title}')">Letter</button>`;
}

/* ── Modal ────────────────────────────────────────────── */
function openModal(title, content) {
  closeModal();
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.id = 'active-modal';
  overlay.onclick = (e) => { if (e.target === overlay) closeModal(); };
  overlay.innerHTML = `
    <div class="modal">
      <h3>${title}</h3>
      <pre>${escapeHtml(content)}</pre>
      <div class="modal-footer">
        <button class="btn btn-ghost" onclick="closeModal()">Close</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);
}

function closeModal() {
  document.getElementById('active-modal')?.remove();
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/* ── Keyboard shortcuts ───────────────────────────────── */
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeModal();
});
