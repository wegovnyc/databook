{{-- On-page NYCHA sub-navigation. Lives on the NYCHA pages themselves (not the
     global Procurement submenu, which stays intact) so the four NYCHA domains
     are navigable as their own area. Include just inside a page's content. --}}
<x-db.tabs :scroll="true" class="mb-4">
    <x-db.tab :href="route('procurement.nycha')"           :active="Request::is('procurement/nycha') && !Request::is('procurement/nycha/*')">Overview</x-db.tab>
    <x-db.tab :href="route('procurement.nycha.budget')"    :active="Request::is('procurement/nycha/budget*')">Budget</x-db.tab>
    <x-db.tab :href="route('procurement.nycha.revenue')"   :active="Request::is('procurement/nycha/revenue*')">Revenue</x-db.tab>
    <x-db.tab :href="route('procurement.nycha.contracts')" :active="Request::is('procurement/nycha/contracts*')">Contracts</x-db.tab>
    <x-db.tab :href="route('procurement.nycha.spending')"  :active="Request::is('procurement/nycha/spending*')">Spending</x-db.tab>
</x-db.tabs>
