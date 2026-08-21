@php
    // ---- Top nav (9 items): [label, href, active] -------------------------
    $nav = [
        ['Renewals',      route('renewals'),           Request::is('procurement/renewals*')],
        ['Notices',       route('notices'),            Request::is('notices*')],
        ['Organizations', route('orgs'),               Request::is('organizations*') || Request::is('organization*') || Request::is('o/*')],
        ['People',        route('people'),             Request::is('people*')],
        ['Jobs',          '/jobs-dashboard',           Request::is('titles*') || Request::is('title*') || Request::is('t/*') || Request::is('jobs*')],
        ['Projects',      route('projects'),           Request::is('capital*') || Request::is('projects*') || Request::is('project*') || Request::is('p/*')],
        ['Schools',       route('schools'),            Request::is('schools*') || Request::is('s/*')],
        ['Districts',     route('districts'),          Request::is('districts*') || Request::is('d/*')],
        ['Procurement',   route('procurement.index'),  Request::is('procurement*') || Request::is('research*')],
        ['About',         route('about'),              Request::is('about*') || Request::is('mcp*') || Request::is('styleguide*') || Request::is('blog*') || Request::is('articles*')],
    ];

    // ---- Submenus: one config replaces the 11 hand-written blocks ----------
    // Each section: 'show' (when this submenu appears), 'title', and 'items' [label, href, active].
    $sections = [
        'notices' => [
            'show'  => Request::is('notices*'),
            'title' => 'Notices',
            'items' => [
                ['Dashboard',            route('notices'),                                            Request::is('notices') && !Request::is('notices/*')],
                ['All',                  route('noticesSection', ['section' => 'all']),               Request::is('notices/all')],
                ['Events',               route('noticesSection', ['section' => 'events']),            Request::is('notices/events*')],
                ['Public Hearings',      route('noticesSection', ['section' => 'public-hearings']),   Request::is('notices/public-hearings*')],
                ['Meetings',             route('noticesSection', ['section' => 'meetings']),          Request::is('notices/meetings*')],
                ['Contract Awards',      route('noticesSection', ['section' => 'contract-awards']),   Request::is('notices/contract-awards*')],
                ['Special Materials',    route('noticesSection', ['section' => 'special-materials']), Request::is('notices/special-materials*')],
                ['Agency Rules',         route('noticesSection', ['section' => 'agency-rules']),      Request::is('notices/agency-rules*')],
                ['Property Disposition', route('noticesSection', ['section' => 'property-disposition']), Request::is('notices/property-disposition*')],
                ['Court Notices',        route('noticesSection', ['section' => 'court-notices']),     Request::is('notices/court-notices*')],
                ['Procurement',          route('noticesSection', ['section' => 'procurement']),       Request::is('notices/procurement*')],
                ['Change in Personnel',  route('noticesSection', ['section' => 'change-of-personnel']), Request::is('notices/change-of-personnel*')],
            ],
        ],
        'organizations' => [
            'show'  => Request::is('organizations*') && !Request::is('organizations/*/'),
            'title' => 'Organizations',
            'items' => [
                // /organizations now redirects to /agencies, so City Agencies is the landing tab.
                ['City Agencies',     route('orgsAgencies'),         Request::is('organizations/agencies*') || Request::is('organizations') ],
                ['City Org Chart',    route('orgsChart'),            Request::is('organizations/chart*')],
                ['City Vendors',      route('procurement.vendors'),  Request::is('procurement/vendor*')],
                ['All Organizations', route('orgsAll'),              Request::is('organizations/all*')],
            ],
        ],
        'jobs' => [
            'show'  => Request::is('titles*') || Request::is('title*') || Request::is('t/*') || Request::is('jobs-exams*') || Request::is('titles-overview*') || Request::is('jobs') || Request::is('jobs-dashboard'),
            'title' => 'Jobs',
            'items' => [
                ['Dashboard', '/jobs-dashboard',  Request::is('jobs-dashboard') || Request::is('titles-overview')],
                ['Jobs',      '/jobs',            Request::is('jobs')],
                ['Titles',    route('titles'),    Request::is('titles') && !Request::is('titles/*')],
                ['Exams',     route('jobsExams'), Request::is('jobs-exams*')],
            ],
        ],
        'projects' => [
            'show'  => Request::is('capital*') || Request::is('projects*'),
            'title' => 'Projects',
            'items' => [
                ['Projects',     route('projects'),       Request::is('projects') && !Request::is('projects/*')],
                ['Types',        route('prjTypes'),       Request::is('projects/types*')],
                ['Categories',   route('prjCategories'),  Request::is('projects/categories*')],
                ['Budget Lines', route('budgetLines'),    Request::is('projects/budget-lines*')],
                ['Commitments',  route('prjCommitments'), Request::is('projects/commitments*')],
                ['Capital',      route('capital'),        Request::is('projects/capital*')],
            ],
        ],
        'districts' => [
            'show'  => Request::is('districts*') || Request::is('d/*'),
            'title' => 'Districts',
            'items' => [
                // The district-type switcher lives in the submenu (design-handoff2 &sect;08).
                // /districts defaults to community districts (cd) in the controller.
                ['Community Districts', route('districtsPresetType', ['type' => 'cd']),  Request::is('districts') || Request::is('districts/cd') || Request::is('d/cd-*')],
                ['City Council',        route('districtsPresetType', ['type' => 'cc']),  Request::is('districts/cc') || Request::is('d/cc-*')],
                ['Neighborhoods (NTA)', route('districtsPresetType', ['type' => 'nta']), Request::is('districts/nta') || Request::is('d/nta-*')],
                ['School Districts',    route('districtsPresetType', ['type' => 'sd']),  Request::is('districts/sd') || Request::is('d/sd-*')],
            ],
        ],
        'procurement' => [
            'show'  => (Request::is('procurement*') || Request::is('research*')) && !Request::is('procurement/renewals*'),
            'title' => 'Procurement',
            'items' => [
                ['Dashboard',     route('procurement.index'),         Request::is('procurement') && !Request::is('procurement/*')],
                ['Solicitations', route('procurement.solicitations'), Request::is('procurement/solicitations*')],
                ['Contracts',     route('procurement.contracts'),     Request::is('procurement/contract*')],
                ['Vendors',       route('procurement.vendors'),       Request::is('procurement/vendor*')],
                ['Transactions',  route('procurement.transactions'),  Request::is('procurement/transaction*')],
                ['Budget',        route('procurement.budget'),        Request::is('procurement/budget*')],
                ['Revenue',       route('procurement.revenue'),       Request::is('procurement/revenue*')],
                ['Payroll',       route('procurement.payroll'),       Request::is('procurement/payroll*')],
                ['NYCHA',         route('procurement.nycha'),         Request::is('procurement/nycha*')],
                ['Agencies',      route('procurement.agencies'),      Request::is('procurement/agencies*') || Request::is('procurement/agency*')],
                // Orange = Analysis product (analyst/AI-enriched, not raw official data).
                ['Digital Services Analysis', route('research.digital-reform'), Request::is('research/digital-reform*'), [
                    ['Overview',                route('research.digital-reform'),          Request::is('research/digital-reform') && !Request::is('research/digital-reform/expiring') && !Request::is('research/digital-reform/licenses*')],
                    ['Contracts Expiring Soon', route('research.digital-reform.expiring'), Request::is('research/digital-reform/expiring')],
                    ['Software Licenses',       route('research.digital-reform.licenses'), Request::is('research/digital-reform/licenses*')],
                ]],
            ],
        ],
        'about' => [
            'show'  => Request::is('about*') || Request::is('mcp*') || Request::is('styleguide*') || Request::is('blog*') || Request::is('articles*'),
            'title' => 'About',
            'items' => [
                ['The Project',     route('about'),       Request::is('about') && !Request::is('about/*')],
                ['Data Health',     route('about.data'),  Request::is('about/data')],
                ['Database Tables', route('about.tables'), Request::is('about/tables')],
                ['Ingestion Log',   route('about.log'),   Request::is('about/log')],
                ['MCP',             route('mcp'),         Request::is('mcp*')],
                ['Styleguide',      '/styleguide',        Request::is('styleguide*')],
                ['Blog',            route('blog'),        Request::is('blog*') || Request::is('articles*')],
            ],
        ],
    ];

    // First matching section wins (URL families are mutually exclusive).
    $activeSection = null;
    foreach ($sections as $section) {
        if ($section['show']) { $activeSection = $section; break; }
    }

    // Breadcrumbs render only when present AND the page has no submenu of its own.
    $showBreadcrumbs = isset($breadcrumbs) && count($breadcrumbs) > 0
        && !Request::is('notices*') && !Request::is('organizations*')
        && !Request::is('capital*') && !Request::is('projects*')
        && !Request::is('jobs*') && !Request::is('titles*') && !Request::is('t/*');
