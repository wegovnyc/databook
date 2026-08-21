<?php
namespace App\Custom;

/**
 * Data + ranking logic for the Renewal Review Queue (/procurement/renewals).
 *
 * Source note: the nine contracts below are the same example records shipped
 * with the design handoff (design_handoff_renewal_queue/README.md) — realistic
 * placeholders, not live Checkbook data. The README's recommended production
 * shape is a `renewal_assessments` table (editorial fields only) joined to the
 * real Checkbook contracts table at query time via a new `/oce/renewals` API
 * endpoint, the same way every other /procurement/* page reads through
 * DatabookAPI::reqOCE(). This class is a stand-in for that endpoint so the
 * two pages are fully working today; swap `contracts()` for a DatabookAPI
 * call (keeping only the editorial fields here) when that endpoint exists.
 */
class RenewalsDatasets
{
    const AGENCY_NAMES = [
        'DHS'   => 'Department of Homeless Services',
        'OTI'   => 'Office of Technology and Innovation',
        'OMB'   => 'Office of Management and Budget',
        'DCAS'  => 'Department of Citywide Administrative Services',
        '311'   => 'NYC 311 Customer Service Center',
        'DCP'   => 'Department of City Planning',
        'FISA'  => 'Financial Information Services Agency',
        'DoITT' => 'Department of Information Technology and Telecommunications',
        'DOT'   => 'Department of Transportation',
    ];

    const EFFORT_TONE = ['Low' => 'success', 'Medium' => 'warning', 'High' => 'danger'];
    const EFFORT_PENALTY = ['Low' => 0, 'Medium' => 12, 'High' => 26];

    const VIEWS = [
        'expiring' => [
            'label' => 'Expiring soon',
            'blurb' => 'Ordered by days until the renewal decision has to be made. Contracts renew automatically unless an agency acts.',
        ],
        'heavy' => [
            'label' => 'Heaviest hitters',
            'blurb' => 'Ordered by the value of the coming renewal — the money the city would not spend if the contract lapsed.',
        ],
        'easy' => [
            'label' => 'Easiest grabs',
            'blurb' => 'Ordered by how replaceable the contract is: how many open-source alternatives exist, weighed against how hard the switch would be.',
        ],
    ];

