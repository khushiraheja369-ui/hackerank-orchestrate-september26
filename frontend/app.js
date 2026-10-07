/**
 * Buy or Wait? — Personal Liquidity Advisory Engine
 * Frontend Controller & State Management
 */

// Application State
const state = {
    overview: null,
    requests: [],
    totalRequests: 0,
    currentPage: 1,
    pageSize: 30,
    selectedRequestId: null,
    currentDetail: null,
    profiles: [],
    filters: {
        status: 'all',
        method: 'all',
        currency: 'all',
        search: ''
    },
    chart: null,
    searchDebounceTimer: null
};

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    initChart();
    initEventListeners();
    fetchOverview();
    fetchProfiles();
    fetchRequests(1);
});

function initChart() {
    state.chart = new BalanceChart('simulation-canvas');
}

// Event Listeners
function initEventListeners() {
    // Search input with debounce & shortcut
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            clearTimeout(state.searchDebounceTimer);
            state.searchDebounceTimer = setTimeout(() => {
                state.filters.search = e.target.value;
                fetchRequests(1);
            }, 200);
        });

        // Cmd/Ctrl + K shortcut
        window.addEventListener('keydown', (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
                e.preventDefault();
                searchInput.focus();
                searchInput.select();
            }
        });
    }

    // Segmented filter buttons
    const segmentedBtns = document.querySelectorAll('#status-filter-pills .segmented-btn');
    segmentedBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            segmentedBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.filters.status = btn.dataset.status;
            fetchRequests(1);
        });
    });

    // Method & Currency selects
    const methodSelect = document.getElementById('method-select');
    if (methodSelect) {
        methodSelect.addEventListener('change', (e) => {
            state.filters.method = e.target.value;
            fetchRequests(1);
        });
    }

    const currencySelect = document.getElementById('currency-select');
    if (currencySelect) {
        currencySelect.addEventListener('change', (e) => {
            state.filters.currency = e.target.value;
            fetchRequests(1);
        });
    }

    // Pagination
    const prevBtn = document.getElementById('btn-prev-page');
    const nextBtn = document.getElementById('btn-next-page');
    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            if (state.currentPage > 1) fetchRequests(state.currentPage - 1);
        });
    }
    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            fetchRequests(state.currentPage + 1);
        });
    }

    // Chart zoom buttons
    const zoomBtns = document.querySelectorAll('.btn-zoom');
    zoomBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            zoomBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const days = parseInt(btn.dataset.zoom, 10);
            if (state.chart) state.chart.setZoom(days);
        });
    });

    // Sandbox Modal
    const sandboxModal = document.getElementById('sandbox-modal');
    const openSandboxBtn = document.getElementById('btn-open-sandbox');
    const closeSandboxBtn = document.getElementById('btn-close-sandbox');
    const cancelSandboxBtn = document.getElementById('btn-cancel-sandbox');
    const runSimBtn = document.getElementById('btn-run-simulation');

    if (openSandboxBtn && sandboxModal) {
        openSandboxBtn.addEventListener('click', () => {
            sandboxModal.classList.add('active');
        });
    }

    const closeSandbox = () => {
        if (sandboxModal) sandboxModal.classList.remove('active');
    };

    if (closeSandboxBtn) closeSandboxBtn.addEventListener('click', closeSandbox);
    if (cancelSandboxBtn) cancelSandboxBtn.addEventListener('click', closeSandbox);
    if (runSimBtn) runSimBtn.addEventListener('click', handleRunSimulation);

    // Lightbox Modal
    const lightboxModal = document.getElementById('lightbox-modal');
    const closeLightboxBtn = document.getElementById('btn-close-lightbox');
    if (closeLightboxBtn && lightboxModal) {
        closeLightboxBtn.addEventListener('click', () => {
            lightboxModal.classList.remove('active');
        });
    }

    // Export CSV
    const exportBtn = document.getElementById('btn-export-csv');
    if (exportBtn) {
        exportBtn.addEventListener('click', exportToCsv);
    }
}

// Fetch Overview Stats
async function fetchOverview() {
    try {
        const res = await fetch('/api/overview');
        if (!res.ok) throw new Error('Failed to load overview');
        const data = await res.json();
        state.overview = data;
        renderOverview(data);
    } catch (err) {
        console.error('Overview error:', err);
    }
}

