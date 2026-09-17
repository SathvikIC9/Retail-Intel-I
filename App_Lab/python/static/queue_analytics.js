// ============================================================
// queue_analytics.js
// Handles: Dashboard "Queue Count" live card + the full
// "Queue Management" tab (headline cards, counter status table).
// Data comes from THIS board's /api/queue/* routes, which proxy
// to the laptop's queue detection service (port 5002).
// ============================================================

async function fetchDashboardQueueCount() {
  try {
    const res = await fetch('/api/queue/summary');
    const data = await res.json();

    const queueEl = document.getElementById('val-queue');
    if (queueEl) {
      queueEl.innerText = (data.total_waiting ?? 0).toString();
    }
  } catch (e) {
    console.error('Could not fetch live queue count:', e);
  }
}

function setQueueConnectionState(connected) {
  const pill = document.getElementById('queue-connection');
  const text = document.getElementById('queue-connection-text');
  if (!pill || !text) return;

  text.innerText = connected ? 'Live' : 'Laptop unreachable';
}

function setQueueText(elementId, value) {
  const el = document.getElementById(elementId);
  if (el) el.innerText = (value === null || value === undefined) ? '--' : value;
}

const COUNTER_STATE_COLORS = {
  QUEUING: 'var(--orange)',
  SERVING: 'var(--green)',
  CASHIER: 'var(--primary)',
  OUTSIDE: 'var(--text-light)',
};

async function refreshQueueTab() {
  try {
    const res = await fetch('/api/queue/summary');
    const data = await res.json();

    setQueueConnectionState(data.error !== 'laptop_unreachable');

    setQueueText('q-total-waiting', data.total_waiting);
    setQueueText('q-active-people', data.active_people_count);
    setQueueText('q-avg-wait', data.average_wait_frames);
    setQueueText('q-longest-wait', data.longest_wait_frames);

    const tbody = document.getElementById('q-counters-table');
    if (tbody) {
      const counters = data.counters || [];
      if (counters.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3">No counter data yet.</td></tr>';
      } else {
        tbody.innerHTML = counters.map(c => {
          const color = COUNTER_STATE_COLORS[c.state] || 'var(--text-muted)';
          return `
            <tr>
              <td>${c.counter_id}</td>
              <td><span style="color:${color}; font-weight:600;">${c.state || 'UNKNOWN'}</span></td>
              <td>${c.queue_count ?? 0}</td>
            </tr>
          `;
        }).join('');
      }
    }
  } catch (e) {
    console.error('Could not fetch queue summary:', e);
    setQueueConnectionState(false);
  }
}

// Dashboard's queue count refreshes regardless of active tab
setInterval(fetchDashboardQueueCount, 3000);
fetchDashboardQueueCount();

// Queue Management tab refreshes a bit more often since it's simulating
// a live feed that changes every few seconds (see AUTO_ADVANCE_INTERVAL_SECONDS
// on the laptop service).
setInterval(() => {
  const queueView = document.getElementById('view-queue');
  if (queueView && queueView.classList.contains('active')) {
    refreshQueueTab();
  }
}, 2000);

// Wrap switchTab (same pattern as analytics.js) so the tab refreshes
// immediately when clicked, not just on the next poll tick.
document.addEventListener('DOMContentLoaded', () => {
  if (typeof window.switchTab === 'function') {
    const previousSwitchTab = window.switchTab;
    window.switchTab = function (tabName) {
      previousSwitchTab(tabName);
      if (tabName === 'queue') {
        refreshQueueTab();
      }
    };
  }
  refreshQueueTab();
});