@endphp

<div class="db-header">
    <div class="container db-header-inner">
        <a href="{{ route('root') }}" class="db-brand">DATABOOK.NYC</a>
        <button class="db-nav-toggle" id="dbNavToggle" type="button" aria-label="Menu" aria-expanded="false" aria-controls="dbNav"><i class="bi bi-list"></i></button>
        <nav class="db-nav" id="dbNav">
            @foreach ($nav as [$label, $href, $active])
                <a href="{{ $href }}" class="db-nav-link{{ $active ? ' is-active' : '' }}">{{ $label }}</a>
            @endforeach
        </nav>
        {{-- Header search &rarr; internal federated search (/search &rarr; api /get/search).
             Enhanced with typeahead: a dropdown of live suggestions from
             /search/suggest (&rarr; api /get/search/suggest). Submitting still runs
             the full /search page, so it degrades gracefully without JS. --}}
        <form class="db-header-search" action="{{ route('search') }}" method="get" role="search">
            <i class="bi bi-search"></i>
            <input type="search" name="q" id="dbHeaderSearchInput" autocomplete="off"
                   value="{{ request()->is('search') ? request()->query('q') : '' }}"
                   placeholder="Search Databook&hellip;" aria-label="Search Databook"
                   role="combobox" aria-expanded="false" aria-autocomplete="list"
                   aria-controls="dbHeaderSearchDD">
            <div class="db-header-search-dd" id="dbHeaderSearchDD" role="listbox" hidden></div>
        </form>
    </div>