function renderOverview(data) {
    const total = data.total_requests || 1;
    const sc = data.status_counts || {};

    const nowCount = sc.affordable_now || 0;
    const planCount = sc.affordable_with_plan || 0;
    const laterCount = sc.affordable_later || 0;
    const notCount = sc.not_affordable || 0;

    const setText = (id, text) => {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    };

    setText('header-total-cases', `${total} Cases`);

    setText('kpi-now-count', `${nowCount} cases`);
    setText('kpi-now-pct', `${Math.round((nowCount / total) * 100)}%`);

    setText('kpi-plan-count', `${planCount} cases`);
    setText('kpi-plan-pct', `${Math.round((planCount / total) * 100)}%`);

    setText('kpi-later-count', `${laterCount} cases`);
    setText('kpi-later-pct', `${Math.round((laterCount / total) * 100)}%`);

    setText('kpi-not-count', `${notCount} cases`);
    setText('kpi-not-pct', `${Math.round((notCount / total) * 100)}%`);
}

// Fetch Profiles (for Sandbox)
async function fetchProfiles() {
    try {
        const res = await fetch('/api/profiles');
        if (!res.ok) return;
        const data = await res.json();
        state.profiles = data.profiles || [];
        populateProfilesSelect();
    } catch (err) {
        console.error('Profiles fetch error:', err);
    }
}

function populateProfilesSelect() {
    const select = document.getElementById('sim-user-select');
    if (!select) return;
    select.innerHTML = '';
    state.profiles.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.user_id;
        opt.textContent = `${p.user_id} (${p.home_currency} • Reserve: ${p.minimum_balance_to_keep.toLocaleString()})`;
        select.appendChild(opt);
    });
}

// Fetch Requests List
async function fetchRequests(page = 1) {
    state.currentPage = page;
    const params = new URLSearchParams({
        page: page,
        page_size: state.pageSize,
        status: state.filters.status,
        method: state.filters.method,
        currency: state.filters.currency,
        q: state.filters.search
    });

    const listEl = document.getElementById('requests-list');
    listEl.innerHTML = '<div style="text-align: center; padding: 30px; color: var(--text-tertiary);">Updating ledger...</div>';

    try {
        const res = await fetch(`/api/requests?${params.toString()}`);
        if (!res.ok) throw new Error('Failed to fetch requests');
        const data = await res.json();
        state.requests = data.items || [];
        state.totalRequests = data.total || 0;

        renderRequestsList();
        renderPagination(data);

        // Select first if current is not in list
        if (state.requests.length > 0) {
            const hasCurrent = state.requests.some(r => r.request_id === state.selectedRequestId);
            if (!hasCurrent) {
                selectRequest(state.requests[0].request_id);
            }
        }
    } catch (err) {
        console.error('Fetch requests error:', err);
        listEl.innerHTML = '<div style="text-align: center; padding: 30px; color: var(--accent-rose);">Error loading ledger</div>';
    }
}

function renderRequestsList() {
    const listEl = document.getElementById('requests-list');
    if (!listEl) return;
    listEl.innerHTML = '';

    if (state.requests.length === 0) {
        listEl.innerHTML = '<div style="text-align: center; padding: 30px; color: var(--text-tertiary);">No matching requests</div>';
        return;
    }

    state.requests.forEach(req => {
        const card = document.createElement('div');
        card.className = `request-card-item ${req.request_id === state.selectedRequestId ? 'selected' : ''}`;
        card.id = `card-${req.request_id}`;
        card.onclick = () => selectRequest(req.request_id);

        const statusClass = req.affordability_status;
        const statusLabel = formatStatusLabel(req.affordability_status);

        card.innerHTML = `
            <div class="card-top-row">
                <span class="card-req-id">${req.request_id}</span>
                <span class="card-cat-badge">${formatCategory(req.request_type)}</span>
            </div>
            <div class="card-middle-row">
                <span class="card-amount font-mono">${req.home_currency} ${req.requested_amount.toLocaleString()}</span>
                <span class="status-chip ${statusClass}">
                    <span>${statusLabel}</span>
                </span>
            </div>
            <div class="card-bottom-row">
                <span>${formatMethod(req.recommended_payment_method)}</span>
                <div style="display: flex; align-items: center; gap: 6px;">
                    ${req.has_images ? '<span class="evidence-tag">Receipt</span>' : ''}
                    <span>${req.request_date}</span>
                </div>
            </div>
        `;

        listEl.appendChild(card);
    });
}

