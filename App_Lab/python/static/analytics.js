// ============================================================
// analytics.js
// Handles: Dashboard "Visitors Now" live card + the full
// "Store Analytics" tab (headline cards, hourly chart, recent events).
// All data comes from THIS board's own /api/analytics/* routes,
// which proxy to the laptop's doorway detection service.
// ============================================================

let hourlyTrafficChart = null;

async function fetchDashboardVisitorCount() {
  try {
    const res = await fetch('/api/analytics/status');
    const data = await res.json();

    const visitorsEl = document.getElementById('val-visitors');
    if (visitorsEl) {
      // "Visitors Now" = people currently inside, from live doorway detection
      visitorsEl.innerText = (data.people_inside ?? 0).toString();
    }
  } catch (e) {
    console.error('Could not fetch live visitor count:', e);
  }
}

function setAnalyticsConnectionState(connected) {
  const pill = document.getElementById('analytics-connection');
  const text = document.getElementById('analytics-connection-text');
  if (!pill || !text) return;

  if (connected) {
    pill.style.borderColor = '';
    text.innerText = 'Live';
  } else {
    text.innerText = 'Laptop unreachable';
  }
}

async function fetchAnalyticsSummary() {
  try {
    const res = await fetch('/api/analytics/summary');
    const data = await res.json();

    setAnalyticsConnectionState(data.error !== 'laptop_unreachable');

    setText('an-inside', data.people_inside_now);
    setText('an-today-visits', data.today_visits);
    setText('an-today-exits', data.today_exits);
    setText('an-peak-hour', data.peak_hour ?? 'N/A');
    setText('an-total-visits', data.total_visits_all_time);

    updateHourlyChart(data.hourly_breakdown || []);
  } catch (e) {
    console.error('Could not fetch analytics summary:', e);
    setAnalyticsConnectionState(false);
  }
}

async function fetchAnalyticsRecentEvents() {
  try {
    const res = await fetch('/api/analytics/events/recent');
    const events = await res.json();
    const tbody = document.getElementById('an-recent-events');
    if (!tbody) return;

    if (!events || events.length === 0) {
      tbody.innerHTML = '<tr><td colspan="3">No events logged yet.</td></tr>';
      return;
    }

    tbody.innerHTML = events.slice(0, 10).map(e => {
      const timePart = (e.timestamp || '').split('T')[1] || e.timestamp || '--';
      const isIn = e.direction === 'IN';
      const color = isIn ? 'var(--green)' : 'var(--danger)';
      return `
        <tr>
          <td>#${e.track_id}</td>
          <td><span style="color:${color}; font-weight:600;">${e.direction}</span></td>
          <td>${timePart}</td>
        </tr>
      `;
    }).join('');
  } catch (e) {
    console.error('Could not fetch recent events:', e);
  }
}

function setText(elementId, value) {
  const el = document.getElementById(elementId);
  if (el) el.innerText = (value === null || value === undefined) ? '--' : value;
}

function updateHourlyChart(hourlyBreakdown) {
  const canvas = document.getElementById('hourlyTrafficChart');
  if (!canvas || typeof Chart === 'undefined') return;

  const labels = hourlyBreakdown.map(row => row.hour);
  const inData = hourlyBreakdown.map(row => row.in);
  const outData = hourlyBreakdown.map(row => row.out);

  if (hourlyTrafficChart) {
    hourlyTrafficChart.data.labels = labels;
    hourlyTrafficChart.data.datasets[0].data = inData;
    hourlyTrafficChart.data.datasets[1].data = outData;
    hourlyTrafficChart.update();
    return;
  }

  const ctx = canvas.getContext('2d');
  hourlyTrafficChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'In',
          data: inData,
          backgroundColor: '#10b981',
          borderRadius: 4,
        },
        {
          label: 'Out',
          data: outData,
          backgroundColor: '#ef4444',
          borderRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: 'top' },
        datalabels: { display: false },
      },
      scales: {
        x: { grid: { display: false } },
        y: { beginAtZero: true, ticks: { precision: 0 } },
      },
    },
  });
}

function refreshAnalyticsTab() {
  fetchAnalyticsSummary();
  fetchAnalyticsRecentEvents();
}

// Dashboard's visitor count refreshes regardless of which tab is active,
// same cadence as the rest of the dashboard's live widgets.
setInterval(fetchDashboardVisitorCount, 3000);
fetchDashboardVisitorCount();

// The Store Analytics tab (chart + table) only needs to refresh while
// it's actually visible - poll a bit less aggressively since it's more data.
setInterval(() => {
  const reportsView = document.getElementById('view-reports');
  if (reportsView && reportsView.classList.contains('active')) {
    refreshAnalyticsTab();
  }
}, 4000);

// Also refresh immediately whenever the user switches to the Reports/Analytics
// tab, so it doesn't show stale "--" placeholders until the next poll tick.
// app.js defines a global switchTab(name) function used by every sidebar
// button's onclick="switchTab('...')" - we wrap it rather than guessing at
// a CSS selector, so this works regardless of markup changes.
document.addEventListener('DOMContentLoaded', () => {
  if (typeof window.switchTab === 'function') {
    const originalSwitchTab = window.switchTab;
    window.switchTab = function (tabName) {
      originalSwitchTab(tabName);
      if (tabName === 'reports') {
        refreshAnalyticsTab();
      }
    };
  }
  // Fire once on load in case Reports is the default active tab
  refreshAnalyticsTab();
});