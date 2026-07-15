@extends('layout')

@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
{{--
    Spending dashboard. The heavy widgets (stat totals, Top-N, charts, sub-vendor,
    M/WBE) are LAZY-LOADED client-side from the API so the page shell renders
    instantly and a cold/slow Parquet-scan endpoint only delays its own widget
    (never the whole page). Same pattern as the transactions table.
--}}
<div class="db-hero">
    <div class="inner_container">
        <div class="container db-hero-inner">
            <div class="db-hero-copy">
                <div class="db-eyebrow" style="color: var(--db-accent);">Procurement</div>
                <h1>Spending @include('procurement.partials.source_badge', ['source' => 'checkbook'])</h1>
                <p style="max-width: 62ch; font-size: var(--db-text-lg); line-height: 1.5; color: var(--db-text-on-navy-muted); margin: var(--db-space-2) 0 0;">Every dollar the City of New York pays out — searchable by payee, agency, and expense category, sourced from <a href="https://www.checkbooknyc.com" target="_blank" rel="noopener" style="color: var(--db-on-dark-accent);">Checkbook NYC</a>.</p>
                <form action="{{ route('procurement.transactions.search') }}" method="GET" style="margin-top: var(--db-space-4); max-width: 620px;">
                    <div class="db-search">
                        <i class="bi bi-search"></i>
                        <input type="search" name="q" placeholder="Search payees, agencies, categories…" aria-label="Search spending" autocomplete="off">
                    </div>
                </form>
            </div>
        </div>
    </div>
</div>