function renderPagination(data) {
    const info = document.getElementById('pagination-info');
    const prevBtn = document.getElementById('btn-prev-page');
    const nextBtn = document.getElementById('btn-next-page');

    const total = data.total || 0;
    const start = total === 0 ? 0 : (data.page - 1) * data.page_size + 1;
    const end = Math.min(total, data.page * data.page_size);

    if (info) info.textContent = `${start}-${end} of ${total}`;
    if (prevBtn) prevBtn.disabled = data.page <= 1;
    if (nextBtn) nextBtn.disabled = data.page >= data.total_pages;
}

// Select & Load Request Detail
async function selectRequest(requestId) {
    state.selectedRequestId = requestId;

    document.querySelectorAll('.request-card-item').forEach(c => c.classList.remove('selected'));
    const activeCard = document.getElementById(`card-${requestId}`);
    if (activeCard) activeCard.classList.add('selected');

    try {
        const res = await fetch(`/api/request/${requestId}`);
        if (!res.ok) throw new Error('Failed to load request detail');
        const detail = await res.json();
        state.currentDetail = detail;
        renderRequestDetail(detail);
    } catch (err) {
        console.error('Request detail load error:', err);
    }
}

function renderRequestDetail(detail) {
    const req = detail.request;
    const prof = detail.profile;
    const verd = detail.verdict;

    // Header info
    setText('dossier-req-id', req.request_id);
    setText('dossier-req-cat', formatCategory(req.request_type));
    setText('dossier-user-tag', `User: ${req.user_id}`);
    setText('dossier-date-tag', `Requested: ${req.request_date}`);
    setText('dossier-deadline-tag', `Target: ${req.desired_completion_date}`);
    setText('dossier-prompt-text', `"${req.request_text}"`);

    // Evidence chip
    const hasImagesChip = document.getElementById('dossier-has-images');
    if (hasImagesChip) {
        hasImagesChip.style.display = (detail.images && detail.images.length > 0) ? 'inline-flex' : 'none';
    }

    // Advisory Memo Banner
    const banner = document.getElementById('verdict-banner');
    if (banner) {
        banner.className = `verdict-banner-card ${verd.affordability_status}`;
    }

    setText('verdict-status-text', formatStatusVerdictTitle(verd.affordability_status));
    setText('verdict-explanation', verd.decision_explanation);

    const curr = prof.home_currency;
    setText('verdict-safe-amt', `${curr} ${verd.amount_safe_to_pay.toLocaleString()}`);
    setText('verdict-req-amt', `${curr} ${req.requested_amount.toLocaleString()}`);

    setText('verdict-method-pill', `Settlement: ${formatMethod(verd.recommended_payment_method)}`);
    setText('verdict-earliest-pill', `Earliest Full: ${verd.earliest_date_for_full_payment || 'N/A'}`);
    setText('verdict-spending-pill', `Adjustments: ${verd.spending_changes_needed || 'None'}`);

    // Update 90-Day Simulation Canvas Chart
    if (state.chart) {
        state.chart.setData(detail, curr);
    }

    // Candidate Settlement Plans Matrix
    renderCandidatesGrid(detail.candidates, curr);

    // Profile & Safeguards
    setText('prof-avail-bal', `${curr} ${prof.current_available_balance.toLocaleString()}`);
    setText('prof-min-bal', `${curr} ${prof.minimum_balance_to_keep.toLocaleString()}`);
    setText('prof-max-months', prof.max_installment_months ? `${prof.max_installment_months} Months` : 'None Allowed');

    renderTagList('prof-protected-tags', prof.protected_categories, 'protected');
    const flexible = [...(prof.reducible_categories || []), ...(prof.stoppable_categories || [])];
    renderTagList('prof-flexible-tags', flexible, 'flexible');

    // Recurring Debits List
    renderRecurringDebits(detail.recurring_commitments, curr);

    // Salary Anchor
    const salBox = document.getElementById('salary-commitment-box');
    const salText = document.getElementById('salary-anchor-text');
    if (detail.salary_commitment && salBox && salText) {
        salBox.style.display = 'block';
        salText.textContent = `${curr} ${detail.salary_commitment.amount.toLocaleString()} recurring on Day ${detail.salary_commitment.day_of_month}`;
    } else if (salBox) {
        salBox.style.display = 'none';
    }

    // Multimodal Evidence Images
    renderEvidenceSection(detail.images, curr);
}

