#!/usr/bin/env python3
"""
Databook API Health Check Script

Tests:
1. Public endpoints return 200 without authentication
2. CORS headers are present for browser access
3. Responses contain expected data structure
4. Common regression issues are caught

Run: python test_api_health.py [local|prod]
"""

import requests
import sys
import json
from typing import Dict, List, Tuple

# Configuration
ENVIRONMENTS = {
    'local': 'http://localhost:8000',
    'staging': 'https://api.staging.databook.nyc',
    'prod': 'https://api.databook.nyc',
}

# Test origin for CORS checks
TEST_ORIGIN = 'https://databook.nyc'

# Public endpoints that should NOT require authentication
# These are confirmed working without auth in production
PUBLIC_ENDPOINTS = [
    # Organizations (confirmed public Jan 30)
    ('/get/orgs/directory', 'rows'),
    ('/get/orgs/all', 'rows'),
    ('/get/orgs/profile/170010040', 'rows'),

    # Capital Projects (confirmed public Jan 30)
    ('/get/capitalprojects/projectsnew', 'rows'),
    ('/get/capitalprojects/core/HBX1086', 'rows'),  # Fixed Jan 30

    # Capital Strategy (fixed Feb 20)
    ('/get/capitalprojects/stratcategory/new-jail-facilities', 'rows'),
    ('/get/pstats-categories_by_type/department-of-correction', 'rows'),

    # Notices (Fixed Jan 30)
    ('/get/notices/frontnews', 'rows'),
    ('/get/notices/frontevents', 'rows'),

    # Titles (auth removed Feb 20)
    ('/get/titles', 'rows'),

    # Schools (public)
    ('/get/schools/section/M015/scaenrollmentcapacity', 'rows'),
    ('/get/schools/section/01M015/attendance', 'rows'),

    # OCE/Procurement (confirmed public Jan 30)
    ('/oce/dashboard/stats', None),  # Returns object, not rows

    # Pipeline Health (added Feb 2026)
    ('/pipeline/health', None),  # Returns {summary, datasets}

    # Health check
    ('/health', None),
]

# No known endpoints requiring auth that should be public
AUTH_REQUIRED_BUT_SHOULD_BE_PUBLIC = []

# Endpoints that must have CORS headers for browser access
CORS_CRITICAL_ENDPOINTS = [
    '/get/orgs/directory',
    '/get/capitalprojects/projectsnew',
    '/oce/dashboard/stats',
    '/health',
]

class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures: List[str] = []
    
    def record_pass(self, test_name: str):
        self.passed += 1
        print(f"  ✅ {test_name}")
    
    def record_fail(self, test_name: str, reason: str):
        self.failed += 1
        self.failures.append(f"{test_name}: {reason}")
        print(f"  ❌ {test_name}: {reason}")

def test_public_endpoints(base_url: str, results: TestResult):
    """Test that public endpoints return 200 without auth"""
    print("\n📋 Testing Public Endpoints (no auth required)...")
    
    for endpoint, rows_key in PUBLIC_ENDPOINTS:
        url = base_url + endpoint
        try:
            # OCE dashboard stats fetches S3 Parquet files; needs 60s
            timeout = 60 if '/oce/' in endpoint else 10
            response = requests.get(url, timeout=timeout)
            
            if response.status_code == 200:
                # Check if response has data
                if rows_key:
                    data = response.json()
                    rows = data.get(rows_key, [])
                    if len(rows) > 0:
                        results.record_pass(f"{endpoint} (200 OK, {len(rows)} rows)")
                    else:
                        results.record_fail(endpoint, "Empty response - no rows returned")
                else:
                    results.record_pass(f"{endpoint} (200 OK)")
            elif response.status_code == 401:
                results.record_fail(endpoint, "401 Unauthorized - endpoint requires auth but should be public")
            elif response.status_code == 404:
                results.record_fail(endpoint, "404 Not Found - endpoint missing")
            else:
                results.record_fail(endpoint, f"HTTP {response.status_code}")
                
        except requests.exceptions.Timeout:
            results.record_fail(endpoint, "Timeout")
        except requests.exceptions.ConnectionError:
            results.record_fail(endpoint, "Connection refused - is the API running?")
        except Exception as e:
            results.record_fail(endpoint, str(e))

def test_cors_headers(base_url: str, results: TestResult):
    """Test that CORS headers are present for browser access"""
    print("\n🌐 Testing CORS Headers...")
    
    for endpoint in CORS_CRITICAL_ENDPOINTS:
        url = base_url + endpoint
        try:
            response = requests.options(url, headers={
                'Origin': TEST_ORIGIN,
                'Access-Control-Request-Method': 'GET'
            }, timeout=10)
            
            # Also check GET response headers
            get_response = requests.get(url, headers={
                'Origin': TEST_ORIGIN
            }, timeout=60)
            
            cors_header = get_response.headers.get('access-control-allow-origin', '')
            
            if TEST_ORIGIN in cors_header or cors_header == '*':
                results.record_pass(f"{endpoint} (CORS: {cors_header})")
            elif cors_header:
                results.record_fail(endpoint, f"CORS header present but wrong origin: {cors_header}")
            else:
                results.record_fail(endpoint, "Missing Access-Control-Allow-Origin header - browser requests will fail")
                
        except Exception as e:
            results.record_fail(endpoint, str(e))

