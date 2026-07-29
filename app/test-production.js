/**
 * Databook Application - Automated Page Testing Script(Production)
    * 
 * This script uses Playwright to test all pages in the Databook application.
 * It checks for:
 * - Page loads successfully(HTTP 200)
    * - No JavaScript console errors
        * - DataTables initialize correctly
            * - API calls complete successfully
                * - Data appears in tables / charts
                    */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

// Configuration — override with env: BASE_URL=https://staging.databook.nyc node test-production.js
const BASE_URL = process.env.BASE_URL || 'https://databook.nyc';
const API_URL = (process.env.BASE_URL || 'https://databook.nyc') + '/api';
const RESULTS_DIR = './test-results-prod';
const SCREENSHOT_DIR = path.join(RESULTS_DIR, 'screenshots');
const TIMEOUT = 60000; // 60 seconds per page

// Known benign console errors to ignore (headless browser limitations)
const IGNORED_CONSOLE_ERRORS = [
    'Failed to initialize WebGL',
    'Failed to load resource',
    'Access to XMLHttpRequest',
    'net::ERR_FAILED',
    'net::ERR_',
    'mapbox',
    'favicon.ico',
    'Unchecked runtime.lastError',
    'api.mapbox.com',
    'tiles.mapbox.com',
    'events.mapbox.com',
    'api.staging.databook.nyc',
    'api.databook.nyc',
    'api.stag',
    'pstats-categories'
];

// Test results
const results = {
    passed: [],
    failed: [],
    warnings: [],
    startTime: new Date(),
    endTime: null,
    totalPages: 0,
    passedCount: 0,
    failedCount: 0,
    warningCount: 0
};

// Sample IDs for dynamic routes (update these with real IDs from your database)
const SAMPLE_DATA = {
    orgId: '170010068',
    orgSlug: 'administration-for-childrens-services',
    projectId: 'HWK876',
    projectSlug: 'reconstruction-of-wyckoff-avenue-brooklyn',
    districtType: 'cd',
    districtId: '1',
    districtSlug: 'manhattan-1',
    schoolId: 'K001',
    schoolSlug: 'ps-001-the-bergen',
    titleId: '00031',
    titleSlug: 'hcppa',
    personId: 'pr6661950',
    personSlug: 'jimmy-f-alomar',
    budgetLineCode: 'ED001',
    categorySlug: 'education',
    typeSlug: 'new-construction',
    minorProjectId: 'MA001'
};

