// ============================================================
// alerts.js
// SINGLE SOURCE OF TRUTH for alerts across the whole dashboard.
// Both the Dashboard's alert widget and the dedicated Alerts page
// render from the exact same /api/alerts response, so they can
// never show different or out-of-sync data.
// ============================================================

let lastAlertsData = { alerts: [], count: 0 };

function alertIconForType(type) {
  switch (type) {
    case 'queue_overflow': return 'fa-triangle-exclamation';
    default: return 'fa-bell';
  }
}

function timeAgoLabel(unixSeconds) {
  const diffSeconds = Math.max(0, Math.floor(Date.now() / 1000 - unixSeconds));
  if (diffSeconds < 60) return `${diffSeconds}s ago`;
  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.floor(diffMinutes / 60);
  return `${diffHours}h ago`;
}

function renderDashboardAlerts(alerts) {
  const container = document.getElementById('dashboard-alerts-list');
  if (!container) return;

  // Remove any previously-inserted live alert items (keep the static
  // low-stock item, which has its own fixed markup and id).
  container.querySelectorAll('.live-alert-item').forEach(el => el.remove());

  // Show at most the 2 most recent live alerts on the Dashboard widget,
  // to keep it compact - the full list lives on the Alerts page.
  alerts.slice(0, 2).forEach(alert => {
    const item = document.createElement('div');
    item.className = 'alert-item alert-danger live-alert-item';
    item.innerHTML = `
      <div class="alert-icon"><i class="fa-solid ${alertIconForType(alert.type)}"></i></div>
      <div class="alert-content">
        <h4>${alert.message}</h4>
        <p>${timeAgoLabel(alert.triggered_at)}</p>
      </div>
      <button class="alert-action" onclick="switchTab('alerts')"><i class="fa-solid fa-arrow-right"></i></button>
    `;
    container.insertBefore(item, container.firstChild);
  });
}

function renderFullAlertsPage(alerts) {
  const container = document.getElementById('alerts-full-list');
  if (!container) return;

  if (alerts.length === 0) {
    container.innerHTML = '<p style="color:var(--text-muted); font-size:13px;">No active alerts right now.</p>';
    return;
  }

  container.innerHTML = alerts.map(alert => `
    <div class="alert-item alert-danger">
      <div class="alert-icon"><i class="fa-solid ${alertIconForType(alert.type)}"></i></div>
      <div class="alert-content">
        <h4>${alert.message}</h4>
        <p>${timeAgoLabel(alert.triggered_at)}</p>
      </div>
    </div>
  `).join('');
}

async function refreshAlerts() {
  try {
    const res = await fetch('/api/alerts');
    const data = await res.json();
    lastAlertsData = data;

    const alerts = data.alerts || [];

    renderDashboardAlerts(alerts);
    renderFullAlertsPage(alerts);

    const countPill = document.getElementById('alerts-count-text');
    if (countPill) countPill.innerText = `${data.count ?? 0} active`;
  } catch (e) {
    console.error('Could not fetch alerts:', e);
  }
}

// Alerts refresh regardless of which tab is active, since the Dashboard
// widget needs to stay current at all times.
setInterval(refreshAlerts, 4000);

document.addEventListener('DOMContentLoaded', () => {
  if (typeof window.switchTab === 'function') {
    const previousSwitchTab = window.switchTab;
    window.switchTab = function (tabName) {
      previousSwitchTab(tabName);
      if (tabName === 'alerts') {
        refreshAlerts();
      }
    };
  }
  refreshAlerts();
});