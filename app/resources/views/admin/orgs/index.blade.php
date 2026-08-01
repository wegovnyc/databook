@extends('layout')

@section('menubar')
    @include('sub.menubar', ['active' => 'about'])
@endsection

@section('content')
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        {{-- ⚠ Blade gotcha: a directive glued to a word character is NOT compiled
             and only its @endif is, which 500s the page while `php -l` passes.
             So every conditional phrase on this page is precomputed here. --}}
        @php
            $editorLabel = $editor ? $editor : 'not identified';
            $count = is_array($orgs) ? count($orgs) : 0;
        @endphp

        <div class="d-flex justify-content-between align-items-start flex-wrap gap-3 mb-4">
            <div>
                <div class="db-eyebrow">Admin</div>
                <h1>Org register</h1>
                <p class="db-page-lead">
                    The system of record for {{ number_format($count) }} organizations.
                    Editing is audited and attributed.
                </p>
            </div>
            <div class="text-end">
                <div class="db-meta">Signed in as</div>
                <div><strong>{{ $editorLabel }}</strong></div>
            </div>
        </div>

        <x-db.alert type="info" class="mb-4">
            <strong>Renaming an organization is not cosmetic.</strong>
            <code>name</code> is how contracts are matched to this org, so a rename
            can zero its procurement figures. To change what the public sees, edit
            <strong>Display name</strong> instead. The editor will warn you and show
            how many contracts are affected before allowing it.
        </x-db.alert>

        <div class="row g-3 mb-4">
            <div class="col-md-8">
                <input type="search" id="orgFilter" class="form-control form-control-lg"
                       placeholder="Search by name, id or type…" autocomplete="off"
                       value="{{ $q }}">
            </div>
            <div class="col-md-4 text-md-end">
                <x-db.button type="button" id="newOrgBtn">
                    <x-db.icon name="plus-lg" /> New organization
                </x-db.button>
            </div>
        </div>

        {{-- create form, hidden until asked for --}}
        <div id="newOrgPanel" class="db-card mb-4" style="display:none;">
            <div class="db-card-body">
                <h2 class="h5 mb-3">New organization</h2>
                <div class="row g-3">
                    <div class="col-md-6">
                        <label class="form-label" for="newName">Name <span class="text-danger">*</span></label>
                        <input class="form-control" id="newName" autocomplete="off">
                        <div class="db-meta mt-1">This becomes the contract join key. Use the operative name.</div>
                    </div>
                    <div class="col-md-6">
                        <label class="form-label" for="newType">Type <span class="text-danger">*</span></label>
                        <select class="form-select" id="newType">
                            <option value="">Choose…</option>
                        </select>
                        <div class="db-meta mt-1">Loaded from the server's vocabulary — free text is not accepted.</div>
                    </div>
                </div>
                <div class="mt-3 d-flex gap-2">
                    <x-db.button type="button" id="newOrgSave">Create</x-db.button>
                    <x-db.button type="button" variant="secondary" id="newOrgCancel">Cancel</x-db.button>
                </div>
                <div id="newOrgResult" class="mt-3"></div>
            </div>
        </div>

        <x-db.table-wrap>
            <table class="db-table" id="orgTable">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Type</th>
                        <th class="text-end">ID</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>
                @foreach ($orgs as $o)
                    @php
                        $oid = $o['id'] ?? '';
                        $oname = $o['name'] ?? '';
                        $otype = $o['type'] ?? '';
                        $odisp = $o['display_name'] ?? '';
                        $hay = strtolower($oname . ' ' . $otype . ' ' . $oid . ' ' . $odisp);
                    @endphp
                    <tr data-hay="{{ $hay }}">
                        <td>
                            <a href="{{ route('admin.orgs.edit', ['id' => $oid]) }}">{{ $oname }}</a>
                            @if ($odisp)
                                <div class="db-meta">shown publicly as {{ $odisp }}</div>
                            @endif
                        </td>
                        <td>{{ $otype }}</td>
                        <td class="text-end"><code>{{ $oid }}</code></td>
                        <td class="text-end">
                            <a class="db-btn db-btn-sm db-btn-secondary"
                               href="{{ route('admin.orgs.edit', ['id' => $oid]) }}">Edit</a>
                        </td>
                    </tr>
                @endforeach
                </tbody>
            </table>
        </x-db.table-wrap>
        <div id="orgEmpty" class="mt-4" style="display:none;">
            <x-db.empty title="No organizations match that search"
                        body="Try part of a name, a type, or an id." />
        </div>
    </div>
</div>

<script>
(function () {
    var filter = document.getElementById('orgFilter');
    var rows = Array.prototype.slice.call(
        document.querySelectorAll('#orgTable tbody tr'));
    var empty = document.getElementById('orgEmpty');

    function apply() {
        var q = (filter.value || '').trim().toLowerCase();
        var shown = 0;
        rows.forEach(function (r) {
            var hit = !q || r.getAttribute('data-hay').indexOf(q) !== -1;
            r.style.display = hit ? '' : 'none';
            if (hit) shown++;
        });
        empty.style.display = shown ? 'none' : '';
    }
    filter.addEventListener('input', apply);
    if (filter.value) apply();

    // ── create ───────────────────────────────────────────────────────────────
    var panel = document.getElementById('newOrgPanel');
    var typeSel = document.getElementById('newType');

    // The vocabulary is rendered by the server, so this page cannot invent a
    // type and does not depend on a second request succeeding.
    @json($types ?? []).forEach(function (t) {
        var o = document.createElement('option');
        o.value = t; o.textContent = t;
        typeSel.appendChild(o);
    });

    document.getElementById('newOrgBtn').addEventListener('click', function () {
        panel.style.display = panel.style.display === 'none' ? '' : 'none';
    });

    document.getElementById('newOrgCancel').addEventListener('click', function () {
        panel.style.display = 'none';
    });

    document.getElementById('newOrgSave').addEventListener('click', function () {
        var out = document.getElementById('newOrgResult');
        out.innerHTML = '<div class="db-meta">Creating…</div>';
        fetch('{{ route('admin.orgs.create') }}', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-CSRF-TOKEN': '{{ csrf_token() }}'
            },
            body: JSON.stringify({
                name: document.getElementById('newName').value,
                type: typeSel.value
            })
        }).then(function (r) {
            return r.json().then(function (d) { return {status: r.status, body: d}; });
        }).then(function (res) {
            if (res.status === 200 && res.body.id) {
                out.innerHTML = '<div class="db-alert db-alert-success">Created. Opening…</div>';
                window.location = '{{ url('/admin/orgs') }}/' + res.body.id;
                return;
            }
            out.innerHTML = '<div class="db-alert db-alert-danger">'
                + escapeHtml(detailOf(res.body)) + '</div>';
        }).catch(function (e) {
            out.innerHTML = '<div class="db-alert db-alert-danger">'
                + escapeHtml(String(e)) + '</div>';
        });
    });

    function detailOf(body) {
        if (!body) return 'No response from the server.';
        var d = body.detail !== undefined ? body.detail : body;
        if (typeof d === 'string') return d;
        return JSON.stringify(d, null, 1);
    }
    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, function (c) {
            return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
        });
    }
})();
</script>
@endsection
