@extends('layout')

@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        <div class="db-eyebrow">Procurement</div>
        <h1>About the Data</h1>
        <p class="db-page-lead">
            This section was produced by <a href="https://wegov.nyc" target="_blank" rel="noopener">WeGov.NYC</a>, a nonprofit initiative
            of <a href="https://sarapis.org" target="_blank" rel="noopener">Sarapis</a>. You can learn more about the data below.
            If you have questions, comments, ideas, etc please email
            <a href="mailto:info@wegov.nyc">info@wegov.nyc</a>.
        </p>

        <h3 class="mb-2 mt-4">Datasets</h3>
        <p class="text-muted mb-3">The following datasets are used to power the NYC Contract Explorer.</p>

        <div class="db-table-wrap mb-5">
            <div class="table-responsive">
            <table class="db-table">
                <thead>
                    <tr>
                        <th>Dataset</th>
                        <th>Source</th>
                        <th>Processed Output</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td class="fw-bold">PASSPort Vendors</td>
                        <td><a href="https://a0333-passportpublic.nyc.gov/vendor.html" target="_blank" rel="noopener">PASSPort Public Data <i class="bi bi-box-arrow-up-right"></i></a></td>
                        <td><a href="https://databook2.s3.amazonaws.com/pre-processed/vendor_data.csv" target="_blank">vendor_data.csv</a></td>
                    </tr>
                    <tr>
                        <td class="fw-bold">PASSPort Contracts</td>
                        <td><a href="https://a0333-passportpublic.nyc.gov/contracts.html" target="_blank" rel="noopener">PASSPort Public Data <i class="bi bi-box-arrow-up-right"></i></a></td>
                        <td><a href="https://databook2.s3.amazonaws.com/pre-processed/contracts_data.csv" target="_blank">contracts_data.csv</a></td>
                    </tr>
                    <tr>
                        <td class="fw-bold">PASSPort Solicitations</td>
                        <td><a href="https://a0333-passportpublic.nyc.gov/rfx.html" target="_blank" rel="noopener">PASSPort Public Data <i class="bi bi-box-arrow-up-right"></i></a></td>
                        <td><a href="https://databook2.s3.amazonaws.com/pre-processed/solicitations_data.csv" target="_blank">solicitations_data.csv</a></td>
                    </tr>
                    <tr>
                        <td class="fw-bold">Doing Business Entities</td>
                        <td><a href="https://data.cityofnewyork.us/City-Government/Doing-Business-Search-Entities/72mk-a8z7/about_data" target="_blank" rel="noopener">NYC Open Data <i class="bi bi-box-arrow-up-right"></i></a></td>
                        <td><a href="https://databook2.s3.amazonaws.com/pre-processed/doing_business_entities.csv" target="_blank">doing_business_entities.csv</a></td>
                    </tr>
                    <tr>
                        <td class="fw-bold">Doing Business People</td>
                        <td><a href="https://data.cityofnewyork.us/City-Government/Doing-Business-Search-People/2sps-j9st/about_data" target="_blank" rel="noopener">NYC Open Data <i class="bi bi-box-arrow-up-right"></i></a></td>
                        <td><a href="https://databook2.s3.amazonaws.com/pre-processed/doing_business_people.csv" target="_blank">doing_business_people.csv</a></td>
                    </tr>
                    <tr>
                        <td class="fw-bold">MOCS Entity Summary</td>
                        <td><a href="https://www.nyc.gov/site/mocs/passport/passport-reports.page" target="_blank" rel="noopener">MOCS Reports <i class="bi bi-box-arrow-up-right"></i></a></td>
                        <td><a href="https://databook2.s3.amazonaws.com/pre-processed/passport_entity_summary.csv" target="_blank">passport_entity_summary.csv</a></td>
                    </tr>
                    <tr>
                        <td class="fw-bold">MOCS Other Names</td>
                        <td><a href="https://www.nyc.gov/site/mocs/passport/passport-reports.page" target="_blank" rel="noopener">MOCS Reports <i class="bi bi-box-arrow-up-right"></i></a></td>
                        <td><a href="https://databook2.s3.amazonaws.com/pre-processed/passport_other_names.csv" target="_blank">passport_other_names.csv</a></td>
                    </tr>
                    <tr>
                        <td class="fw-bold">MOCS Performance Evaluations</td>
                        <td><a href="https://www.nyc.gov/site/mocs/passport/passport-reports.page" target="_blank" rel="noopener">MOCS Reports <i class="bi bi-box-arrow-up-right"></i></a></td>
                        <td><a href="https://databook2.s3.amazonaws.com/pre-processed/passport_performance_evaluation.csv" target="_blank">passport_performance_evaluation.csv</a></td>
                    </tr>
                    <tr>
                        <td class="fw-bold">MOCS Principals</td>
                        <td><a href="https://www.nyc.gov/site/mocs/passport/passport-reports.page" target="_blank" rel="noopener">MOCS Reports <i class="bi bi-box-arrow-up-right"></i></a></td>
                        <td><a href="https://databook2.s3.amazonaws.com/pre-processed/passport_principals.csv" target="_blank">passport_principals.csv</a></td>
                    </tr>
                    <tr>
                        <td class="fw-bold">MOCS Related Entities</td>
                        <td><a href="https://www.nyc.gov/site/mocs/passport/passport-reports.page" target="_blank" rel="noopener">MOCS Reports <i class="bi bi-box-arrow-up-right"></i></a></td>
                        <td><a href="https://databook2.s3.amazonaws.com/pre-processed/passport_related_entities.csv" target="_blank">passport_related_entities.csv</a></td>
                    </tr>
                    <tr>
                        <td class="fw-bold">OpenCorporates Matches</td>
                        <td><a href="https://opencorporates.com/" target="_blank" rel="noopener">OpenCorporates <i class="bi bi-box-arrow-up-right"></i></a></td>
                        <td><a href="https://databook2.s3.amazonaws.com/pre-processed/opencorporates_matches.csv" target="_blank">opencorporates_matches.csv</a></td>
                    </tr>
                    <tr>
                        <td class="fw-bold">Checkbook NYC Spending</td>
                        <td><a href="https://www.checkbooknyc.com/api" target="_blank" rel="noopener">Checkbook NYC API <i class="bi bi-box-arrow-up-right"></i></a></td>
                        <td><code>s3://nyc-databook-spending</code> (Parquet)</td>
                    </tr>
                    <tr>
                        <td class="fw-bold">Checkbook NYC Contracts</td>
                        <td><a href="https://www.checkbooknyc.com/api" target="_blank" rel="noopener">Checkbook NYC API <i class="bi bi-box-arrow-up-right"></i></a></td>
                        <td><code>s3://nyc-databook-spending/contracts</code></td>
                    </tr>
                </tbody>
            </table>
            </div>
        </div>

    </div>
</div>
@endsection