    /** Raw contract records. `days_left` is never stored — see daysLeft(). */
    public static function contracts(): array
    {
        return [
            ['id' => 'CT1-85800-20260007', 'purpose' => 'Proprietary case-management platform for shelter intake', 'agency' => 'DHS', 'vendor' => 'Accenture LLP', 'expires' => '2026-09-30', 'renewal' => 18400000, 'term' => '3 years', 'spend' => 51200000, 'since' => 2017, 'users' => '2,400 caseworkers', 'method' => 'Sole source renewal', 'story' => true, 'replaceable' => true, 'ossCount' => 4, 'effort' => 'Low', 'effortNote' => 'Intake, referral and case notes map cleanly onto existing open-source case management. Data export is contractually guaranteed.', 'options' => [
                ['n' => 'OpenCaseBook', 'l' => 'Apache-2.0', 'note' => 'Used by two county human-services agencies'],
                ['n' => 'Bahmni HSS module', 'l' => 'AGPL-3.0', 'note' => 'Active maintainers, hosted options exist'],
                ['n' => 'Ushahidi Casework', 'l' => 'AGPL-3.0', 'note' => 'Requires intake form work'],
                ['n' => 'OpenReferral HSDS stack', 'l' => 'CC-BY', 'note' => 'Standards-based referral directory'],
            ], 'sources' => ['Checkbook NYC — contract CT1-85800-20260007', 'MOCS award notice, City Record 2023-04-11', 'FY26 Adopted Budget, DHS OTPS schedule']],

            ['id' => 'CT1-85601-20260118', 'purpose' => 'Enterprise document e-signature licensing', 'agency' => 'OTI', 'vendor' => 'DocuSign Inc.', 'expires' => '2026-10-15', 'renewal' => 6900000, 'term' => '2 years', 'spend' => 21400000, 'since' => 2019, 'users' => '31 agencies', 'method' => 'Citywide requirements contract', 'story' => false, 'replaceable' => true, 'ossCount' => 5, 'effort' => 'Low', 'effortNote' => 'Mature open-source signing stacks exist and several other US cities have migrated. Main cost is credential issuance, not software.', 'options' => [
                ['n' => 'Docuseal', 'l' => 'AGPL-3.0', 'note' => 'Drop-in workflow parity for standard forms'],
                ['n' => 'OpenSign', 'l' => 'GPL-3.0', 'note' => 'Self-hosted, audit trail included'],
                ['n' => 'DSS (EU Digital Signature Service)', 'l' => 'LGPL-2.1', 'note' => 'eIDAS-grade cryptography'],
                ['n' => 'Documenso', 'l' => 'AGPL-3.0', 'note' => 'Hosted or self-hosted'],
                ['n' => 'SignServer', 'l' => 'LGPL-2.1', 'note' => 'Enterprise signing appliance replacement'],
            ], 'sources' => ['Checkbook NYC — payments through FY26 Q3', 'DCAS citywide contract register', 'OTI technology inventory (FOIL response, 2025-08)']],

            ['id' => 'CT1-82600-20260044', 'purpose' => 'Business intelligence dashboard licenses', 'agency' => 'OMB', 'vendor' => 'Tableau / Salesforce', 'expires' => '2026-11-01', 'renewal' => 4200000, 'term' => '1 year', 'spend' => 14800000, 'since' => 2016, 'users' => '1,150 named seats', 'method' => 'Software license renewal', 'story' => false, 'replaceable' => true, 'ossCount' => 6, 'effort' => 'Medium', 'effortNote' => 'Dashboards must be rebuilt, but the underlying warehouse is already Postgres. Roughly 40 published workbooks are in active use.', 'options' => [
                ['n' => 'Apache Superset', 'l' => 'Apache-2.0', 'note' => 'Closest feature match; Postgres native'],
                ['n' => 'Metabase (OSS edition)', 'l' => 'AGPL-3.0', 'note' => 'Fastest analyst onboarding'],
                ['n' => 'Grafana', 'l' => 'AGPL-3.0', 'note' => 'Best for operational metrics'],
                ['n' => 'Redash', 'l' => 'BSD-2', 'note' => 'Query-first teams'],
            ], 'sources' => ['Checkbook NYC — OMB OTPS payments', 'Comptroller audit FN25-104A', 'MOCS solicitation record 20260044']],

            ['id' => 'CT1-84102-20261209', 'purpose' => 'Video conferencing and webinar licensing', 'agency' => 'DCAS', 'vendor' => 'Zoom Communications', 'expires' => '2026-12-09', 'renewal' => 3100000, 'term' => '2 years', 'spend' => 11600000, 'since' => 2020, 'users' => '48,000 accounts', 'method' => 'Emergency-era extension', 'story' => false, 'replaceable' => true, 'ossCount' => 3, 'effort' => 'High', 'effortNote' => 'Software substitutes exist but public-hearing streaming, captioning and phone bridging obligations make a full cutover slow.', 'options' => [
                ['n' => 'Jitsi Meet', 'l' => 'Apache-2.0', 'note' => 'Scales with SFU cluster; captions via plugin'],
                ['n' => 'BigBlueButton', 'l' => 'LGPL-3.0', 'note' => 'Strong for hearings and classrooms'],
                ['n' => 'Element Call / Matrix', 'l' => 'AGPL-3.0', 'note' => 'Federated, no per-seat licensing'],
            ], 'sources' => ['Checkbook NYC — DCAS technology payments', 'City Record extension notice, 2024-11-22']],

            ['id' => 'CT1-85601-20260907', 'purpose' => 'Constituent 311 chatbot and AI triage add-on', 'agency' => '311', 'vendor' => 'Verint Systems', 'expires' => '2026-09-07', 'renewal' => 2750000, 'term' => '1 year', 'spend' => 8200000, 'since' => 2022, 'users' => '311 web + app', 'method' => 'Change order to master agreement', 'story' => false, 'replaceable' => true, 'ossCount' => 4, 'effort' => 'Medium', 'effortNote' => 'The triage model is the replaceable part; the CRM integration is not. A staged replacement of the chat layer alone captures most of the savings.', 'options' => [
                ['n' => 'Rasa Open Source', 'l' => 'Apache-2.0', 'note' => 'Intent routing with on-prem hosting'],
                ['n' => 'Botpress OSS', 'l' => 'MIT', 'note' => 'Visual flow editor for non-engineers'],
                ['n' => 'Typesense + RAG service', 'l' => 'GPL-3.0', 'note' => 'Knowledge-base answers over 311 content'],
            ], 'sources' => ['311 annual performance report FY25', 'Checkbook NYC — change order CT1-85601-20260907']],

            ['id' => 'CT1-82700-20260311', 'purpose' => 'Geospatial mapping platform enterprise agreement', 'agency' => 'DCP', 'vendor' => 'Esri Inc.', 'expires' => '2027-03-31', 'renewal' => 9600000, 'term' => '3 years', 'spend' => 38900000, 'since' => 2011, 'users' => '19 agencies', 'method' => 'Enterprise license agreement', 'story' => false, 'replaceable' => false, 'ossCount' => 5, 'effort' => 'High', 'effortNote' => 'Not recommended for cancellation. Regulatory zoning workflows, licensed extensions and 15 years of models are embedded. Partial migration of public-facing maps is viable.', 'options' => [
                ['n' => 'QGIS', 'l' => 'GPL-2.0', 'note' => 'Desktop parity for most analyst work'],
                ['n' => 'PostGIS + pg_tileserv', 'l' => 'GPL-2.0', 'note' => 'Serving layer already in use internally'],
                ['n' => 'MapLibre GL', 'l' => 'BSD-3', 'note' => 'Public-facing map viewers'],
            ], 'sources' => ['DCP technology roster, 2025', 'Checkbook NYC — Esri payments 2011–2026']],

            ['id' => 'CT1-85800-20261028', 'purpose' => 'Legacy mainframe payroll maintenance and support', 'agency' => 'FISA', 'vendor' => 'IBM Corporation', 'expires' => '2026-10-28', 'renewal' => 12300000, 'term' => '2 years', 'spend' => 96400000, 'since' => 2004, 'users' => 'City payroll (300K+)', 'method' => 'Sole source maintenance', 'story' => false, 'replaceable' => false, 'ossCount' => 1, 'effort' => 'High', 'effortNote' => 'No credible open-source replacement for a live COBOL payroll of this size. Savings here come from renegotiation and modernization planning, not cancellation.', 'options' => [
                ['n' => 'GnuCOBOL', 'l' => 'GPL-3.0', 'note' => 'Compiler only; does not replace the platform'],
            ], 'sources' => ['FISA-OPA budget testimony, FY26', 'Comptroller contract register']],

            ['id' => 'CT1-84102-20260822', 'purpose' => 'Website content management licensing and hosting', 'agency' => 'DoITT', 'vendor' => 'Adobe Experience Manager', 'expires' => '2026-08-22', 'renewal' => 5400000, 'term' => '1 year', 'spend' => 27300000, 'since' => 2015, 'users' => '62 agency sites', 'method' => 'Annual license renewal', 'story' => false, 'replaceable' => true, 'ossCount' => 6, 'effort' => 'Medium', 'effortNote' => 'Editorial teams need retraining and 62 sites must be migrated in waves, but every technical requirement has an open-source equivalent in production elsewhere.', 'options' => [
                ['n' => 'Drupal (govCMS profile)', 'l' => 'GPL-2.0', 'note' => 'Used by dozens of governments'],
                ['n' => 'WordPress multisite', 'l' => 'GPL-2.0', 'note' => 'Lowest editorial retraining cost'],
                ['n' => 'Wagtail', 'l' => 'BSD-3', 'note' => 'Strong accessibility defaults'],
                ['n' => 'Strapi', 'l' => 'MIT', 'note' => 'Headless option for app-driven sites'],
            ], 'sources' => ['Checkbook NYC — DoITT software payments', 'NYC.gov platform inventory, 2025-06']],

            ['id' => 'CT1-82600-20270115', 'purpose' => 'Parking and curb permit management system', 'agency' => 'DOT', 'vendor' => 'Conduent Government', 'expires' => '2027-01-15', 'renewal' => 7100000, 'term' => '3 years', 'spend' => 44100000, 'since' => 2013, 'users' => 'Citywide curb ops', 'method' => 'Request for proposals', 'story' => false, 'replaceable' => true, 'ossCount' => 2, 'effort' => 'High', 'effortNote' => 'Payment reconciliation and enforcement handhelds are proprietary; a replacement would need custom integration work before the permit layer can move.', 'options' => [
                ['n' => 'CurbLR', 'l' => 'Apache-2.0', 'note' => 'Open curb regulation data standard'],
                ['n' => 'Open Parking Suite', 'l' => 'MIT', 'note' => 'Permit issuance only, no enforcement'],
            ], 'sources' => ['Checkbook NYC — Conduent payments', 'MOCS RFP award, City Record 2024-01-08']],
        ];
    }

