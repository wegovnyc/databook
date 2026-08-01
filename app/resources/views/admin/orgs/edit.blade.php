@extends('layout')

@section('menubar')
    @include('sub.menubar', ['active' => 'about'])
@endsection

@section('content')
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        {{-- ⚠ Every conditional phrase is precomputed. A Blade directive glued to
             a word character is not compiled and only its @endif is, which 500s
             the page while `php -l` passes clean. --}}
        @php
            $oid          = $org['id'] ?? '';
            $oname        = $org['name'] ?? '';
            $retiredAt    = $org['retired_at'] ?? null;
            $mergedName   = $org['merged_into_name'] ?? null;
            $mergedId     = $org['merged_into'] ?? null;
            $parentId     = $org['parent_org_id'] ?? null;
            $parentName   = $org['parent_name'] ?? null;
            $inChart      = array_key_exists('in_org_chart', $org) ? $org['in_org_chart'] : null;
            $contracts    = $renameImpact['contracts_matching_name'] ?? null;
            $editorLabel  = $editor ? $editor : 'not identified';
            $isRetired    = !empty($retiredAt);
            $chartState   = ($inChart === null || $inChart === '')
                                ? '' : ($inChart ? '1' : '0');
            $contractsLabel = $contracts === null
                ? 'not measurable in this environment'
                : number_format($contracts) . ' contract(s) currently match this name';
            // Text fields rendered generically, in a deliberate order.
            $textFields = [
                'display_name'   => 'Display name',
                'alternate_name' => 'Alternate name / acronym',
                'url'            => 'Website',
                'main_phone'     => 'Phone',
                'main_address'   => 'Address',
                'code'           => 'Code',
                'description'    => 'Description',
                'internal_notes' => 'Internal notes',
            ];
        @endphp

        <div class="d-flex justify-content-between align-items-start flex-wrap gap-3 mb-4">
            <div>
                <div class="db-eyebrow"><a href="{{ route('admin.orgs') }}">Org register</a></div>
                <h1 class="mb-1">{{ $oname }}</h1>
                <div class="db-meta">
                    id <code>{{ $oid }}</code>
                    &middot; <a href="/organization/{{ $oid }}" target="_blank" rel="noopener">view public profile</a>
                </div>
            </div>
            <div class="text-end">
                <div class="db-meta">Editing as</div>
                <div><strong>{{ $editorLabel }}</strong></div>
            </div>
        </div>

        @if ($isRetired)
            <x-db.alert type="warning" class="mb-4">
                <strong>This organization is retired.</strong>
                @if ($mergedName)
                    It was merged into <a href="{{ route('admin.orgs.edit', ['id' => $mergedId]) }}">{{ $mergedName }}</a>,
                    which is the record to use.
                @endif
                Retirement is reversible — match rows and ingested ids still resolve through it.
                <div class="mt-2">
                    <x-db.button type="button" variant="secondary" id="unretireBtn">Un-retire</x-db.button>
                </div>
            </x-db.alert>
        @endif

        <div id="result" class="mb-4"></div>

        <div class="row g-4">
            <div class="col-lg-7">
                <div class="db-card mb-4">
                    <div class="db-card-body">
                        <h2 class="h5 mb-3">Identity</h2>

                        <div class="mb-3">
                            <label class="form-label" for="f_name">Name</label>
                            <input class="form-control" id="f_name" data-field="name"
                                   value="{{ $oname }}" autocomplete="off">
                            <div class="db-meta mt-1">
                                <x-db.icon name="exclamation-triangle" />
                                <strong>This is a join key, not a label.</strong>
                                Contracts are matched to this org by this exact name —
                                {{ $contractsLabel }}. Changing it can zero this org's
                                procurement figures. To change the name the public sees,
                                use <strong>Display name</strong> below. You will be asked
                                to confirm.
                            </div>
                        </div>

                        <div class="mb-3">
                            <label class="form-label" for="f_type">Type</label>
                            <select class="form-select" id="f_type" data-field="type">
                                @foreach ($types as $t)
                                    <option value="{{ $t }}" @if (($org['type'] ?? '') === $t) selected @endif>{{ $t }}</option>
                                @endforeach
                            </select>
                            <div class="db-meta mt-1">
                                Drives the directory, the org chart, the agencies page and
                                the Greenbook enrichment. Only values the server recognises
                                are offered — a free-text type makes an org vanish from those
                                pages with no error.
                            </div>
                        </div>

                        @foreach ($textFields as $field => $label)
                            @php $val = $org[$field] ?? ''; @endphp
                            @if (in_array($field, $editableFields, true))
                                <div class="mb-3">
                                    <label class="form-label" for="f_{{ $field }}">{{ $label }}</label>
                                    @if ($field === 'description' || $field === 'internal_notes')
                                        <textarea class="form-control" id="f_{{ $field }}"
                                                  data-field="{{ $field }}" rows="3">{{ $val }}</textarea>
                                    @else
                                        <input class="form-control" id="f_{{ $field }}"
                                               data-field="{{ $field }}" value="{{ $val }}"
                                               autocomplete="off">
                                    @endif
                                    @if ($field === 'display_name')
                                        <div class="db-meta mt-1">
                                            What the public sees. Safe to change — this is where
                                            an official longer name belongs.
                                        </div>
                                    @endif
                                </div>
                            @endif
                        @endforeach
                    </div>
                </div>

                <div class="db-card mb-4">
                    <div class="db-card-body">
                        <h2 class="h5 mb-3">Place in the organization</h2>

                        <div class="mb-3">
                            <label class="form-label" for="f_parent">Reports to</label>
                            <select class="form-select" id="f_parent" data-field="parent_org_id">
                                <option value="">— no parent —</option>
                                @foreach ($orgs as $cand)
                                    @php $cid = $cand['id'] ?? ''; @endphp
                                    @if ((string)$cid !== (string)$oid)
                                        <option value="{{ $cid }}" @if ((string)$parentId === (string)$cid) selected @endif>{{ $cand['name'] ?? '' }}</option>
                                    @endif
                                @endforeach
                            </select>
                            <div class="db-meta mt-1">
                                A real reference, so a parent that does not exist is
                                impossible. The server also refuses a parent that is retired
                                or that would create a loop — a loop would break the whole
                                org chart, not just this row.
                            </div>
                        </div>

                        <div class="mb-3">
                            <label class="form-label" for="f_chart">On the org chart</label>
                            <select class="form-select" id="f_chart" data-field="in_org_chart">
                                <option value=""  @if ($chartState === '')  selected @endif>Not stated</option>
                                <option value="1" @if ($chartState === '1') selected @endif>Yes</option>
                                <option value="0" @if ($chartState === '0') selected @endif>No</option>
                            </select>
                            <div class="db-meta mt-1">
                                "Not stated" is a real answer and is not the same as No — an
                                org nobody has an opinion about stays on the chart.
                            </div>
                        </div>
                    </div>
                </div>

                <div class="d-flex gap-2 mb-4">
                    <x-db.button type="button" id="saveBtn">Save changes</x-db.button>
                    <a class="db-btn db-btn-secondary" href="{{ route('admin.orgs') }}">Cancel</a>
                </div>

                @if (!$isRetired)
                    <div class="db-card mb-4">
                        <div class="db-card-body">
                            <h2 class="h5 mb-2">Retire this organization</h2>
                            <p class="db-meta">
                                Organizations are never deleted. Retiring keeps every existing
                                reference resolving and is reversible — you must say which
                                record supersedes this one.
                            </p>
                            <div class="row g-2 align-items-end">
                                <div class="col-md-8">
                                    <label class="form-label" for="f_merged">Merged into</label>
                                    <select class="form-select" id="f_merged">
                                        <option value="">Choose the surviving record…</option>
                                        @foreach ($orgs as $cand)
                                            @php $cid = $cand['id'] ?? ''; @endphp
                                            @if ((string)$cid !== (string)$oid)
                                                <option value="{{ $cid }}">{{ $cand['name'] ?? '' }}</option>
                                            @endif
                                        @endforeach
                                    </select>
                                </div>
                                <div class="col-md-4">
                                    <x-db.button type="button" variant="secondary" id="retireBtn">Retire</x-db.button>
                                </div>
                            </div>
                        </div>
                    </div>
                @endif
            </div>

            <div class="col-lg-5">
                <div class="db-card">
                    <div class="db-card-body">
                        <h2 class="h5 mb-3">History</h2>
                        @if (count($audit))
                            <ul class="list-unstyled mb-0">
                                @foreach ($audit as $a)
                                    @php
                                        $when = $a['at'] ?? '';
                                        try {
                                            $dt = new \DateTime($when);
                                            $dt->setTimezone(new \DateTimeZone('America/New_York'));
                                            $whenLabel = $dt->format('M j, Y g:ia');
                                        } catch (\Exception $e) {
                                            $whenLabel = $when;
                                        }
                                        $fieldLabel = $a['field'] ?? '';
                                        $oldV = $a['old_value'] ?? '';
                                        $newV = $a['new_value'] ?? '';
                                    @endphp
                                    <li class="pb-3 mb-3" style="border-bottom:1px solid var(--db-border);">
                                        <div>
                                            <strong>{{ $a['action'] ?? '' }}</strong>
                                            @if ($fieldLabel)
                                                <code>{{ $fieldLabel }}</code>
                                            @endif
                                        </div>
                                        @if ($newV !== '' || $oldV !== '')
                                            <div class="db-meta">{{ $oldV }} &rarr; {{ $newV }}</div>
                                        @endif
                                        <div class="db-meta">{{ $whenLabel }} by {{ $a['actor'] ?? '' }}</div>
                                        @if (!empty($a['note']))
                                            <div class="db-meta">{{ $a['note'] }}</div>
                                        @endif
                                    </li>
                                @endforeach
                            </ul>
                        @else
                            <p class="db-meta mb-0">No recorded changes yet.</p>
                        @endif
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
(function () {
    var ORG_ID = @json($oid);
    var SAVE   = @json(route('admin.orgs.save', ['id' => $oid]));
    var RETIRE = @json(route('admin.orgs.retire', ['id' => $oid]));
    var UNRET  = @json(route('admin.orgs.unretire', ['id' => $oid]));
    var TOKEN  = @json(csrf_token());
    var out    = document.getElementById('result');

    // The stored values, so only genuine edits are sent.
    var original = {};
    fields().forEach(function (el) { original[el.getAttribute('data-field')] = el.value; });

    function fields() {
        return Array.prototype.slice.call(document.querySelectorAll('[data-field]'));
    }

    function changed() {
        var body = {};
        fields().forEach(function (el) {
            var f = el.getAttribute('data-field');
            if (el.value === original[f]) return;
            var v = el.value;
            if (f === 'parent_org_id')  v = v === '' ? null : parseInt(v, 10);
            if (f === 'in_org_chart')   v = v === '' ? null : (v === '1');
            body[f] = v;
        });
        return body;
    }

    function say(kind, html) {
        out.innerHTML = '<div class="db-alert db-alert-' + kind + '">' + html + '</div>';
        out.scrollIntoView({behavior: 'smooth', block: 'nearest'});
    }

    function esc(s) {
        return String(s).replace(/[&<>"']/g, function (c) {
            return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
        });
    }

    function post(url, body, method) {
        return fetch(url, {
            method: method || 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-CSRF-TOKEN': TOKEN
            },
            body: JSON.stringify(body)
        }).then(function (r) {
            return r.json().catch(function () { return {}; })
                    .then(function (d) { return {status: r.status, body: d}; });
        });
    }

    function send(body) {
        say('info', 'Saving…');
        post(SAVE, body, 'PATCH').then(function (res) {
            // ⚠ 409 is the rename guard, and it is the reason this page does not
            // decide for itself whether a rename is safe. Show the server's
            // reasoning and the blast radius, then offer the confirmation.
            if (res.status === 409 && res.body && res.body.detail && res.body.detail.why) {
                var d = res.body.detail;
                var n = (d.impact && d.impact.contracts_matching_name !== null &&
                         d.impact.contracts_matching_name !== undefined)
                        ? d.impact.contracts_matching_name : null;
                say('warning',
                    '<strong>Confirm this rename</strong>'
                    + '<p class="mb-2">' + esc(d.why) + '</p>'
                    + '<p class="mb-2"><code>' + esc(d.from) + '</code> &rarr; <code>'
                    + esc(d.to) + '</code>'
                    + (n === null ? '' : ' — <strong>' + n
                        + '</strong> contract(s) match the current name and would stop matching')
                    + '</p>'
                    + '<button type="button" class="db-btn db-btn-sm" id="confirmRename">'
                    + 'Yes, rename it anyway</button> '
                    + '<button type="button" class="db-btn db-btn-sm db-btn-secondary" '
                    + 'id="cancelRename">Keep the current name</button>');
                document.getElementById('confirmRename').addEventListener('click', function () {
                    body.confirm_rename = true;
                    send(body);
                });
                document.getElementById('cancelRename').addEventListener('click', function () {
                    document.getElementById('f_name').value = original['name'];
                    out.innerHTML = '';
                });
                return;
            }
            if (res.status !== 200) {
                say('danger', '<strong>Not saved.</strong><br>' + esc(detail(res.body)));
                return;
            }
            var warn = (res.body.warnings || []).map(function (w) {
                return '<li>' + esc(w) + '</li>';
            }).join('');
            var n = Object.keys(res.body.changed || {}).length;
            say(warn ? 'warning' : 'success',
                (n ? '<strong>Saved ' + n + ' change(s).</strong>'
                   : '<strong>Nothing to save</strong> — no field differed from its stored value.')
                + (warn ? '<ul class="mb-0 mt-2">' + warn + '</ul>' : ''));
            if (n) setTimeout(function () { window.location.reload(); }, 1200);
        }).catch(function (e) {
            say('danger', esc(String(e)));
        });
    }

    function detail(body) {
        if (!body) return 'No response from the server.';
        var d = body.detail !== undefined ? body.detail : body;
        if (typeof d === 'string') return d;
        return JSON.stringify(d, null, 1);
    }

    document.getElementById('saveBtn').addEventListener('click', function () {
        var body = changed();
        if (!Object.keys(body).length) {
            say('info', 'No changes to save.');
            return;
        }
        send(body);
    });

    var retireBtn = document.getElementById('retireBtn');
    if (retireBtn) {
        retireBtn.addEventListener('click', function () {
            var into = document.getElementById('f_merged').value;
            if (!into) {
                say('warning', 'Choose the record that supersedes this one first — '
                    + 'existing references have to keep resolving to something.');
                return;
            }
            post(RETIRE, {merged_into: parseInt(into, 10)}).then(function (res) {
                if (res.status !== 200) {
                    say('danger', '<strong>Not retired.</strong><br>' + esc(detail(res.body)));
                    return;
                }
                var warn = (res.body.warnings || []).map(function (w) {
                    return '<li>' + esc(w) + '</li>';
                }).join('');
                say(warn ? 'warning' : 'success',
                    '<strong>Retired into ' + esc(res.body.successor || '') + '.</strong>'
                    + (warn ? '<ul class="mb-0 mt-2">' + warn + '</ul>' : ''));
                setTimeout(function () { window.location.reload(); }, 1800);
            });
        });
    }

    var unretireBtn = document.getElementById('unretireBtn');
    if (unretireBtn) {
        unretireBtn.addEventListener('click', function () {
            post(UNRET, {}).then(function (res) {
                if (res.status !== 200) {
                    say('danger', esc(detail(res.body)));
                    return;
                }
                say('success', '<strong>Un-retired.</strong>');
                setTimeout(function () { window.location.reload(); }, 1200);
            });
        });
    }
})();
</script>
@endsection
