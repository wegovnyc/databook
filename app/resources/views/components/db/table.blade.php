{{-- <x-db.table id="myTable"> <thead>…</thead><tbody>…</tbody> </x-db.table>
     Passes through id/dom hooks so DataTables keeps working. --}}
<table {{ $attributes->merge(['class' => 'db-table']) }}>{{ $slot }}</table>