    public static function agencyName(string $code): ?string
    {
        return self::AGENCY_NAMES[$code] ?? null;
    }

    public static function daysLeft(array $contract): int
    {
        return (int) now()->startOfDay()->diffInDays(\Carbon\Carbon::parse($contract['expires']), false);
    }

    public static function easeScore(array $c): int
    {
        if (!$c['replaceable']) return 0;
        return $c['ossCount'] * 10 - self::EFFORT_PENALTY[$c['effort']];
    }

    public static function compact(int $n): string
    {
        if ($n >= 1e9) return '$' . round($n / 1e9, 1) . 'B';
        if ($n >= 1e6) return '$' . round($n / 1e6, 1) . 'M';
        return '$' . round($n / 1e3) . 'K';
    }

    public static function full(int $n): string
    {
        return '$' . number_format($n);
    }

    public static function dateFmt(string $s): string
    {
        return \Carbon\Carbon::parse($s)->format('M j, Y');
    }

    public static function metricLabel(string $rank, array $c): string
    {
        switch ($rank) {
            case 'heavy': return self::compact($c['renewal']);
            case 'easy':
                return $c['replaceable']
                    ? $c['ossCount'] . ' alternatives · ' . strtolower($c['effort']) . ' effort'
                    : 'Partial only';
            default: return self::daysLeft($c) . ' days';
        }
    }