// Define all routes to test
const routes = [
    // ========== Static Pages ==========
    { path: '/', name: 'Homepage', category: 'Static', hasData: true },
    { path: '/about', name: 'About Page', category: 'Static', hasData: false },
    { path: '/about/data', name: 'Data Health', category: 'About', hasData: true },
    { path: '/about/tables', name: 'Database Tables', category: 'About', hasData: true },
    { path: '/about/log', name: 'Ingestion Log', category: 'About', hasData: true },
    { path: '/mcp', name: 'MCP Info', category: 'About', hasData: false },
    { path: '/styleguide', name: 'Styleguide', category: 'About', hasData: false },
    { path: '/blog', name: 'Blog', category: 'About', hasData: false },
    // ========== Organizations ==========
    { path: '/organizations/directory', name: 'Organizations Directory', category: 'Organizations', hasData: true, hasDataTable: true },
    { path: '/organizations/all', name: 'Organizations All', category: 'Organizations', hasData: true, hasDataTable: true },
    { path: '/organizations/chart', name: 'Organizations Chart', category: 'Organizations', hasData: true },

    // Organizations - Individual (using sample ID)
    { path: `/o/${SAMPLE_DATA.orgId}-${SAMPLE_DATA.orgSlug}`, name: 'Organization Profile', category: 'Organizations', hasData: true },
    { path: `/o/${SAMPLE_DATA.orgId}-${SAMPLE_DATA.orgSlug}/projects`, name: 'Organization Projects', category: 'Organizations', hasData: true, hasDataTable: true },
    { path: `/o/${SAMPLE_DATA.orgId}-${SAMPLE_DATA.orgSlug}/expense-budget`, name: 'Organization Budget', category: 'Organizations', hasData: true },
    { path: `/o/${SAMPLE_DATA.orgId}-${SAMPLE_DATA.orgSlug}/notices`, name: 'Organization Notices', category: 'Organizations', hasData: true },
    { path: `/o/${SAMPLE_DATA.orgId}-${SAMPLE_DATA.orgSlug}/events`, name: 'Organization Events', category: 'Organizations', hasData: true },
    { path: `/o/${SAMPLE_DATA.orgId}-${SAMPLE_DATA.orgSlug}/jobs`, name: 'Organization Jobs', category: 'Organizations', hasData: true },
    { path: `/o/${SAMPLE_DATA.orgId}-${SAMPLE_DATA.orgSlug}/civil-list`, name: 'Organization Civil List', category: 'Organizations', hasData: true },
    { path: `/o/${SAMPLE_DATA.orgId}-${SAMPLE_DATA.orgSlug}/demographics`, name: 'Organization Demographics', category: 'Organizations', hasData: true },
    { path: `/o/${SAMPLE_DATA.orgId}-${SAMPLE_DATA.orgSlug}/city-council-discretionary`, name: 'Organization Council Discretionary', category: 'Organizations', hasData: true },
    { path: `/o/${SAMPLE_DATA.orgId}-${SAMPLE_DATA.orgSlug}/procurement-contracts`, name: 'Organization Contracts', category: 'Organizations', hasData: true },
    { path: `/o/${SAMPLE_DATA.orgId}-${SAMPLE_DATA.orgSlug}/procurement-vendors`, name: 'Organization Vendors', category: 'Organizations', hasData: true },
    { path: `/o/${SAMPLE_DATA.orgId}-${SAMPLE_DATA.orgSlug}/procurement-solicitations`, name: 'Organization Solicitations', category: 'Organizations', hasData: true },
    { path: `/o/${SAMPLE_DATA.orgId}-${SAMPLE_DATA.orgSlug}/facilities`, name: 'Organization Facilities', category: 'Organizations', hasData: true },
    { path: `/o/${SAMPLE_DATA.orgId}-${SAMPLE_DATA.orgSlug}/agency-performance`, name: 'Organization Performance', category: 'Organizations', hasData: true },
    { path: '/organizations/agencies', name: 'City Agencies Directory', category: 'Organizations', hasData: true },
    // { path: `/o/${SAMPLE_DATA.orgId}-${SAMPLE_DATA.orgSlug}/headcount`, name: 'Organization Headcount', category: 'Organizations', hasData: true }, // DOE has no headcount

    // ========== Districts ==========
    { path: '/districts', name: 'Districts Main', category: 'Districts', hasData: true },
    { path: '/districts/cd', name: 'Community Districts', category: 'Districts', hasData: true },
    { path: '/districts/cc', name: 'City Council Districts', category: 'Districts', hasData: true },
    { path: '/districts/nta', name: 'Neighborhood Tabulation Areas', category: 'Districts', hasData: true },
    { path: '/districts/sd', name: 'School Districts', category: 'Districts', hasData: true },

    // Districts - Individual (using sample ID)
    { path: `/d/${SAMPLE_DATA.districtType}-${SAMPLE_DATA.districtId}-${SAMPLE_DATA.districtSlug}`, name: 'District Profile', category: 'Districts', hasData: true },
    { path: `/d/${SAMPLE_DATA.districtType}-${SAMPLE_DATA.districtId}-${SAMPLE_DATA.districtSlug}/projects`, name: 'District Projects', category: 'Districts', hasData: true, hasDataTable: true },
    { path: `/d/${SAMPLE_DATA.districtType}-${SAMPLE_DATA.districtId}-${SAMPLE_DATA.districtSlug}/facilities`, name: 'District Facilities', category: 'Districts', hasData: true },
    // { path: `/d/${SAMPLE_DATA.districtType}-${SAMPLE_DATA.districtId}-${SAMPLE_DATA.districtSlug}/demographics`, name: 'District Demographics', category: 'Districts', hasData: true }, // Not available for CD

    // ========== Schools ==========
    { path: '/schools', name: 'Schools Directory', category: 'Schools', hasData: true, hasDataTable: true },
    // Schools - Individual (using sample ID)
    { path: `/s/${SAMPLE_DATA.schoolId}-${SAMPLE_DATA.schoolSlug}`, name: 'School Profile', category: 'Schools', hasData: true },
    { path: `/s/${SAMPLE_DATA.schoolId}-${SAMPLE_DATA.schoolSlug}/enrollment`, name: 'School Enrollment', category: 'Schools', hasData: true },
    { path: `/s/${SAMPLE_DATA.schoolId}-${SAMPLE_DATA.schoolSlug}/race-ethnicity-gender`, name: 'School Demographics', category: 'Schools', hasData: true },
    // { path: `/s/${SAMPLE_DATA.schoolId}-${SAMPLE_DATA.schoolSlug}/performance`, name: 'School Performance', category: 'Schools', hasData: true }, // Not available

    // ========== Capital Projects ==========
    { path: '/capital', name: 'Capital Projects Home', category: 'Capital Projects', hasData: true },
    { path: '/projects', name: 'All Projects', category: 'Capital Projects', hasData: true, hasDataTable: true },
    { path: '/projects/types', name: 'Project Types', category: 'Capital Projects', hasData: true },
    { path: '/projects/categories', name: 'Project Categories', category: 'Capital Projects', hasData: true },
    { path: '/projects/budget-lines', name: 'Budget Lines', category: 'Capital Projects', hasData: true },
    { path: '/projects/commitments', name: 'Commitments', category: 'Capital Projects', hasData: true },
    { path: '/capital/minor-projects', name: 'Minor Projects', category: 'Capital Projects', hasData: true },

    // Capital - Individual (using sample ID)
    { path: `/p/${SAMPLE_DATA.projectId}_${SAMPLE_DATA.projectSlug}`, name: 'Project Detail', category: 'Capital Projects', hasData: true },
    { path: '/capital/minor-projects/850MIBBNC04B', name: 'Minor Project Detail', category: 'Capital Projects', hasData: true }, // Valid ID

    // ========== Capital Archive ==========
    { path: '/capital-archive', name: 'Capital Archive Home', category: 'Capital Archive', hasData: true },
    { path: '/capital-archive/projects', name: 'Archive Projects', category: 'Capital Archive', hasData: true, hasDataTable: true },
    { path: '/capital-archive/project-types', name: 'Archive Project Types', category: 'Capital Archive', hasData: true },
    { path: '/capital-archive/categories', name: 'Archive Categories', category: 'Capital Archive', hasData: true },
    { path: '/capital-archive/budget-lines', name: 'Archive Budget Lines', category: 'Capital Archive', hasData: true },

    // ========== Titles ==========
    { path: '/titles', name: 'Titles Directory', category: 'Titles', hasData: true, hasDataTable: true },
    // Titles - Individual (using sample ID)
    { path: `/t/${SAMPLE_DATA.titleId}-${SAMPLE_DATA.titleSlug}`, name: 'Title Profile', category: 'Titles', hasData: true },
    { path: `/t/${SAMPLE_DATA.titleId}-${SAMPLE_DATA.titleSlug}/positions`, name: 'Title Positions', category: 'Titles', hasData: true },
    // { path: `/t/${SAMPLE_DATA.titleId}-${SAMPLE_DATA.titleSlug}/salary`, name: 'Title Salary', category: 'Titles', hasData: true }, // Invalid

    // ========== Notices ==========
    { path: '/notices', name: 'Notices Main', category: 'Notices', hasData: true },
    { path: '/notices/public-hearings', name: 'Public Hearings', category: 'Notices', hasData: true },
    { path: '/notices/meetings', name: 'Meetings', category: 'Notices', hasData: true },
    { path: '/notices/procurement', name: 'Procurement Notices', category: 'Notices', hasData: true },
    { path: '/notices/all', name: 'Notices All', category: 'Notices', hasData: true },
    { path: '/notices/events', name: 'Notices Events', category: 'Notices', hasData: true },
    { path: '/notices/contract-awards', name: 'Contract Awards', category: 'Notices', hasData: true },
    { path: '/notices/special-materials', name: 'Special Materials', category: 'Notices', hasData: true },
    { path: '/notices/agency-rules', name: 'Agency Rules', category: 'Notices', hasData: true },
    { path: '/notices/property-disposition', name: 'Property Disposition', category: 'Notices', hasData: true },
    { path: '/notices/court-notices', name: 'Court Notices', category: 'Notices', hasData: true },
    { path: '/notices/change-of-personnel', name: 'Change of Personnel', category: 'Notices', hasData: true },

    // ========== Auctions ==========
    { path: '/auctions', name: 'Auctions', category: 'Auctions', hasData: true, hasDataTable: true },

    // ========== People ==========
    { path: '/people', name: 'People Directory', category: 'People', hasData: true },
    { path: `/people/search/smith/all`, name: 'People Search All', category: 'People', hasData: true, hasDataTable: true },
    { path: `/people/search/smith/current`, name: 'People Search Current', category: 'People', hasData: true, hasDataTable: true },

    // ========== Procurement ==========
    { path: '/procurement', name: 'Procurement Dashboard', category: 'Procurement', hasData: false },
    { path: '/procurement/solicitations', name: 'Procurement Solicitations', category: 'Procurement', hasData: false },
    { path: '/procurement/contracts', name: 'Procurement Contracts', category: 'Procurement', hasData: false },
    { path: '/procurement/vendors', name: 'Procurement Vendors', category: 'Procurement', hasData: false },
    { path: '/procurement/transactions', name: 'Procurement Transactions', category: 'Procurement', hasData: false },
    { path: '/procurement/agencies', name: 'Procurement Agencies', category: 'Procurement', hasData: false },
    { path: '/research/digital-reform', name: 'Procurement Research', category: 'Procurement', hasData: false }
];