function renderCandidatesGrid(candidates, currency) {
    const grid = document.getElementById('candidates-grid');
    if (!grid) return;
    grid.innerHTML = '';

    if (!candidates || candidates.length === 0) {
        grid.innerHTML = '<div class="text-muted" style="font-size: 12px;">No payment options evaluated</div>';
        return;
    }

    candidates.forEach((cand) => {
        const card = document.createElement('div');
        card.className = `candidate-plan-card ${cand.is_winner ? 'winner' : ''}`;

        card.innerHTML = `
            ${cand.is_winner ? '<span class="candidate-badge-winner">Recommended Plan</span>' : ''}
            <div class="cand-title">${formatMethod(cand.method)} ${cand.payment_option_id ? `(${cand.payment_option_id})` : ''}</div>
            <div class="cand-row">
                <span class="text-muted">Total Payable:</span>
                <span class="cand-val">${currency} ${cand.total_amount_paid.toLocaleString()}</span>
            </div>
            <div class="cand-row">
                <span class="text-muted">Schedule:</span>
                <span class="cand-val font-mono" style="font-size: 11px;">${cand.num_payments} settlement(s)</span>
            </div>
            <div class="cand-row">
                <span class="text-muted">Horizon:</span>
                <span class="cand-val" style="font-size: 11px;">${cand.start_date} → ${cand.completion_date}</span>
            </div>
            <div class="cand-row">
                <span class="text-muted">Liquidity Impact:</span>
                <span class="cand-val" style="color: ${cand.is_safe ? '#10b981' : '#f43f5e'};">
                    ${cand.is_safe ? '✓ Reserve Protected (+' + currency + ' ' + Math.round(cand.min_headroom).toLocaleString() + ')' : '✗ Reserve Deficit'}
                </span>
            </div>
        `;
        grid.appendChild(card);
    });
}

function renderRecurringDebits(commitments, currency) {
    const list = document.getElementById('recurring-debits-list');
    if (!list) return;
    list.innerHTML = '';

    if (!commitments || commitments.length === 0) {
        list.innerHTML = '<span class="text-muted" style="font-size: 11.5px;">No historical recurring commitments</span>';
        return;
    }

    commitments.forEach(rd => {
        const item = document.createElement('div');
        item.style.display = 'flex';
        item.style.justifyContent = 'space-between';
        item.style.fontSize = '11.5px';
        item.style.borderBottom = '1px solid rgba(255,255,255,0.03)';
        item.style.paddingBottom = '3px';

        const cadenceDesc = rd.cadence === 'monthly' ? `Monthly (Day ${rd.day_of_month})` : `Every ${rd.period_days} Days`;
        item.innerHTML = `
            <div>
                <span style="font-weight: 500; color: #ffffff;">${formatCategory(rd.category)}</span>
                <span class="text-muted" style="font-size: 10.5px; display: block;">${cadenceDesc}</span>
            </div>
            <span class="font-mono text-secondary">${currency} ${rd.amount.toLocaleString()}</span>
        `;
        list.appendChild(item);
    });
}

function renderTagList(containerId, tags, cssClass) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = '';
    if (!tags || tags.length === 0) {
        el.innerHTML = '<span class="text-muted" style="font-size: 10.5px;">None</span>';
        return;
    }
    tags.forEach(t => {
        const span = document.createElement('span');
        span.className = `meta-tag ${cssClass}`;
        span.textContent = formatCategory(t);
        el.appendChild(span);
    });
}

function renderEvidenceSection(images, currency) {
    const sec = document.getElementById('evidence-section');
    const container = document.getElementById('evidence-images-container');
    if (!sec || !container) return;

    if (!images || images.length === 0) {
        sec.style.display = 'none';
        return;
    }

    sec.style.display = 'flex';
    container.innerHTML = '';

    images.forEach(img => {
        const thumb = document.createElement('div');
        thumb.className = 'evidence-image-thumb';
        thumb.innerHTML = `
            <img src="${img.image_url}" alt="${img.doc_type}">
            <div class="thumb-overlay">
                ${formatCategory(img.doc_type)} • ${img.currency} ${img.amount ? img.amount.toLocaleString() : ''}
            </div>
        `;
        thumb.onclick = () => openLightbox(img);
        container.appendChild(thumb);
    });
}