    /**
     * Filter, rank, and return rows plus the toolbar/stat numbers needed by
     * the queue view. $filters: agency, window (days), replaceable (bool).
     */
    public static function queue(string $rank, array $filters): array
    {
        $all = self::contracts();

        $rows = array_values(array_filter($all, function ($c) use ($filters) {
            if (!empty($filters['agency']) && $c['agency'] !== $filters['agency']) return false;
            if (!empty($filters['replaceable']) && !$c['replaceable']) return false;
            if (!empty($filters['window']) && self::daysLeft($c) > (int) $filters['window']) return false;
            return true;
        }));

        usort($rows, function ($a, $b) use ($rank) {
            switch ($rank) {
                case 'heavy': return $b['renewal'] <=> $a['renewal'];
                case 'easy': return self::easeScore($b) <=> self::easeScore($a);
                default: return self::daysLeft($a) <=> self::daysLeft($b);
            }
        });

        $totalAtStake = array_sum(array_column($rows, 'renewal'));
        $replaceableValue = array_sum(array_map(fn($c) => $c['replaceable'] ? $c['renewal'] : 0, $rows));
        $soon = count(array_filter($rows, fn($c) => self::daysLeft($c) <= 90));

        $fastest = $all;
        usort($fastest, fn($a, $b) => self::daysLeft($a) <=> self::daysLeft($b));
        $fastest = $fastest[0];

        return [
            'rows' => $rows,
            'view' => self::VIEWS[$rank],
            'agencies' => collect($all)->pluck('agency')->unique()->sort()->values()->all(),
            'stats' => [
                'totalAtStake' => self::compact($totalAtStake),
                'contractCount' => count($rows),
                'replaceableValue' => self::compact($replaceableValue),
                'soon' => $soon,
                'fastestDays' => self::daysLeft($fastest),
                'fastestSub' => self::agencyName($fastest['agency']) . ' — ' . $fastest['vendor'],
            ],
        ];
    }

    public static function find(string $id): ?array
    {
        foreach (self::contracts() as $c) {
            if ($c['id'] === $id) return $c;
        }
        return null;
    }

    public static function hasStory(string $id): bool
    {
        return file_exists(resource_path("stories/renewals/{$id}.md"));
    }
}
