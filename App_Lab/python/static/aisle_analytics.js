// ============================================================
// aisle_analytics.js
// Handles the "Aisle Intelligence" tab: live heatmap image +
// per-aisle stats table (dwell time, visits, people inside now).
// Data comes from THIS board's /api/aisle/* routes, which proxy
// to the laptop's aisle dwell-time service (port 5003).
// ============================================================

function setAisleConnectionState(connected) {
  const text = document.getElementById('aisle-connection-text');
  if (text) text.innerText = connected ? 'Live' : 'Laptop unreachable';
}

function setAisleText(elementId, value) {
  const el = document.getElementById(elementId);
  if (el) el.innerText = (value === null || value === undefined) ? '--' : value;
}

async function refreshAisleTab() {
  try {
    const res = await fetch('/api/aisle/summary');
    const data = await res.json();

    setAisleConnectionState(data.error !== 'laptop_unreachable');

    const aisles = data.aisles || {};
    const tbody = document.getElementById('aisle-stats-table');

    const aisleIds = Object.keys(aisles);
    if (aisleIds.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4">No aisle data yet.</td></tr>';
    } else {
      tbody.innerHTML = aisleIds.map(aisleId => {
        const a = aisles[aisleId];
        const label = aisleId.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
        return `
          <tr>
            <td>${label}</td>
            <td>${a.people_inside_now ?? 0}</td>
            <td>${a.average_dwell_seconds ?? 0}s</td>
            <td>${a.completed_visits ?? 0}</td>
          </tr>
        `;
      }).join('');
    }

    const busiestLabel = document.getElementById('aisle-busiest-label');
    if (busiestLabel) {
      busiestLabel.innerText = data.busiest_aisle
        ? `Busiest: ${data.busiest_aisle.replace('_', ' ')}`
        : 'No data yet';
    }
  } catch (e) {
    console.error('Could not fetch aisle summary:', e);
    setAisleConnectionState(false);
  }
}

function refreshHeatmapImage() {
  const img = document.getElementById('aisle-heatmap-img');
  if (!img) return;
  // Cache-bust with a timestamp so the browser actually re-fetches
  // the image instead of showing a stale cached version.
  img.style.display = '';
  const fallback = document.getElementById('aisle-heatmap-fallback');
  if (fallback) fallback.style.display = 'none';
  img.src = '/api/aisle/heatmap.png?t=' + Date.now();
}

// Poll the Aisle Intelligence tab only while it's actually visible,
// since the heatmap re-render is a heavier operation on the laptop side.
setInterval(() => {
  const aisleView = document.getElementById('view-aisle');
  if (aisleView && aisleView.classList.contains('active')) {
    refreshAisleTab();
    refreshHeatmapImage();
  }
}, 5000);

document.addEventListener('DOMContentLoaded', () => {
  if (typeof window.switchTab === 'function') {
    const previousSwitchTab = window.switchTab;
    window.switchTab = function (tabName) {
      previousSwitchTab(tabName);
      if (tabName === 'aisle') {
        refreshAisleTab();
        refreshHeatmapImage();
      }
    };
  }
  refreshAisleTab();
});