function openLightbox(img) {
    const modal = document.getElementById('lightbox-modal');
    const lightboxImg = document.getElementById('lightbox-img');
    const title = document.getElementById('lightbox-title');
    const caption = document.getElementById('lightbox-caption');

    if (!modal || !lightboxImg) return;
    lightboxImg.src = img.image_url;
    if (title) title.textContent = `Attached Receipt: ${img.image_id} (${formatCategory(img.doc_type)})`;
    if (caption) caption.textContent = `Extracted Amount: ${img.currency} ${img.amount ? img.amount.toLocaleString() : 'N/A'} • Related Event: ${img.related_event_id || 'N/A'}`;
    modal.classList.add('active');
}

// Handle Custom Sandbox Simulation
async function handleRunSimulation() {
    const uid = document.getElementById('sim-user-select').value;
    const cat = document.getElementById('sim-category-select').value;
    const amt = parseFloat(document.getElementById('sim-amount-input').value) || 1000;
    const reqDate = document.getElementById('sim-req-date').value;
    const deadline = document.getElementById('sim-deadline-date').value;
    const allowPartial = document.getElementById('sim-allow-partial').checked;

    const payload = {
        user_id: uid,
        request_id: `custom_${Date.now()}`,
        request_date: reqDate,
        request_type: cat,
        requested_amount: amt,
        desired_completion_date: deadline,
        allows_partial_payment: allowPartial,
        request_text: `Custom purchase simulation: ${amt} for ${cat}`,
        payment_options: [
            {
                payment_option_id: 'opt_full',
                payment_method: 'full_payment',
                payment_amount: amt,
                number_of_payments: 1,
                first_payment_date: reqDate,
                financing_fee: 0,
                total_payable_amount: amt
            },
            {
                payment_option_id: 'opt_bnpl_3m',
                payment_method: 'installments',
                payment_amount: Math.round((amt / 3) * 100) / 100,
                number_of_payments: 3,
                first_payment_date: reqDate,
                payment_frequency_days: 30,
                financing_fee: 0,
                total_payable_amount: amt
            },
            {
                payment_option_id: 'opt_bnpl_6m',
                payment_method: 'installments',
                payment_amount: Math.round(((amt * 1.05) / 6) * 100) / 100,
                number_of_payments: 6,
                first_payment_date: reqDate,
                payment_frequency_days: 30,
                financing_fee: amt * 0.05,
                total_payable_amount: amt * 1.05
            }
        ]
    };

    try {
        const res = await fetch('/api/simulate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error('Simulation failed');
        const detail = await res.json();
        
        const modal = document.getElementById('sandbox-modal');
        if (modal) modal.classList.remove('active');

        state.currentDetail = detail;
        renderRequestDetail(detail);
    } catch (err) {
        console.error('Simulation error:', err);
        alert('Simulation error: ' + err.message);
    }
}

// Export CSV
function exportToCsv() {
    if (!state.requests || state.requests.length === 0) return;
    const headers = ['request_id', 'amount_safe_to_pay', 'affordability_status', 'recommended_payment_method', 'earliest_date_for_full_payment'];
    const rows = state.requests.map(r => [
        r.request_id,
        r.amount_safe_to_pay,
        r.affordability_status,
        r.recommended_payment_method,
        r.earliest_date_for_full_payment
    ]);

    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map(e => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', 'liquidity_evaluation_ledger.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Helper Utilities
function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function formatStatusLabel(status) {
    if (!status) return 'Unknown';
    switch (status) {
        case 'affordable_now': return 'Instant';
        case 'affordable_with_plan': return 'Staged';
        case 'affordable_later': return 'Deferred';
        case 'not_affordable': return 'Declined';
        default: return status.replace(/_/g, ' ');
    }
}

function formatStatusVerdictTitle(status) {
    switch (status) {
        case 'affordable_now': return 'APPROVED FOR IMMEDIATE SETTLEMENT';
        case 'affordable_with_plan': return 'STRUCTURED PLAN RECOMMENDED';
        case 'affordable_later': return 'DEFERRED SETTLEMENT RECOMMENDED';
        case 'not_affordable': return 'TRANSACTION DECLINED — PRESERVES RESERVE';
        default: return (status || '').toUpperCase().replace(/_/g, ' ');
    }
}

function formatMethod(method) {
    if (!method) return 'N/A';
    switch (method) {
        case 'full_payment': return 'Full Settlement';
        case 'installments': return 'Installment Plan';
        case 'partial_payment': return 'Staged Payment';
        case 'wait': return 'Hold / Wait';
        case 'not_recommended': return 'Decline';
        default: return method.replace(/_/g, ' ');
    }
}

function formatCategory(cat) {
    if (!cat) return 'General';
    return cat.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}