</div>

@if ($activeSection)
<div class="db-submenu">
    <div class="container db-submenu-inner">
        <span class="db-submenu-title">{{ $activeSection['title'] }}</span>
        <nav class="db-submenu-nav">
            @foreach ($activeSection['items'] as $item)
                @php $label = $item[0]; $href = $item[1]; $active = $item[2]; $children = $item[3] ?? null; @endphp
                @if ($children)
                    <div class="db-submenu-analysis">
                        <button type="button" class="db-submenu-link db-analysis-toggle{{ $active ? ' is-active' : '' }}" id="dsAnalysisToggle" aria-haspopup="true" aria-expanded="false">
                            {{ $label }} <i class="bi bi-caret-down-fill" style="font-size: .7em;"></i>
                        </button>
                        <div class="db-analysis-menu" id="dsAnalysisMenu" role="menu">
                            @foreach ($children as [$cLabel, $cHref, $cActive])
                                <a role="menuitem" class="{{ $cActive ? 'is-active' : '' }}" href="{{ $cHref }}">{{ $cLabel }}</a>
                            @endforeach
                        </div>
                    </div>
                @else
                    <a href="{{ $href }}" class="db-submenu-link{{ $active ? ' is-active' : '' }}">{{ $label }}</a>
                @endif
            @endforeach
        </nav>
    </div>
</div>
@endif

