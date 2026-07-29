{{-- NYCHA vendor cell. Crosswalked → City vendor profile; otherwise → the
     NYCHA-native vendor profile (org-profile section, keyed by name). Both are
     real drill-downs. stopPropagation keeps the row's expand toggle from firing
     on the link. Expects $r (with vendor + optional vendor_id), $id (+ $org/
     $orgslug for the slug). --}}
@php $vname = trim($r['vendor'] ?? ''); $vslug = $orgslug ?? \Illuminate\Support\Str::slug($org['name'] ?? '', '-'); @endphp
@if($vname === '')
—
@elseif(!empty($r['vendor_id']))
<a href="{{ route('procurement.vendor', ['id' => $r['vendor_id']]) }}" onclick="event.stopPropagation()" title="City vendor profile (PASSPort)">{{ $vname }}</a>
@else
<a href="{{ route('orgSection', ['id' => $id, 'orgslug' => $vslug, 'section' => 'procurement-nycha-vendor']) }}?name={{ urlencode($vname) }}" onclick="event.stopPropagation()" title="NYCHA vendor profile">{{ $vname }}</a>
@endif
