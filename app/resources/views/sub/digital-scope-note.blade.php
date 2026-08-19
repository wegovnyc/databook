{{--
  ONE scope note, included verbatim by all three Digital Services pages.

  ⚠ WHY IT IS A PARTIAL. Until 2026-08-13 the section had two definitions of
  "digital" serving at once and each page explained itself differently — the
  Overview said "tagged in database", the queue said "digital contract", the
  Licenses page carried the real methodology. A reader comparing two pages had no
  way to learn they were looking at two different universes. One file, three
  includes, and a guard asserts all three include it.

  ⚠ THE PERCENTAGES HERE ARE TYPED, DELIBERATELY, AND THEY ARE THE ONLY ONES
  ALLOWED TO BE. They come from api/eval_contract_classifier.py, an offline
  harness that scores the classifier against labels on a fixed stratified sample
  — the page cannot compute them, and stating them with their sample size and
  date is what makes them a measurement rather than a claim. Every figure the
  page CAN compute comes from the payload. See the guard in
  api/tests/test_license_families.py.

  Takes $scope (optional) from the payload so the note states the live scope mode
  rather than assuming it.
--}}
@php
    $scopeMode = $scope['mode'] ?? 'derived';
    $scopePositive = (bool) ($scope['positive'] ?? ($scopeMode === 'derived'));
@endphp
<details class="db-alert db-alert-neutral ds-scope-note mb-4">
    <summary>
        <i class="bi bi-rulers"></i>
        <strong>What counts as technology here</strong>
        <span class="text-muted">&mdash; scope, accuracy and the blind spot</span>
    </summary>
    <div class="db-alert-body">
        @if($scopePositive)
        <p>
            Every registered City contract that an AI classification pass <strong>confirmed is
            technology</strong>, one row per contract, valued at its current amount where one
            exists and its original award otherwise. A contract is in scope because the
            classification says so &mdash; not because its vendor's <em>name</em> looked
            technical, which is how a physical-guard company once ranked fifth on this section's
            vendor table.
        </p>
        @else
        <p>
            <strong>Rolled back to the older vendor-name scope.</strong> Contracts are in scope
            because their vendor appears on a hand-kept list of ~200 names, at amendment-row
            grain. That list was measured 85.2% precise and covered 2.9% of City vendors; these
            figures are the ones this section published before 2026-08-13.
        </p>
        @endif
        <p class="mb-0">
            <strong>Accuracy, measured rather than asserted.</strong> Scored against labels on a
            stratified 120-contract sample drawn from the whole population (August 2026), the
            model used for the bulk run agreed on <em>is this technology</em> 95.8% of the time
            and on <em>is this a licence</em> 97.5%. Both were 100% on the rows it marked
            high-confidence. The labels are themselves AI-adjudicated, so treat them as a
            careful second opinion, not ground truth.
        </p>
        <p class="mb-0 mt-2">
            <strong>The blind spot.</strong> PASSPort assigns a contract id at
            <em>registration</em>, and every figure in this section keys on it &mdash; so
            agreements still in approval are excluded from every total, including citywide
            purchasing vehicles worth more than some of the totals themselves. They are listed
            separately on the
            <a href="{{ route('research.digital-reform') }}#pipeline">Overview</a>, as ceilings,
            never added in.
        </p>
        <p class="mb-0 mt-2 text-muted" style="font-size: var(--db-text-sm);">
            This is an analysis, not an inventory: figures move as curation lands, and the
            section says which judgements are hand-reviewed and which are automatic.
        </p>
    </div>
</details>