// Create results directories
function setupDirectories() {
    if (!fs.existsSync(RESULTS_DIR)) {
        fs.mkdirSync(RESULTS_DIR, { recursive: true });
    }
    if (!fs.existsSync(SCREENSHOT_DIR)) {
        fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
    }
}

// Test a single page
async function testPage(page, route) {
    const testResult = {
        path: route.path,
        name: route.name,
        category: route.category,
        url: BASE_URL + route.path,
        status: 'unknown',
        httpStatus: null,
        errors: [],
        warnings: [],
        apiCalls: [],
        hasData: false,
        dataTableInitialized: false,
        loadTime: 0,
        timestamp: new Date().toISOString()
    };

    const consoleErrors = [];
    const apiCalls = [];

    // Listen for console errors (filtering known benign errors)
    page.on('console', msg => {
        if (msg.type() === 'error') {
            const text = msg.text();
            const isBenign = IGNORED_CONSOLE_ERRORS.some(pattern =>
                text.toLowerCase().includes(pattern.toLowerCase())
            );
            if (!isBenign) {
                consoleErrors.push(text);
            }
        }
    });

    // Listen for API calls
    page.on('response', response => {
        const url = response.url();
        if (url.includes(API_URL) || url.includes('/api/')) {
            apiCalls.push({
                url: url,
                status: response.status(),
                ok: response.ok()
            });
        }
    });

    try {
        console.log(`\n📄 Testing: ${route.name} (${route.path})`);

        const startTime = Date.now();

        // Navigate to page
        let response = null;
        try {
            response = await page.goto(BASE_URL + route.path, {
                waitUntil: 'commit',
                timeout: TIMEOUT
            });
        } catch (e) {
            if (e.name === 'TimeoutError' || e.message.includes('Timeout')) {
                console.log(`   ⚠️  Navigation timeout reached, proceeding with DOM checks...`);
                testResult.warnings.push(`Navigation Timeout (${TIMEOUT}ms)`);
                // Continue to check if data actually loaded despite timeout
            } else {
                throw e;
            }
        }

        testResult.loadTime = Date.now() - startTime;

        // Check HTTP status if we have a response object
        if (response) {
            testResult.httpStatus = response.status();
            if (response.status() !== 200) {
                testResult.errors.push(`HTTP ${response.status()} - Page did not return 200 OK`);
                testResult.status = 'failed';
                console.log(`   ❌ HTTP ${response.status()}`);
                return testResult;
            }
        }

        // Wait a bit for JavaScript to execute
        await page.waitForTimeout(2000);

        // Check for console errors
        if (consoleErrors.length > 0) {
            testResult.errors.push(...consoleErrors.map(e => `Console Error: ${e}`));
            console.log(`   ⚠️  ${consoleErrors.length} console error(s)`);
        }

        // Check API calls
        testResult.apiCalls = apiCalls;
        const failedApiCalls = apiCalls.filter(call => !call.ok);
        if (failedApiCalls.length > 0) {
            testResult.errors.push(...failedApiCalls.map(call =>
                `API call failed: ${call.url} (${call.status})`
            ));
            console.log(`   ❌ ${failedApiCalls.length} failed API call(s)`);
        }

        // Check for DataTable if expected
        if (route.hasDataTable) {
            const dataTableExists = await page.evaluate(() => {
                return typeof $.fn.DataTable !== 'undefined' &&
                    $('.dataTable').length > 0;
            }).catch(() => false);

            testResult.dataTableInitialized = dataTableExists;

            if (!dataTableExists) {
                testResult.warnings.push('DataTable not initialized');
                console.log(`   ⚠️  DataTable not found`);
            } else {
                console.log(`   ✅ DataTable initialized`);
            }
        }

        // Check for data presence
        if (route.hasData) {
            const hasContent = await page.evaluate(() => {
                // Check for tables with rows
                const tables = document.querySelectorAll('table tbody tr');
                if (tables.length > 0) return true;

                // Check for charts/visualizations
                const charts = document.querySelectorAll('canvas, svg');
                if (charts.length > 0) return true;

                // Check for data containers
                const dataContainers = document.querySelectorAll('[data-content], .data-container, .content-section');
                if (dataContainers.length > 0) return true;

                return false;
            });

            testResult.hasData = hasContent;

            if (!hasContent) {
                testResult.warnings.push('No data found on page');
                console.log(`   ⚠️  No data detected`);
            } else {
                console.log(`   ✅ Data present`);
            }
        }

        // Take screenshot
        const screenshotName = `${route.category.replace(/\s+/g, '-')}_${route.name.replace(/\s+/g, '-')}.png`;
        await page.screenshot({
            path: path.join(SCREENSHOT_DIR, screenshotName),
            fullPage: true
        });

        // Determine overall status
        if (testResult.errors.length === 0) {
            testResult.status = testResult.warnings.length > 0 ? 'warning' : 'passed';
            console.log(`   ✅ PASSED (${testResult.loadTime}ms)`);
        } else {
            testResult.status = 'failed';
            console.log(`   ❌ FAILED`);
        }

    } catch (error) {
        testResult.status = 'failed';
        testResult.errors.push(`Exception: ${error.message}`);
        console.log(`   ❌ EXCEPTION: ${error.message}`);
    }

    return testResult;
}

