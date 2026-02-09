const API_URL = '/api';

// --- DATA FETCHING ---

// Dashboard (Stats)
async function refreshDashboard() {
    try {
        const res = await fetch(`${API_URL}/stats`);
        const stats = await res.json();

        const elPending = document.getElementById('stat-pending');
        const elFailed = document.getElementById('stat-failed');
        const elWorker = document.getElementById('stat-worker');

        if (elPending) elPending.innerText = stats.pending_jobs;
        if (elFailed) elFailed.innerText = stats.failed_jobs;
        if (elWorker) elWorker.innerText = stats.worker_active ? 'ACTIVE' : 'PAUSED';

        const statusEl = document.getElementById('server-status');
        if (statusEl) {
            statusEl.innerText = 'Online';
            statusEl.style.color = '#10b981';
            document.querySelector('.status-dot').style.backgroundColor = '#10b981';
        }
    } catch (e) {
        console.error("Dashboard Sync Failed", e);
        const statusEl = document.getElementById('server-status');
        if (statusEl) {
            statusEl.innerText = 'Offline';
            statusEl.style.color = '#ef4444';
            document.querySelector('.status-dot').style.backgroundColor = '#ef4444';
        }
    }
}

// Jobs Table
async function loadJobs() {
    try {
        const res = await fetch(`${API_URL}/jobs?limit=20`);
        const jobs = await res.json();
        const tbody = document.getElementById('jobs-table-body');
        if (!tbody) return;

        tbody.innerHTML = '';

        jobs.forEach(job => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><small>${job.id.substring(0, 8)}...</small></td>
                <td><span class="badge badge-default">${job.type}</span></td>
                <td><span style="font-weight:bold; color: ${getStatusColor(job.status)}">${job.status}</span></td>
                <td>${new Date(job.scheduled_at).toLocaleString()}</td>
                <td>${job.attempts}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error("Failed to load jobs", e);
    }
}

function getStatusColor(status) {
    if (status === 'completed') return '#10b981';
    if (status === 'failed') return '#ef4444';
    if (status === 'processing') return '#f59e0b';
    return '#9CA3AF';
}

// Settings Form
async function loadSettings() {
    try {
        const res = await fetch(`${API_URL}/settings`);
        const settings = await res.json();

        // Auto-fill inputs matching IDs
        for (const [key, value] of Object.entries(settings)) {
            const el = document.getElementById(key);
            if (el) {
                if (el.type === 'checkbox') el.checked = value;
                else el.value = value || '';
            }
        }
    } catch (e) {
        console.error("Failed to load settings", e);
    }
}

async function saveSettings() {
    const form = document.getElementById('settings-form');
    if (!form) return;

    const formData = new FormData(form);
    const updates = {};

    formData.forEach((value, key) => {
        updates[key] = value;
    });

    // Handle checkboxes manually
    document.querySelectorAll('#settings-form input[type="checkbox"]').forEach(cb => {
        updates[cb.name] = cb.checked;
    });

    try {
        await fetch(`${API_URL}/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates)
        });
        showToast('Settings Saved Successfully!');
    } catch (e) {
        alert("Failed to save settings: " + e.message);
    }
}

function showToast(msg) {
    const t = document.getElementById('toast');
    if (!t) return;
    t.innerText = msg;
    t.classList.remove('hidden');
    setTimeout(() => t.classList.add('hidden'), 3000);
}

// Quick Actions
async function triggerAction(action) {
    alert(`Triggering Action: ${action} (Backend implementation pending)`);
}