{{-- Orange "Digital Services Analysis" submenu dropdown. The menu is
     position:fixed and placed under the toggle by JS, so it escapes the submenu
     bar's overflow-x:auto clipping. Plain vanilla &mdash; no Bootstrap dependency. --}}
<script>
(function () {
    var t = document.getElementById('dsAnalysisToggle');
    var m = document.getElementById('dsAnalysisMenu');
    if (!t || !m) return;
    function place() {
        var r = t.getBoundingClientRect();
        m.style.top = (r.bottom + 4) + 'px';
        m.style.left = r.left + 'px';
    }
    function open() { place(); m.classList.add('is-open'); t.setAttribute('aria-expanded', 'true'); }
    function close() { m.classList.remove('is-open'); t.setAttribute('aria-expanded', 'false'); }
    t.addEventListener('click', function (e) {
        e.stopPropagation();
        m.classList.contains('is-open') ? close() : open();
    });
    document.addEventListener('click', function (e) { if (!m.contains(e.target)) close(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
    window.addEventListener('resize', function () { if (m.classList.contains('is-open')) place(); });
    window.addEventListener('scroll', function () { if (m.classList.contains('is-open')) place(); }, true);
})();
</script>

@if ($showBreadcrumbs)
<div class="container">
    <nav class="db-breadcrumb" aria-label="breadcrumb">
        @foreach ($breadcrumbs as $i => $br)
            @if ($i > 0)<span class="db-breadcrumb-sep">/</span>@endif
            @if (!$br[0])
                <span class="is-current" aria-current="page">{{ $br[1] }}</span>
            @else
                <a href="{!! $br[0] !!}">{{ $br[1] }}</a>
            @endif
        @endforeach
    </nav>
</div>
@endif

{{-- Header search typeahead. Debounced fetch of /search/suggest; keyboard
     navigable (&uarr;/&darr;/Enter/Esc); click-out closes. Enter with nothing highlighted
     falls through to the form submit &rarr; full /search page. --}}
<script>
(function () {
    var input = document.getElementById('dbHeaderSearchInput');
    var dd = document.getElementById('dbHeaderSearchDD');
    if (!input || !dd) return;
    var SUGGEST_URL = @json(route('search.suggest'));

    var items = [], active = -1, lastQuery = '', timer = null, ctrl = null;

    function close() {
        dd.hidden = true; dd.innerHTML = ''; items = []; active = -1;
        input.setAttribute('aria-expanded', 'false');
    }

    function setActive(i) {
        if (active > -1 && items[active]) items[active].classList.remove('is-active');
        active = i;
        if (active > -1 && items[active]) {
            items[active].classList.add('is-active');
            items[active].scrollIntoView({ block: 'nearest' });
        }
    }

    function go(el) {
        if (!el) return;
        if (el.dataset.external === '1') window.open(el.dataset.url, '_blank', 'noopener');
        else window.location.href = el.dataset.url;
    }

    function render(suggestions) {
        if (!suggestions.length) { close(); return; }
        dd.innerHTML = '';
        suggestions.forEach(function (s) {
            var a = document.createElement('a');
            a.className = 'db-suggest-item';
            a.href = s.url;
            a.setAttribute('role', 'option');
            a.dataset.url = s.url;
            a.dataset.external = s.external ? '1' : '0';
            if (s.external) { a.target = '_blank'; a.rel = 'noopener'; }
            var title = document.createElement('span');
            title.className = 'db-suggest-title';
            title.textContent = s.title || '';
            var meta = document.createElement('span');
            meta.className = 'db-suggest-meta';
            meta.textContent = s.meta || s.type_label || '';
            a.appendChild(title); a.appendChild(meta);
            a.addEventListener('mousemove', function () { setActive(items.indexOf(a)); });
            // mousedown (not click) fires before the input's blur closes the dropdown.
            a.addEventListener('mousedown', function (e) { e.preventDefault(); go(a); });
            dd.appendChild(a);
        });
        items = Array.prototype.slice.call(dd.querySelectorAll('.db-suggest-item'));
        active = -1;
        dd.hidden = false;
        input.setAttribute('aria-expanded', 'true');
    }

    function fetchSuggest(q) {
        if (ctrl) ctrl.abort();
        ctrl = new AbortController();
        fetch(SUGGEST_URL + '?q=' + encodeURIComponent(q), {
            signal: ctrl.signal, headers: { 'Accept': 'application/json' }
        })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
                if (!data || input.value.trim() !== q) return;  // stale guard
                render(data.suggestions || []);
            })
            .catch(function () { /* aborted or network error - ignore */ });
    }

    input.addEventListener('input', function () {
        var q = input.value.trim();
        if (q === lastQuery) return;
        lastQuery = q;
        clearTimeout(timer);
        if (q.length < 2) { close(); return; }
        timer = setTimeout(function () { fetchSuggest(q); }, 180);
    });

    input.addEventListener('keydown', function (e) {
        if (dd.hidden || !items.length) return;
        if (e.key === 'ArrowDown') { e.preventDefault(); setActive((active + 1) % items.length); }
        else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((active - 1 + items.length) % items.length); }
        else if (e.key === 'Enter') {
            if (active > -1) { e.preventDefault(); go(items[active]); }  // else: form submits -> /search
        }
        else if (e.key === 'Escape') { close(); }
    });

    input.addEventListener('focus', function () {
        if (items.length && input.value.trim().length >= 2) {
            dd.hidden = false; input.setAttribute('aria-expanded', 'true');
        }
    });

    document.addEventListener('click', function (e) {
        if (!e.target.closest || !e.target.closest('.db-header-search')) close();
    });
})();
</script>