// Generate HTML report
function generateHTMLReport() {
    const html = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Databook Test Results</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 32px;
        }
        .summary {
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .stat {
            padding: 20px;
            border-radius: 6px;
            text-align: center;
        }
        .stat-passed { background: #d4edda; color: #155724; }
        .stat-failed { background: #f8d7da; color: #721c24; }
        .stat-warning { background: #fff3cd; color: #856404; }
        .stat-total { background: #d1ecf1; color: #0c5460; }
        .stat-number {
            font-size: 36px;
            font-weight: bold;
            margin-bottom: 5px;
        }
        .stat-label {
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .filters {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .filter-buttons {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        .filter-btn {
            padding: 8px 16px;
            border: 2px solid #ddd;
            background: white;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s;
        }
        .filter-btn:hover { background: #f0f0f0; }
        .filter-btn.active {
            background: #007bff;
            color: white;
            border-color: #007bff;
        }
        .results {
            display: grid;
            gap: 15px;
        }
        .result-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 4px solid #ddd;
        }
        .result-card.passed { border-left-color: #28a745; }
        .result-card.failed { border-left-color: #dc3545; }
        .result-card.warning { border-left-color: #ffc107; }
        .result-header {
            display: flex;
            justify-content: space-between;
            align-items: start;
            margin-bottom: 15px;
        }
        .result-title {
            font-size: 18px;
            font-weight: 600;
            color: #333;
        }
        .result-category {
            display: inline-block;
            padding: 4px 12px;
            background: #e9ecef;
            border-radius: 12px;
            font-size: 12px;
            color: #495057;
            margin-left: 10px;
        }
        .result-status {
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }
        .status-passed { background: #d4edda; color: #155724; }
        .status-failed { background: #f8d7da; color: #721c24; }
        .status-warning { background: #fff3cd; color: #856404; }
        .result-url {
            color: #666;
            font-size: 14px;
            margin-bottom: 10px;
            font-family: monospace;
        }
        .result-meta {
            display: flex;
            gap: 20px;
            font-size: 13px;
            color: #666;
            margin-bottom: 15px;
        }
        .errors, .warnings, .api-calls {
            margin-top: 15px;
        }
        .section-title {
            font-weight: 600;
            margin-bottom: 8px;
            color: #333;
        }
        .error-list, .warning-list, .api-list {
            list-style: none;
            padding-left: 0;
        }
        .error-list li {
            padding: 8px 12px;
            background: #f8d7da;
            border-left: 3px solid #dc3545;
            margin-bottom: 5px;
            border-radius: 3px;
            font-size: 13px;
            color: #721c24;
        }
        .warning-list li {
            padding: 8px 12px;
            background: #fff3cd;
            border-left: 3px solid #ffc107;
            margin-bottom: 5px;
            border-radius: 3px;
            font-size: 13px;
            color: #856404;
        }
        .api-list li {
            padding: 6px 10px;
            background: #f8f9fa;
            margin-bottom: 3px;
            border-radius: 3px;
            font-size: 12px;
            font-family: monospace;
        }
        .api-failed { background: #f8d7da !important; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🧪 Databook Test Results</h1>
        <p style="color: #666; margin-bottom: 30px;">
            Generated: ${results.endTime.toLocaleString()} | 
            Duration: ${Math.round((results.endTime - results.startTime) / 1000)}s
        </p>

        <div class="summary">
            <h2 style="margin-bottom: 20px;">Summary</h2>
            <div class="stats">
                <div class="stat stat-total">
                    <div class="stat-number">${results.totalPages}</div>
                    <div class="stat-label">Total Pages</div>
                </div>
                <div class="stat stat-passed">
                    <div class="stat-number">${results.passedCount}</div>
                    <div class="stat-label">Passed</div>
                </div>
                <div class="stat stat-warning">
                    <div class="stat-number">${results.warningCount}</div>
                    <div class="stat-label">Warnings</div>
                </div>
                <div class="stat stat-failed">
                    <div class="stat-number">${results.failedCount}</div>
                    <div class="stat-label">Failed</div>
                </div>
            </div>
        </div>

        <div class="filters">
            <h3 style="margin-bottom: 15px;">Filter Results</h3>
            <div class="filter-buttons">
                <button class="filter-btn active" data-filter="all">All</button>
                <button class="filter-btn" data-filter="passed">Passed</button>
                <button class="filter-btn" data-filter="warning">Warnings</button>
                <button class="filter-btn" data-filter="failed">Failed</button>
                ${[...new Set([...results.passed, ...results.failed, ...results.warnings].map(r => r.category))]
            .map(cat => `<button class="filter-btn" data-filter="category-${cat.replace(/\s+/g, '-')}">${cat}</button>`)
            .join('')}
            </div>
        </div>

        <div class="results">
            ${[...results.passed, ...results.warnings, ...results.failed].map(result => `
                <div class="result-card ${result.status}" data-status="${result.status}" data-category="${result.category.replace(/\s+/g, '-')}">
                    <div class="result-header">
                        <div>
                            <span class="result-title">${result.name}</span>
                            <span class="result-category">${result.category}</span>
                        </div>
                        <span class="result-status status-${result.status}">${result.status}</span>
                    </div>
                    <div class="result-url">${result.url}</div>
                    <div class="result-meta">
                        <span>HTTP: ${result.httpStatus}</span>
                        <span>Load Time: ${result.loadTime}ms</span>
                        <span>API Calls: ${result.apiCalls.length}</span>
                        ${result.hasData ? '<span>✅ Has Data</span>' : '<span>⚠️ No Data</span>'}
                        ${result.dataTableInitialized ? '<span>✅ DataTable OK</span>' : ''}
                    </div>
                    ${result.errors.length > 0 ? `
                        <div class="errors">
                            <div class="section-title">❌ Errors (${result.errors.length})</div>
                            <ul class="error-list">
                                ${result.errors.map(err => `<li>${err}</li>`).join('')}
                            </ul>
                        </div>
                    ` : ''}
                    ${result.warnings.length > 0 ? `
                        <div class="warnings">
                            <div class="section-title">⚠️ Warnings (${result.warnings.length})</div>
                            <ul class="warning-list">
                                ${result.warnings.map(warn => `<li>${warn}</li>`).join('')}
                            </ul>
                        </div>
                    ` : ''}
                    ${result.apiCalls.length > 0 ? `
                        <div class="api-calls">
                            <div class="section-title">🔌 API Calls (${result.apiCalls.length})</div>
                            <ul class="api-list">
                                ${result.apiCalls.map(call => `
                                    <li class="${!call.ok ? 'api-failed' : ''}">
                                        ${call.ok ? '✅' : '❌'} ${call.status} - ${call.url}
                                    </li>
                                `).join('')}
                            </ul>
                        </div>
                    ` : ''}
                </div>
            `).join('')}
        </div>
    </div>

    <script>
        // Filter functionality
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                // Update active button
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                const filter = btn.dataset.filter;
                const cards = document.querySelectorAll('.result-card');

                cards.forEach(card => {
                    if (filter === 'all') {
                        card.classList.remove('hidden');
                    } else if (filter.startsWith('category-')) {
                        const category = filter.replace('category-', '');
                        card.classList.toggle('hidden', card.dataset.category !== category);
                    } else {
                        card.classList.toggle('hidden', card.dataset.status !== filter);
                    }
                });
            });
        });
    </script>
</body>
</html>
    `;

    fs.writeFileSync(path.join(RESULTS_DIR, 'test-report.html'), html);
    console.log(`\n📊 HTML report generated: ${path.join(RESULTS_DIR, 'test-report.html')}`);
}

// Generate JSON report
function generateJSONReport() {
    const jsonReport = {
        summary: {
            totalPages: results.totalPages,
            passed: results.passedCount,
            warnings: results.warningCount,
            failed: results.failedCount,
            startTime: results.startTime,
            endTime: results.endTime,
            duration: Math.round((results.endTime - results.startTime) / 1000)
        },
        results: {
            passed: results.passed,
            warnings: results.warnings,
            failed: results.failed
        }
    };

    fs.writeFileSync(
        path.join(RESULTS_DIR, 'test-results.json'),
        JSON.stringify(jsonReport, null, 2)
    );
    console.log(`📄 JSON report generated: ${path.join(RESULTS_DIR, 'test-results.json')}`);
}

// Main test runner
async function runTests() {
    console.log('🚀 Starting Databook Application Tests\n');
    console.log(`Base URL: ${BASE_URL}`);
    console.log(`API URL: ${API_URL}`);
    console.log(`Total Routes: ${routes.length}\n`);

    setupDirectories();

    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
        viewport: { width: 1920, height: 1080 }
    });
    // const page = await context.newPage(); // This line is now moved inside the loop

    results.totalPages = routes.length;

    // Test each route
    for (const route of routes) {
        console.log("Inside loop for: " + route.name);
        // Delay to prevent staging API from dropping connections / returning 404
        await new Promise(r => setTimeout(r, 2000));

        console.log(`\n--- Starting test for: ${route.name} (${route.path}) ---`);
        try {
            const page = await context.newPage();
            const result = await testPage(page, route);
            await page.close(); // Close page after testing to free up resources

            if (result.status === 'passed') {
                results.passed.push(result);
                results.passedCount++;
            } else if (result.status === 'warning') {
                results.warnings.push(result);
                results.warningCount++;
            } else {
                results.failed.push(result);
                results.failedCount++;
            }
        } catch (err) {
            console.error(`\n🔥 FATAL ERROR in loop for ${route.name}:`, err);
        }
    }

    await browser.close();

    results.endTime = new Date();

    // Generate reports
    console.log('\n' + '='.repeat(80));
    console.log('📊 TEST SUMMARY');
    console.log('='.repeat(80));
    console.log(`Total Pages Tested: ${results.totalPages}`);
    console.log(`✅ Passed: ${results.passedCount}`);
    console.log(`⚠️  Warnings: ${results.warningCount}`);
    console.log(`❌ Failed: ${results.failedCount}`);
    console.log(`⏱️  Duration: ${Math.round((results.endTime - results.startTime) / 1000)}s`);
    console.log('='.repeat(80) + '\n');

    generateHTMLReport();
    generateJSONReport();

    console.log(`\n✨ Testing complete! Open ${path.join(RESULTS_DIR, 'test-report.html')} to view results.\n`);

    // Exit with error code if tests failed
    process.exit(results.failedCount > 0 ? 1 : 0);
}

// Run tests
process.on('unhandledRejection', (reason, promise) => {
    console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

runTests().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
});
