#!/usr/bin/env python3
"""
Newsletter Link Validator

Tests all links in the generated newsletter and produces an HTML report.
"""

import asyncio
import aiohttp
import re
from datetime import datetime
from collections import defaultdict
from typing import Optional
from bs4 import BeautifulSoup


async def test_link(session: aiohttp.ClientSession, url: str, timeout: int = 10) -> dict:
    """Test a single URL and return status."""
    try:
        async with session.head(url, timeout=aiohttp.ClientTimeout(total=timeout), allow_redirects=True) as resp:
            return {
                "url": url,
                "status": resp.status,
                "ok": resp.status < 400,
                "error": None
            }
    except aiohttp.ClientError as e:
        # Try GET if HEAD fails (some servers don't support HEAD)
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout), allow_redirects=True) as resp:
                return {
                    "url": url,
                    "status": resp.status,
                    "ok": resp.status < 400,
                    "error": None
                }
        except Exception as e2:
            return {
                "url": url,
                "status": 0,
                "ok": False,
                "error": str(e2)
            }
    except Exception as e:
        return {
            "url": url,
            "status": 0,
            "ok": False,
            "error": str(e)
        }


def extract_links_from_html(html: str) -> list:
    """Extract all links from HTML content."""
    soup = BeautifulSoup(html, 'html.parser')
    links = []
    
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True)[:50]
        
        # Skip mailto and javascript links
        if href.startswith(('mailto:', 'javascript:', '#')):
            continue
            
        links.append({
            "url": href,
            "text": text,
            "section": _get_section_name(a)
        })
    
    return links


def _get_section_name(element) -> str:
    """Find the section name for a link by traversing up the DOM."""
    parent = element.find_parent('div', class_='section')
    if parent:
        header = parent.find('span', class_='section-title')
        if header:
            return header.get_text(strip=True)
    return "Header/Footer"


def categorize_links(links: list) -> dict:
    """Categorize links by domain/type."""
    categories = defaultdict(list)
    
    for link in links:
        url = link["url"]
        
        if "databook.nyc/o/" in url:
            categories["organization"].append(link)
        elif "databook.nyc/procurement/contract/" in url:
            categories["contract"].append(link)
        elif "databook.nyc/procurement/vendor/" in url:
            categories["vendor"].append(link)
        elif "databook.nyc" in url:
            categories["databook_other"].append(link)
        elif "cityrecord.nyc.gov" in url:
            categories["city_record"].append(link)
        elif "passport.cityofnewyork" in url:
            categories["passport"].append(link)
        elif "checkbooknyc" in url:
            categories["checkbook"].append(link)
        else:
            categories["external"].append(link)
    
    return dict(categories)


async def test_all_links(links: list, concurrency: int = 5) -> list:
    """Test all links with controlled concurrency."""
    connector = aiohttp.TCPConnector(limit=concurrency)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        # Deduplicate URLs
        unique_urls = list(set(link["url"] for link in links))
        
        tasks = [test_link(session, url) for url in unique_urls]
        results = await asyncio.gather(*tasks)
        
        # Map results back to links
        url_status = {r["url"]: r for r in results}
        
        for link in links:
            status = url_status.get(link["url"], {})
            link["status"] = status.get("status", 0)
            link["ok"] = status.get("ok", False)
            link["error"] = status.get("error")
        
        return links