<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-5); padding-bottom: var(--db-space-8);">

        {{-- Stat tiles (values filled client-side) --}}
        <div class="db-stat-grid">
            <div class="db-stat is-accent">
                <div class="db-stat-label">Total spending</div>
                <div class="db-stat-value" id="st-total">—</div>
                <div class="db-stat-sub">FY{{ $fiscal_year }}</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Transactions</div>
                <div class="db-stat-value" id="st-count">—</div>
                <div class="db-stat-sub">posted</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Agencies</div>
                <div class="db-stat-value" id="st-agencies">—</div>
                <div class="db-stat-sub">reporting</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Expense categories</div>
                <div class="db-stat-value" id="st-categories">—</div>
                <div class="db-stat-sub">tracked</div>
            </div>
        </div>

        {{-- Top-5 ranked cards (2×2) — filled client-side --}}
        <div style="display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: var(--db-space-3); margin-top: var(--db-space-4);">
            @php
                $cards = [
                    ['agencies', 'Top agencies', route('procurement.agencies')],
                    ['payees', 'Top payees', route('procurement.vendors')],
                    ['categories', 'Top expense categories', route('procurement.transactions.search', ['fiscal_year' => $fiscal_year])],
                    ['contracts', 'Top contracts', route('procurement.contracts')],
                ];
            @endphp
            @foreach($cards as [$key, $title, $viewAll])
            <div class="db-card">
                <div class="db-card-body">
                    <div style="display: flex; align-items: baseline; justify-content: space-between; margin-bottom: var(--db-space-1);">
                        <h3 style="margin: 0; font-size: var(--db-text-2xs); font-weight: var(--db-weight-bold); text-transform: uppercase; letter-spacing: var(--db-tracking-caps); color: var(--db-text-muted);">{{ $title }}</h3>
                        <a href="{{ $viewAll }}" class="db-btn db-btn-ghost db-btn-sm">View all</a>
                    </div>
                    <div class="db-ranked-list" id="top-{{ $key }}"><div class="db-rank-skel">Loading…</div></div>
                </div>
            </div>
            @endforeach
        </div>

        {{-- Charts --}}
        <div style="display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: var(--db-space-3); margin-top: var(--db-space-3);">
            <div class="db-chart-card">
                <div class="db-chart-head"><span class="db-chart-title">Spending by fiscal year</span></div>
                <div class="db-chart-body" style="height: 320px;"><canvas id="byYearChart" aria-label="Spending by fiscal year"></canvas></div>
            </div>
            <div class="db-chart-card">
                <div class="db-chart-head"><span class="db-chart-title">Last 12 months</span></div>
                <div class="db-chart-body" style="height: 320px;"><canvas id="byMonthChart" aria-label="Spending over the last 12 months"></canvas></div>
            </div>
        </div>

        {{-- Sub-vendor spending lens (shown client-side when there's data) --}}
        <div id="subvendor-section" style="margin-top: var(--db-space-7); display: none;">
            <div style="display: flex; align-items: baseline; justify-content: space-between; gap: var(--db-space-2); margin-bottom: var(--db-space-1);">
                <h2 style="margin: 0; font-size: var(--db-text-xl);">Sub-vendor spending</h2>
                <a href="{{ route('procurement.transactions.search', ['fiscal_year' => $fiscal_year, 'sub_vendor' => 'Yes']) }}" class="db-btn db-btn-ghost db-btn-sm">View all sub-vendor payments</a>
            </div>
            <p style="color: var(--db-text-muted); font-size: var(--db-text-sm); margin: 0 0 var(--db-space-2);">Payments the City made to sub-vendors working under prime contractors.</p>
            <div class="db-stat-grid">
                <div class="db-stat is-accent"><div class="db-stat-label">Sub-vendor spending</div><div class="db-stat-value" id="sv-total">—</div><div class="db-stat-sub">FY{{ $fiscal_year }}</div></div>
                <div class="db-stat"><div class="db-stat-label">Payments</div><div class="db-stat-value" id="sv-payments">—</div></div>
                <div class="db-stat"><div class="db-stat-label">Sub-vendors</div><div class="db-stat-value" id="sv-subs">—</div></div>
                <div class="db-stat"><div class="db-stat-label">Prime vendors</div><div class="db-stat-value" id="sv-primes">—</div></div>
            </div>
            <div style="display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: var(--db-space-3); margin-top: var(--db-space-4);">
                <div class="db-card"><div class="db-card-body">
                    <h3 style="margin: 0 0 var(--db-space-1); font-size: var(--db-text-2xs); font-weight: var(--db-weight-bold); text-transform: uppercase; letter-spacing: var(--db-tracking-caps); color: var(--db-text-muted);">Top sub-vendors</h3>
                    <div class="db-ranked-list" id="sv-top-subs"></div>
                </div></div>
                <div class="db-card"><div class="db-card-body">
                    <h3 style="margin: 0 0 var(--db-space-1); font-size: var(--db-text-2xs); font-weight: var(--db-weight-bold); text-transform: uppercase; letter-spacing: var(--db-tracking-caps); color: var(--db-text-muted);">Top primes routing sub-payments</h3>
                    <div class="db-ranked-list" id="sv-top-primes"></div>
                </div></div>
            </div>
        </div>

        {{-- M/WBE spending lens (shown client-side once the v2 re-ingest lands) --}}
        <div id="mwbe-section" style="margin-top: var(--db-space-7); display: none;">
            <div style="display: flex; align-items: baseline; justify-content: space-between; gap: var(--db-space-2); margin-bottom: var(--db-space-1);">
                <h2 style="margin: 0; font-size: var(--db-text-xl);">M/WBE spending</h2>
                <a href="{{ route('procurement.transactions.search', ['fiscal_year' => $fiscal_year, 'woman_owned' => 'Yes']) }}" class="db-btn db-btn-ghost db-btn-sm">View women-owned payments</a>
            </div>
            <p style="color: var(--db-text-muted); font-size: var(--db-text-sm); margin: 0 0 var(--db-space-2);">Spending attributed to minority- and women-owned business enterprises, per Checkbook NYC's certification categories.</p>
            <div class="db-stat-grid">
                <div class="db-stat is-accent"><div class="db-stat-label">Certified M/WBE spending</div><div class="db-stat-value" id="mw-certified">—</div><div class="db-stat-sub">FY{{ $fiscal_year }}</div></div>
                <div class="db-stat"><div class="db-stat-label">Woman-owned</div><div class="db-stat-value" id="mw-woman">—</div></div>
                <div class="db-stat"><div class="db-stat-label">Emerging (EBE)</div><div class="db-stat-value" id="mw-emerging">—</div></div>
                <div class="db-stat"><div class="db-stat-label">Certified payments</div><div class="db-stat-value" id="mw-certified-n">—</div></div>
            </div>
            <div class="db-card" style="margin-top: var(--db-space-4);"><div class="db-card-body">
                <h3 style="margin: 0 0 var(--db-space-1); font-size: var(--db-text-2xs); font-weight: var(--db-weight-bold); text-transform: uppercase; letter-spacing: var(--db-tracking-caps); color: var(--db-text-muted);">Spending by M/WBE category</h3>
                <div class="db-ranked-list" id="mw-categories"></div>
            </div></div>
        </div>

    </div>
</div>

<style>.db-rank-skel { color: var(--db-text-muted); font-size: var(--db-text-sm); padding: var(--db-space-2) 0; }</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script>
(function () {
    const FY = {{ (int) $fiscal_year }};
    const apiBase = @json(rtrim(config('apis.fapi_public_entry', 'https://api.databook.nyc'), '/'));
    const $ = id => document.getElementById(id);
    const enc = encodeURIComponent;
    const money = n => {
        n = parseFloat(n || 0);
        if (n >= 1e9) return '$' + (n / 1e9).toFixed(1) + 'B';
        if (n >= 1e6) return '$' + (n / 1e6).toFixed(1) + 'M';
        if (n >= 1e3) return '$' + (n / 1e3).toFixed(0) + 'K';
        return '$' + Math.round(n).toLocaleString();
    };
    const num = n => Number(n || 0).toLocaleString();
    const esc = s => (s == null ? '' : String(s)).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
    const jget = path => fetch(apiBase + path).then(r => r.ok ? r.json() : null).catch(() => null);

    // Deep-link a ranked item (mirror of the server-side $rankLink).
    function rankLink(key, it) {
        const v = it.value || '';
        if (!v) return null;
        if (key === 'agencies')   return '/procurement/agency/' + enc(v);
        if (key === 'categories')  return '/procurement/transactions/search?fiscal_year=' + FY + '&expense_category=' + enc(v);
        if (key === 'payees')      return it.vendor_id ? '/procurement/vendor/' + it.vendor_id
                                     : '/procurement/transactions/search?fiscal_year=' + FY + '&vendor=' + enc(v);
        if (key === 'contracts')   return it.ctr_id ? '/procurement/contract/' + it.ctr_id
                                     : '/procurement/transactions/search?fiscal_year=' + FY + '&q=' + enc(v);
        return null;
    }
    function rankedRows(items, key, nameOf, valueOf, subOf) {
        if (!items || !items.length) return '<div class="db-rank-skel">No data.</div>';
        return items.map((it, i) => {
            const lnk = key ? rankLink(key, it) : null;
            const name = esc(nameOf(it));
            const sub = subOf ? subOf(it) : '';
            const label = (lnk ? `<a href="${lnk}">${name}</a>` : name) + sub;
            return `<div class="db-ranked-item"><span class="db-ranked-rank">${i + 1}</span>` +
                   `<span class="db-ranked-name" title="${name}">${label}</span>` +
                   `<span class="db-ranked-value">${money(valueOf(it))}</span></div>`;
        }).join('');
    }

    // --- Stat totals ---
    jget(`/oce/transactions?fiscal_year=${FY}&limit=1`).then(d => {
        if (!d) return;
        $('st-total').textContent = money(d.total_amount);
        $('st-count').textContent = num(d.total);
    });
    jget(`/oce/transactions/facets?fiscal_year=${FY}`).then(d => {
        if (!d) return;
        $('st-agencies').textContent = num((d.agency || []).length);
        $('st-categories').textContent = num((d.expense_category || []).length);
    });

    // --- Top-N cards ---
    jget(`/oce/spending/top?fiscal_year=${FY}&limit=5`).then(d => {
        if (!d) { document.querySelectorAll('[id^="top-"] .db-rank-skel').forEach(e => e.textContent = 'Unavailable.'); return; }
        const val = it => it.amount, name = it => it.value;
        $('top-agencies').innerHTML   = rankedRows(d.agencies, 'agencies', name, val);
        $('top-payees').innerHTML     = rankedRows(d.payees, 'payees', name, val);
        $('top-categories').innerHTML = rankedRows(d.expense_categories, 'categories', name, val);
        $('top-contracts').innerHTML  = rankedRows(d.contracts, 'contracts', name, val);
    });

    // --- Charts ---
    jget(`/oce/transactions/charts`).then(data => {
        if (!data || !data.by_year || !window.Chart) return;
        DBChart.apply(Chart);
        new Chart($('byYearChart').getContext('2d'), {
            type: 'bar',
            data: { labels: data.by_year.labels, datasets: [{ data: data.by_year.values, backgroundColor: DBChart.navy, borderRadius: 4, maxBarThickness: 46 }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, grid: { color: DBChart.grid }, ticks: { callback: DBChart.money } }, x: { grid: { display: false } } } }
        });
        new Chart($('byMonthChart').getContext('2d'), {
            type: 'line',
            data: { labels: data.by_month.labels, datasets: [{ data: data.by_month.values, borderColor: DBChart.accent, backgroundColor: DBChart.accentFill, fill: true, tension: 0.35, pointRadius: 0, pointHoverRadius: 4, borderWidth: 2 }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, grid: { color: DBChart.grid }, ticks: { callback: DBChart.money } }, x: { grid: { display: false } } } }
        });
    });

    // --- Sub-vendor lens ---
    jget(`/oce/spending/subvendors?fiscal_year=${FY}&limit=8`).then(d => {
        if (!d || !(d.payment_count > 0)) return;
        $('sv-total').textContent = money(d.total_amount);
        $('sv-payments').textContent = num(d.payment_count);
        $('sv-subs').textContent = num(d.subvendor_count);
        $('sv-primes').textContent = num(d.prime_count);
        // Sub-vendor payee links to its vendor profile when resolved; prime shown inline.
        $('sv-top-subs').innerHTML = (d.top_subvendors || []).map((s, i) => {
            const nm = esc(s.payee || '—');
            const name = s.vendor_id ? `<a href="/procurement/vendor/${s.vendor_id}">${nm}</a>` : nm;
            const prime = s.prime ? ` <span style="color:var(--db-text-muted);font-size:var(--db-text-2xs);">· via ${esc(s.prime)}</span>` : '';
            return `<div class="db-ranked-item"><span class="db-ranked-rank">${i+1}</span>` +
                   `<span class="db-ranked-name" title="${esc(s.payee||'')}">${name}${prime}</span>` +
                   `<span class="db-ranked-value">${money(s.amount)}</span></div>`;
        }).join('');
        $('sv-top-primes').innerHTML = (d.top_primes || []).map((p, i) => {
            const nm = esc(p.prime || '—');
            const name = p.vendor_id ? `<a href="/procurement/vendor/${p.vendor_id}">${nm}</a>` : nm;
            return `<div class="db-ranked-item"><span class="db-ranked-rank">${i+1}</span>` +
                   `<span class="db-ranked-name" title="${esc(p.prime||'')}">${name}</span>` +
                   `<span class="db-ranked-value">${money(p.amount)}</span></div>`;
        }).join('');
        $('subvendor-section').style.display = '';
    });

    // --- M/WBE lens ---
    jget(`/oce/spending/mwbe?fiscal_year=${FY}`).then(d => {
        if (!d || !d.available) return;
        $('mw-certified').textContent = money((d.certified_mwbe||{}).total_amount);
        $('mw-certified-n').textContent = num((d.certified_mwbe||{}).payment_count);
        $('mw-woman').textContent = money((d.woman_owned||{}).total_amount);
        $('mw-emerging').textContent = money((d.emerging||{}).total_amount);
        $('mw-categories').innerHTML = (d.by_category || []).map((c, i) =>
            `<a class="db-ranked-item" href="/procurement/transactions/search?fiscal_year=${FY}&mwbe_category=${enc(c.category||'')}" style="text-decoration:none;color:inherit;">` +
            `<span class="db-ranked-rank">${i+1}</span>` +
            `<span class="db-ranked-name" title="${esc(c.category||'')}">${esc(c.category||'—')}<span style="color:var(--db-text-muted);font-size:var(--db-text-2xs);"> · ${num(c.payment_count)} payments</span></span>` +
            `<span class="db-ranked-value">${money(c.total_amount)}</span></a>`).join('');
        $('mwbe-section').style.display = '';
    });
})();
</script>
@endsection