def test_api_response_structure(base_url: str, results: TestResult):
    """Test that API responses have expected structure"""
    print("\n📊 Testing Response Structure...")

    # Test OCE stats structure
    url = base_url + '/oce/dashboard/stats'
    try:
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            data = response.json()
            expected_keys = ['contracts', 'vendors', 'solicitations']
            missing = [k for k in expected_keys if k not in data]
            if not missing:
                results.record_pass(f"OCE stats has all keys: {list(data.keys())}")
            else:
                results.record_fail("OCE stats structure", f"Missing keys: {missing}")
        else:
            results.record_fail("OCE stats structure", f"HTTP {response.status_code}")
    except Exception as e:
        results.record_fail("OCE stats structure", str(e))

    # Test org directory structure
    url = base_url + '/get/orgs/directory'
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'rows' in data and len(data['rows']) > 0:
                first_row = data['rows'][0]
                expected_fields = ['id', 'name']
                has_fields = all(f in first_row for f in expected_fields)
                if has_fields:
                    results.record_pass(f"Org directory has expected fields")
                else:
                    results.record_fail("Org directory structure",
                                        f"Missing expected fields in row")
            else:
                results.record_fail("Org directory structure",
                                    "No rows returned")
    except Exception as e:
        results.record_fail("Org directory structure", str(e))

    # Test pipeline health structure
    url = base_url + '/pipeline/health'
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if 'summary' in data and 'datasets' in data:
                summary = data['summary']
                expected = ['total_datasets', 'fresh', 'aging', 'stale']
                missing = [k for k in expected if k not in summary]
                if not missing:
                    ds_count = summary['total_datasets']
                    fresh = summary['fresh']
                    results.record_pass(
                        f"Pipeline health: {ds_count} datasets, "
                        f"{fresh} fresh")
                else:
                    results.record_fail("Pipeline health structure",
                                        f"Missing summary keys: {missing}")
                # Check datasets have required fields
                datasets = data['datasets']
                if datasets:
                    ds = datasets[0]
                    req = ['table_name', 'freshness', 'freshness_label',
                           'sections', 'source_updated_label']
                    ds_missing = [k for k in req if k not in ds]
                    if not ds_missing:
                        results.record_pass(
                            f"Pipeline datasets have all fields "
                            f"({len(datasets)} datasets)")
                    else:
                        results.record_fail(
                            "Pipeline dataset fields",
                            f"Missing: {ds_missing}")
            else:
                results.record_fail("Pipeline health structure",
                                    "Missing summary or datasets key")
        else:
            results.record_fail("Pipeline health",
                                f"HTTP {response.status_code}")
    except Exception as e:
        results.record_fail("Pipeline health", str(e))

    # Test CROL data exists and is fresh
    url = base_url + '/pipeline/health'
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            crol = [d for d in data['datasets']
                    if d['table_name'] == 'crol']
            if crol:
                c = crol[0]
                rows = c.get('actual_row_count') or 0
                fresh = c.get('freshness', '')
                label = c.get('freshness_label', '')
                if rows > 1_000_000:
                    results.record_pass(
                        f"CROL: {rows:,} rows, {label}")
                else:
                    results.record_fail(
                        "CROL row count",
                        f"Expected >1M, got {rows:,}")
            else:
                results.record_fail("CROL dataset", "Not found in registry")
    except Exception as e:
        results.record_fail("CROL check", str(e))

    # Test capital project-types response structure
    url = base_url + '/get/pstats-categories_by_type/department-of-correction'
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            rows = data.get('rows', [])
            if rows:
                r = rows[0]
                required = ['prjtypename', 'category', 'total']
                missing = [k for k in required if k not in r]
                if not missing:
                    results.record_pass(
                        f"Project type has fields: {list(r.keys())}")
                else:
                    results.record_fail(
                        "Project type structure",
                        f"Missing: {missing}")
            else:
                results.record_fail("Project type", "No rows returned")
    except Exception as e:
        results.record_fail("Project type structure", str(e))

def main():
    env = sys.argv[1] if len(sys.argv) > 1 else 'prod'
    
    if env not in ENVIRONMENTS:
        print(f"Usage: python test_api_health.py [local|prod]")
        print(f"  Default: prod")
        sys.exit(1)
    
    base_url = ENVIRONMENTS[env]
    print(f"🔍 Databook API Health Check")
    print(f"   Environment: {env}")
    print(f"   Base URL: {base_url}")
    print("=" * 60)
    
    results = TestResult()
    
    # Run tests
    test_public_endpoints(base_url, results)
    test_cors_headers(base_url, results)
    test_api_response_structure(base_url, results)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"✅ Passed: {results.passed}")
    print(f"❌ Failed: {results.failed}")
    
    if results.failures:
        print("\n❌ Failures:")
        for failure in results.failures:
            print(f"   - {failure}")
    
    # Exit code
    if results.failed > 0:
        print("\n⚠️  Some tests failed. Review and fix before deploying.")
        sys.exit(1)
    else:
        print("\n✅ All tests passed!")
        sys.exit(0)

if __name__ == '__main__':
    main()