def generate_report_html(links: list, categories: dict) -> str:
    """Generate an HTML report matching the example format."""
    
    # Calculate stats
    total = len(links)
    ok_count = sum(1 for l in links if l.get("ok"))
    failed_count = total - ok_count
    
    org_links = len(categories.get("organization", []))
    contract_links = len(categories.get("contract", []))
    external_links = sum(len(v) for k, v in categories.items() 
                        if k not in ["organization", "contract", "vendor", "databook_other"])
    
    # Group by status
    ok_links = [l for l in links if l.get("ok")]
    failed_links = [l for l in links if not l.get("ok")]
    
    now = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    
    # Determine header style based on results
    if failed_count == 0:
        header_style = "background: linear-gradient(135deg, #28a745 0%, #1e7e34 100%);"
        header_icon = "✅"
    elif failed_count < 5:
        header_style = "background: linear-gradient(135deg, #FF6319 0%, #d44e0c 100%);"
        header_icon = "⚠️"
    else:
        header_style = "background: linear-gradient(135deg, #dc3545 0%, #a71d2a 100%);"
        header_icon = "❌"
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Newsletter Link Test Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            padding: 40px 20px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            {header_style}
            color: white;
            padding: 32px;
        }}
        h1 {{ font-size: 28px; margin-bottom: 8px; }}
        .subtitle {{ opacity: 0.9; font-size: 14px; }}
        .content {{ padding: 32px; }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 32px;
        }}
        .summary-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .summary-card.success {{ border-left: 4px solid #28a745; }}
        .summary-card.info {{ border-left: 4px solid #002D72; }}
        .summary-card.error {{ border-left: 4px solid #dc3545; }}
        .summary-value {{
            font-size: 32px;
            font-weight: 700;
            color: #002D72;
        }}
        .summary-label {{
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
        }}
        h2 {{
            font-size: 18px;
            color: #002D72;
            margin: 32px 0 16px;
            padding-bottom: 8px;
            border-bottom: 2px solid #28a745;
        }}
        h2:first-of-type {{ margin-top: 0; }}
        .finding {{
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 16px;
        }}
        .finding.success {{ border-color: #28a745; background: #f0fff4; }}
        .finding.error {{ border-color: #dc3545; background: #fff0f0; }}
        .finding.warning {{ border-color: #FF6319; background: #fff8f0; }}
        .finding-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
        }}
        .finding-icon {{ font-size: 24px; }}
        .finding-title {{ font-weight: 600; font-size: 16px; color: #333; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            margin: 16px 0;
        }}
        th {{
            background: #002D72;
            color: white;
            padding: 10px 12px;
            text-align: left;
            font-size: 11px;
            text-transform: uppercase;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #e9ecef;
            vertical-align: top;
        }}
        tr:hover {{ background: #f8f9fa; }}
        .status-badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }}
        .status-ok {{ background: #28a745; color: white; }}
        .status-fail {{ background: #dc3545; color: white; }}
        .status-warn {{ background: #FF6319; color: white; }}
        .url {{
            font-family: monospace;
            font-size: 11px;
            word-break: break-all;
            color: #002D72;
        }}
        .footer {{
            background: #f8f9fa;
            padding: 20px 32px;
            font-size: 12px;
            color: #666;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{header_icon} Link Test Report</h1>
            <div class="subtitle">Databook Weekly Newsletter • {now}</div>
        </div>

        <div class="content">
            <div class="summary-grid">
                <div class="summary-card info">
                    <div class="summary-value">{total}</div>
                    <div class="summary-label">Total Links</div>
                </div>
                <div class="summary-card success">
                    <div class="summary-value">{ok_count}</div>
                    <div class="summary-label">Working</div>
                </div>
                <div class="summary-card {"error" if failed_count > 0 else "success"}">
                    <div class="summary-value">{failed_count}</div>
                    <div class="summary-label">Failed</div>
                </div>
                <div class="summary-card info">
                    <div class="summary-value">{len(set(l["url"] for l in links))}</div>
                    <div class="summary-label">Unique URLs</div>
                </div>
            </div>
'''
    
    # Failed links section (if any)
    if failed_links:
        html += '''
            <h2>❌ Failed Links</h2>
            <div class="finding error">
                <table>
                    <thead>
                        <tr>
                            <th>Link Text</th>
                            <th>URL</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
'''
        for link in failed_links:
            error_msg = link.get("error", "")[:30] if link.get("error") else f"HTTP {link.get('status', '?')}"
            html += f'''                        <tr>
                            <td>{link.get("text", "")}</td>
                            <td class="url">{link["url"]}</td>
                            <td><span class="status-badge status-fail">{error_msg}</span></td>
                        </tr>
'''
        html += '''                    </tbody>
                </table>
            </div>
'''
    
    # Organization links
    if categories.get("organization"):
        html += '''
            <h2>✅ Organization Links</h2>
            <div class="finding success">
                <table>
                    <thead>
                        <tr>
                            <th>Agency</th>
                            <th>URL Path</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
'''
        for link in categories["organization"]:
            status_class = "status-ok" if link.get("ok") else "status-fail"
            status_text = "OK" if link.get("ok") else "FAIL"
            path = link["url"].replace("https://databook.nyc/o/", "/o/")
            html += f'''                        <tr>
                            <td>{link.get("text", "")}</td>
                            <td class="url">{path}</td>
                            <td><span class="status-badge {status_class}">{status_text}</span></td>
                        </tr>
'''
        html += '''                    </tbody>
                </table>
            </div>
'''

    # Contract links
    if categories.get("contract"):
        html += '''
            <h2>✅ Contract Links</h2>
            <div class="finding success">
                <table>
                    <thead>
                        <tr>
                            <th>Contract</th>
                            <th>URL Path</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
'''
        for link in categories["contract"]:
            status_class = "status-ok" if link.get("ok") else "status-fail"
            status_text = "OK" if link.get("ok") else "FAIL"
            path = link["url"].replace("https://databook.nyc", "")
            html += f'''                        <tr>
                            <td>{link.get("text", "")}</td>
                            <td class="url">{path}</td>
                            <td><span class="status-badge {status_class}">{status_text}</span></td>
                        </tr>
'''
        html += '''                    </tbody>
                </table>
            </div>
'''

    # External links
    external_cats = ["city_record", "passport", "checkbook", "external"]
    ext_links = []
    for cat in external_cats:
        ext_links.extend(categories.get(cat, []))
    
    if ext_links:
        html += '''
            <h2>✅ External Links</h2>
            <div class="finding success">
                <table>
                    <thead>
                        <tr>
                            <th>Domain</th>
                            <th>Description</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
'''
        # Dedupe by domain
        seen_domains = set()
        for link in ext_links:
            domain = re.search(r'https?://([^/]+)', link["url"])
            if domain:
                domain = domain.group(1)
                if domain not in seen_domains:
                    seen_domains.add(domain)
                    status_class = "status-ok" if link.get("ok") else "status-fail"
                    status_text = "OK" if link.get("ok") else "FAIL"
                    html += f'''                        <tr>
                            <td class="url">{domain}</td>
                            <td>{link.get("text", "")[:40]}</td>
                            <td><span class="status-badge {status_class}">{status_text}</span></td>
                        </tr>
'''
        html += '''                    </tbody>
                </table>
            </div>
'''

    html += f'''
        </div>

        <div class="footer">
            <strong>Summary:</strong> {org_links} org links • {contract_links} contract links • {len(set(l["url"] for l in ext_links))} external domains<br>
            Generated {now}
        </div>
    </div>
</body>
</html>
'''
    
    return html


async def validate_newsletter_links(html: str, output_path: Optional[str] = None) -> dict:
    """
    Main entry point: extract links from newsletter HTML, test them, generate report.
    
    Args:
        html: The generated newsletter HTML
        output_path: Optional path to save the HTML report
        
    Returns:
        dict with results summary
    """
    print("Extracting links from newsletter...")
    links = extract_links_from_html(html)
    print(f"Found {len(links)} links")
    
    print("Categorizing links...")
    categories = categorize_links(links)
    
    print("Testing links (this may take a moment)...")
    tested_links = await test_all_links(links)
    
    print("Generating report...")
    report_html = generate_report_html(tested_links, categories)
    
    if output_path:
        with open(output_path, 'w') as f:
            f.write(report_html)
        print(f"Report saved to: {output_path}")
    
    # Summary
    ok_count = sum(1 for l in tested_links if l.get("ok"))
    failed_count = len(tested_links) - ok_count
    
    return {
        "total_links": len(tested_links),
        "ok": ok_count,
        "failed": failed_count,
        "categories": {k: len(v) for k, v in categories.items()},
        "report_html": report_html,
        "failed_links": [l for l in tested_links if not l.get("ok")]
    }


async def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate newsletter links")
    parser.add_argument("--input", "-i", required=True, help="Input newsletter HTML file")
    parser.add_argument("--output", "-o", default="link_test_report.html", help="Output report file")
    args = parser.parse_args()
    
    with open(args.input, 'r') as f:
        html = f.read()
    
    result = await validate_newsletter_links(html, args.output)
    
    print(f"\n{'='*50}")
    print(f"Total: {result['total_links']} links")
    print(f"OK: {result['ok']}")
    print(f"Failed: {result['failed']}")
    print(f"Report: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
