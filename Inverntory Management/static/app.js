let donutChart = null;

document.addEventListener('DOMContentLoaded', () => {
  initClock();
  initDonutChart();
  fetchDashboardSummary();
  fetchCategorySummary();
  fetchProducts();
});

// Clock Updates
function initClock() {
  const timeEl = document.getElementById('live-time');
  const dateEl = document.getElementById('live-date');

  function update() {
    const now = new Date();
    timeEl.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    dateEl.textContent = now.toLocaleDateString('en-GB', { day: '2-digit', month: 'Long', year: 'numeric' });
  }
  update();
  setInterval(update, 1000);
}

// Tab Switching Logic
function switchTab(tabId) {
  document.querySelectorAll('.nav-item').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.tab-view').forEach(view => view.classList.remove('active'));

  event.currentTarget.classList.add('active');
  const target = document.getElementById(`view-${tabId}`);
  if (target) target.classList.add('active');

  if (tabId === 'inventory') fetchCategorySummary();
  if (tabId === 'deduct') loadDeductDropdown();
}

// Initialize Donut Chart matching UI Palette
function initDonutChart() {
  const ctx = document.getElementById('summaryDonutChart').getContext('2d');
  
  donutChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Visitors Now', 'Queue Count', 'Low Stock', 'Active Staff'],
      datasets: [{
        data: [214, 8, 12, 15],
        backgroundColor: ['#1d5eff', '#f59e0b', '#10b981', '#8b5cf6'],
        borderWidth: 0,
        hoverOffset: 4
      }]
    },
    options: {
      cutout: '78%',
      plugins: {
        legend: { display: false },
        tooltip: { enabled: true }
      },
      responsive: true,
      maintainAspectRatio: false
    }
  });
}

// Update Donut Chart and Summaries
function updateSummaryView(visitors, queue, lowstock, staff) {
  const total = visitors + queue + lowstock + staff;

  document.getElementById('donut-total').textContent = total;
  
  // Percentages
  const pVisitors = ((visitors / total) * 100).toFixed(1) + '%';
  const pQueue = ((queue / total) * 100).toFixed(1) + '%';
  const pLowStock = ((lowstock / total) * 100).toFixed(1) + '%';
  const pStaff = ((staff / total) * 100).toFixed(1) + '%';

  document.getElementById('pct-visitors').textContent = pVisitors;
  document.getElementById('pct-queue').textContent = pQueue;
  document.getElementById('pct-lowstock').textContent = pLowStock;
  document.getElementById('pct-staff').textContent = pStaff;

  // Chart
  donutChart.data.datasets[0].data = [visitors, queue, lowstock, staff];
  donutChart.update();

  // Banner text
  document.getElementById('summary-banner-text').textContent = 
    `Total store activity is ${total}, with ${visitors} visitors, ${queue} in queue, ${lowstock} low stock items and ${staff} active staff members.`;
}

// Fetch Backend Data
async function fetchDashboardSummary() {
  try {
    const res = await fetch('/api/products');
    if (!res.ok) return;
    const products = await res.json();
    
    // Count low stock items from backend
    const lowStockCount = products.filter(p => p.shelf_units <= (p.shelf_capacity * 0.25)).length;

    document.getElementById('val-lowstock').textContent = lowStockCount;
    document.getElementById('summary-lowstock').textContent = lowStockCount;
    document.getElementById('alert-stock-title').textContent = `${lowStockCount} items are low in stock`;

    // Static values matching baseline dashboard design
    const visitors = 214;
    const queue = 8;
    const staff = 15;

    updateSummaryView(visitors, queue, lowStockCount, staff);
  } catch (err) {
    console.error('Error fetching dashboard summary:', err);
  }
}

async function fetchCategorySummary() {
  try {
    const res = await fetch('/api/category/summary');
    const categories = await res.json();

    const container = document.getElementById('category-cards-container');
    if (!container) return;

    container.innerHTML = categories.map(c => `
      <div class="category-card ${c.needs_attention ? 'needs-attention' : ''}">
        <h3>${c.category}</h3>
        <p>Capacity: <strong>${c.capacity_per_item} ${c.unit}</strong></p>
        <p>Current Shelf Units: <strong>${c.total_shelf_units} ${c.unit}</strong></p>
        <p>Out of Stock: <strong class="text-danger">${c.out_of_stock_count}</strong></p>
        <button class="btn btn-reset" onclick="resetCategory('${c.category}')">
          <i class="fa-solid fa-arrows-rotate"></i> Reset Category Stock
        </button>
      </div>
    `).join('');
  } catch (err) {
    console.error('Failed to load categories:', err);
  }
}

async function fetchProducts() {
  try {
    const res = await fetch('/api/products');
    const products = await res.json();

    const tbody = document.getElementById('inventory-table-body');
    if (!tbody) return;

    tbody.innerHTML = products.map(p => `
      <tr>
        <td><strong>${p.product_id}</strong></td>
        <td>${p.product_name}</td>
        <td>${p.category}</td>
        <td><strong>${p.shelf_units}</strong></td>
        <td>${p.shelf_capacity}</td>
        <td><span class="badge ${p.shelf_units <= (p.shelf_capacity * 0.25) ? 'text-danger' : 'text-green'}">${p.status}</span></td>
        <td>
          <button class="btn btn-primary" onclick="resetProduct('${p.product_id}')">Reset</button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Failed to load products:', err);
  }
}

async function loadDeductDropdown() {
  const select = document.getElementById('deduct-pid');
  if (!select) return;

  try {
    const res = await fetch('/api/products');
    const products = await res.json();

    select.innerHTML = products.map(p => `
      <option value="${p.product_id}">
        ${p.product_id} - ${p.product_name} (${p.shelf_units} remaining)
      </option>
    `).join('');
  } catch (err) {
    console.error('Failed to populate dropdown:', err);
  }
}

async function handleDeductSubmit(e) {
  e.preventDefault();
  const product_id = document.getElementById('deduct-pid').value;
  const quantity = document.getElementById('deduct-qty').value;

  const res = await fetch('/api/products/deduct', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ product_id, quantity })
  });

  const data = await res.json();
  if (res.ok) {
    alert('Stock deducted successfully!');
    loadDeductDropdown();
    fetchDashboardSummary();
  } else {
    alert(data.error || 'Failed to deduct stock');
  }
}

async function resetCategory(category) {
  await fetch('/api/category/reset', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ category })
  });
  alert(`Category '${category}' reset back to full capacity.`);
  fetchCategorySummary();
  fetchDashboardSummary();
}

async function resetProduct(product_id) {
  await fetch(`/api/products/${product_id}/reset`, { method: 'POST' });
  fetchProducts();
  fetchDashboardSummary();
}
