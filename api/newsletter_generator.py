#!/usr/bin/env python3
"""
Databook Weekly Newsletter Generator

Generates AI-enhanced newsletter content using:
- PostgreSQL for data (contracts, events, notices)
- Gemini 2.0 Flash for compelling headlines and summaries
- Jinja2 for HTML template rendering
"""

import os
import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape

from google import genai
from google.genai import types

# Import database module
from postgrex import PostgresModelAsync


# ============================================================================
# Configuration
# ============================================================================

GEMINI_MODEL = "gemini-2.0-flash"

# Agency ID to slug mapping for URLs
AGENCY_SLUGS = {
    "170010827": "department-of-sanitation",
    "170010841": "department-of-transportation",
    "170010002": "mayors-office",
    "170010071": "department-of-homeless-services",
    "170010056": "police-department",
    "170011025": "office-of-administrative-trials-and-hearings",
    "170010059": "board-of-standards-and-appeals",
    "170010846": "department-of-parks-and-recreation",
    "170010136": "landmarks-preservation-commission",
    "170010073": "board-of-correction",
    "170020034": "nyc-housing-authority",
    "170010816": "department-of-health-and-mental-hygiene",
    "170010069": "department-of-social-services",
    "170010856": "department-of-citywide-administrative-services",
    "170010866": "department-of-consumer-and-worker-protection",
    "170010031": "campaign-finance-board",
}


# ============================================================================
# Gemini Client
# ============================================================================

_client = None

def get_gemini_client():
    """Get or create Gemini client."""
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        _client = genai.Client(api_key=api_key)
    return _client


# ============================================================================
# Database Queries
# ============================================================================

async def _query(sql: str, *args):
    """Execute a database query."""
    try:
        # Pass empty tuple () instead of None when no args - fixes asyncpg iterable error
        result = await PostgresModelAsync.select(sql, args if args else ())
        return result.get("rows", [])
    except Exception as e:
        print(f"Database query error: {e}")
        return []


async def get_pipeline_stats() -> dict:
    """Get contract pipeline statistics."""
    # Initialize with defaults to prevent template errors
    stats = {
        "pending_comptroller_count": 0,
        "pending_comptroller_total": 0.0,
        "contracts_in_queue": 0,
        "notices_30_days": 0,
        "capital_projects": 0,
    }
    
    try:
        # Pending Comptroller approval
        rows = await _query("""
            SELECT COUNT(*) as cnt, COALESCE(SUM(award_amount), 0) as total
            FROM contracts WHERE status ILIKE '%pending%comptroller%'
        """)
        if rows and len(rows) > 0:
            stats["pending_comptroller_count"] = rows[0].get("cnt", 0) or 0
            stats["pending_comptroller_total"] = float(rows[0].get("total", 0) or 0)
    except Exception as e:
        print(f"Stats query error (pending_comptroller): {e}")
    
    try:
        # Total contracts in queue (pending any approval)
        rows = await _query("""
            SELECT COUNT(*) as cnt FROM contracts WHERE status ILIKE '%pending%'
        """)
        if rows and len(rows) > 0:
            stats["contracts_in_queue"] = rows[0].get("cnt", 0) or 0
    except Exception as e:
        print(f"Stats query error (contracts_in_queue): {e}")
    
    try:
        # Notices in last 30 days
        rows = await _query("""
            SELECT COUNT(*) as cnt FROM crol
            WHERE start_date_parsed >= CURRENT_DATE - INTERVAL '30 days'
        """)
        if rows and len(rows) > 0:
            stats["notices_30_days"] = rows[0].get("cnt", 0) or 0
    except Exception as e:
        print(f"Stats query error (notices_30_days): {e}")
    
    try:
        # Capital projects count
        rows = await _query("""
            SELECT COUNT(*) as cnt FROM capitalprojectsdollarscomp
            WHERE "PUB_DATE" = (SELECT MAX("PUB_DATE") FROM capitalprojectsdollarscomp)
        """)
        if rows and len(rows) > 0:
            stats["capital_projects"] = rows[0].get("cnt", 0) or 0
    except Exception as e:
        print(f"Stats query error (capital_projects): {e}")
    
    return stats


async def get_top_contracts(limit: int = 5) -> list:
    """Get top pending contracts by value."""
    rows = await _query("""
        SELECT contract_id, ctr_id, contract_title, vendor_name, agency,
               award_amount, status, agency_id as org_id
        FROM contracts
        WHERE status ILIKE '%pending%'
        ORDER BY award_amount DESC NULLS LAST
        LIMIT $1
    """, limit)
    
    contracts = []
    for r in rows:
        org_id = str(r.get("org_id", ""))
        slug = AGENCY_SLUGS.get(org_id, "")
        contracts.append({
            "ctr_id": r.get("ctr_id"),
            "title": r.get("contract_title", "Untitled")[:60],
            "vendor": r.get("vendor_name", "Unknown")[:40],
            "agency": r.get("agency", "Unknown"),
            "agency_acronym": _get_agency_acronym(r.get("agency", "")),
            "amount": float(r.get("award_amount") or 0),
            "amount_formatted": _format_currency(r.get("award_amount")),
            "status": r.get("status", ""),
            "org_id": org_id,
            "org_slug": f"{org_id}-{slug}" if slug else None,
        })
    return contracts


async def get_upcoming_events(days: int = 7) -> list:
    """Get upcoming public events and hearings."""
    rows = await _query("""
        SELECT "EventDate", "SectionName", "ShortTitle", "RequestID",
               "wegov-org-name", "wegov-org-id", "TypeOfNoticeDescription",
               event_date_parsed
        FROM crol
        WHERE event_date_parsed IS NOT NULL
          AND event_date_parsed >= CURRENT_DATE
          AND event_date_parsed <= CURRENT_DATE + $1
        ORDER BY event_date_parsed
        LIMIT 10
    """, days)
    
    events = []
    for r in rows:
        org_id = str(r.get("wegov-org-id", ""))
        slug = AGENCY_SLUGS.get(org_id, "")
        event_date = r.get("event_date_parsed")
        
        events.append({
            "date": event_date,
            "day": event_date.day if event_date else "",
            "month": event_date.strftime("%b") if event_date else "",
            "time": _extract_time(r.get("EventDate", "")),
            "title": r.get("ShortTitle", "")[:80],
            "agency": r.get("wegov-org-name", "Unknown"),
            "agency_acronym": _get_agency_acronym(r.get("wegov-org-name", "")),
            "section": r.get("SectionName", ""),
            "notice_type": r.get("TypeOfNoticeDescription", ""),
            "request_id": r.get("RequestID"),
            "org_id": org_id,
            "org_slug": f"{org_id}-{slug}" if slug else None,
        })
    return events


async def get_recent_procurements(limit: int = 5) -> list:
    """Get recent procurement notices from City Record."""
    rows = await _query("""
        SELECT "StartDate", "ShortTitle", "RequestID",
               "wegov-org-name", "wegov-org-id"
        FROM crol
        WHERE "SectionName" IN ('Procurement', 'Contract Awards', 'Solicitations')
        ORDER BY start_date_parsed DESC
        LIMIT $1
    """, limit)
    
    notices = []
    for r in rows:
        org_id = str(r.get("wegov-org-id", ""))
        slug = AGENCY_SLUGS.get(org_id, "")
        notices.append({
            "title": r.get("ShortTitle", "")[:80],
            "date": r.get("StartDate", ""),
            "agency": r.get("wegov-org-name", "Unknown"),
            "agency_acronym": _get_agency_acronym(r.get("wegov-org-name", "")),
            "request_id": r.get("RequestID"),
            "org_id": org_id,
            "org_slug": f"{org_id}-{slug}" if slug else None,
        })
    return notices


async def get_data_anomalies() -> list:
    """Detect unusual patterns in contracts - for journalists."""
    anomalies = []
    
    # Sole-source contracts above $1M
    rows = await _query("""
        SELECT contract_title, vendor_name, agency, award_amount, ctr_id,
               "wegov-org-id" as org_id
        FROM contracts
        WHERE award_method ILIKE '%sole%source%' 
          AND award_amount > 1000000
          AND status ILIKE '%pending%'
        ORDER BY award_amount DESC
        LIMIT 3
    """)
    for r in rows:
        org_id = str(r.get("org_id", ""))
        slug = AGENCY_SLUGS.get(org_id, "")
        anomalies.append({
            "type": "sole_source",
            "icon": "🔍",
            "title": f"Sole-Source: {r.get('contract_title', 'Untitled')[:50]}",
            "detail": f"{_format_currency(r.get('award_amount'))} to {r.get('vendor_name', 'Unknown')[:30]}",
            "agency": r.get("agency", "")[:30],
            "ctr_id": r.get("ctr_id"),
            "org_slug": f"{org_id}-{slug}" if slug else None,
        })
    
    # Contract amendments > 50% of original value
    rows = await _query("""
        SELECT contract_title, vendor_name, agency, award_amount, 
               current_amount, ctr_id, agency_id as org_id
        FROM contracts
        WHERE current_amount > 0 
          AND award_amount > current_amount * 1.5
          AND status ILIKE '%pending%'
        ORDER BY (award_amount - current_amount) DESC
        LIMIT 3
    """)
    for r in rows:
        org_id = str(r.get("org_id", ""))
        slug = AGENCY_SLUGS.get(org_id, "")
        increase = float(r.get("award_amount", 0)) - float(r.get("current_amount", 0))
        anomalies.append({
            "type": "amendment",
            "icon": "📈",
            "title": f"Amendment: {r.get('contract_title', 'Untitled')[:50]}",
            "detail": f"+{_format_currency(increase)} increase ({r.get('vendor_name', '')[:25]})",
            "agency": r.get("agency", "")[:30],
            "ctr_id": r.get("ctr_id"),
            "org_slug": f"{org_id}-{slug}" if slug else None,
        })
    
    return anomalies[:5]


async def get_open_solicitations(limit: int = 5) -> list:
    """Get open procurement solicitations - for vendors."""
    rows = await _query("""
        SELECT "ShortTitle", "RequestID", "DueDate", "StartDate",
               "wegov-org-name", "wegov-org-id", "CategoryDescription",
               "TypeOfNoticeDescription"
        FROM crol
        WHERE "SectionName" = 'Procurement'
          AND "TypeOfNoticeDescription" ILIKE '%solicitation%'
          AND ("DueDate" IS NOT NULL AND "DueDate" != '')
        ORDER BY start_date_parsed DESC
        LIMIT $1
    """, limit)
    
    solicitations = []
    for r in rows:
        org_id = str(r.get("wegov-org-id", ""))
        slug = AGENCY_SLUGS.get(org_id, "")
        solicitations.append({
            "title": r.get("ShortTitle", "")[:60],
            "due_date": r.get("DueDate", ""),
            "category": r.get("CategoryDescription", ""),
            "agency": r.get("wegov-org-name", "Unknown"),
            "agency_acronym": _get_agency_acronym(r.get("wegov-org-name", "")),
            "request_id": r.get("RequestID"),
            "org_id": org_id,
            "org_slug": f"{org_id}-{slug}" if slug else None,
        })
    return solicitations


async def get_expiring_contracts(days: int = 90) -> list:
    """Get contracts expiring soon - rebid opportunities for vendors."""
    rows = await _query("""
        SELECT contract_title, vendor_name, agency, award_amount,
               end_date, ctr_id, agency_id as org_id
        FROM contracts
        WHERE end_date IS NOT NULL
          AND end_date >= CURRENT_DATE
          AND end_date <= CURRENT_DATE + $1
          AND award_amount > 500000
        ORDER BY end_date
        LIMIT 5
    """, days)
    
    expiring = []
    for r in rows:
        org_id = str(r.get("org_id", ""))
        slug = AGENCY_SLUGS.get(org_id, "")
        expiring.append({
            "title": r.get("contract_title", "Untitled")[:50],
            "vendor": r.get("vendor_name", "Unknown")[:30],
            "agency": r.get("agency", ""),
            "agency_acronym": _get_agency_acronym(r.get("agency", "")),
            "amount": _format_currency(r.get("award_amount")),
            "end_date": r.get("end_date"),
            "ctr_id": r.get("ctr_id"),
            "org_slug": f"{org_id}-{slug}" if slug else None,
        })
    return expiring


async def get_public_comment_deadlines(days: int = 14) -> list:
    """Get agency rules open for public comment - for activists."""
    rows = await _query("""
        SELECT "ShortTitle", "RequestID", "EndDate", "StartDate",
               "wegov-org-name", "wegov-org-id", "TypeOfNoticeDescription"
        FROM crol
        WHERE "SectionName" = 'Agency Rules'
          AND start_date_parsed >= CURRENT_DATE - INTERVAL '30 days'
          AND start_date_parsed <= CURRENT_DATE
        ORDER BY start_date_parsed DESC
        LIMIT 5
    """)
    
    comments = []
    for r in rows:
        org_id = str(r.get("wegov-org-id", ""))
        slug = AGENCY_SLUGS.get(org_id, "")
        comments.append({
            "title": r.get("ShortTitle", "")[:60],
            "deadline": r.get("EndDate", ""),
            "agency": r.get("wegov-org-name", "Unknown"),
            "agency_acronym": _get_agency_acronym(r.get("wegov-org-name", "")),
            "notice_type": r.get("TypeOfNoticeDescription", ""),
            "request_id": r.get("RequestID"),
            "org_id": org_id,
            "org_slug": f"{org_id}-{slug}" if slug else None,
        })
    return comments


async def get_all_newsletter_data() -> dict:
    """Fetch all data needed for the newsletter."""
    stats = await get_pipeline_stats()
    contracts = await get_top_contracts(5)
    events = await get_upcoming_events(7)
    procurements = await get_recent_procurements(5)
    
    # New sections
    anomalies = await get_data_anomalies()
    solicitations = await get_open_solicitations(5)
    expiring = await get_expiring_contracts(90)
    public_comments = await get_public_comment_deadlines(14)
    
    return {
        "stats": stats,
        "contracts": contracts,
        "events": events,
        "procurements": procurements,
        "anomalies": anomalies,
        "solicitations": solicitations,
        "expiring": expiring,
        "public_comments": public_comments,
        "generated_at": datetime.now(),
    }


# ============================================================================
# AI Content Generation
# ============================================================================

HEADLINE_PROMPT = """You are an NYC government transparency journalist writing for civic-minded New Yorkers.

Given this week's data, write 4 compelling news headlines with brief summaries. Be factual, not sensational.

DATA:
- Pending Comptroller Approval: ${pending_comptroller:,.0f}
- Contracts in Queue: {contracts_queue}
- City Record Notices (30 days): {notices_30d}

TOP PENDING CONTRACTS:
{contracts_list}

UPCOMING EVENTS:
{events_list}

Write exactly 4 headlines in this JSON format:
[
  {{
    "headline": "Brief, compelling headline",
    "summary": "2-3 sentence explanation of why this matters to New Yorkers.",
    "contract_ctr_id": "optional - ctr_id if about a specific contract",
    "org_slug": "optional - org_id-slug if about a specific agency",
    "accent": "orange" or "blue" (alternate)
  }}
]

Focus on:
- Large dollar amounts and their civic impact
- Transparency and accountability angles  
- Major agencies and services New Yorkers use daily
- Upcoming hearings citizens can attend

Return ONLY valid JSON, no markdown."""


WATCHLIST_PROMPT = """You are an NYC government transparency journalist.

Given this week's contract and event data, identify 3 items for a "Civic Watchlist" - things engaged citizens should pay attention to.

TOP CONTRACTS:
{contracts_list}

UPCOMING EVENTS:
{events_list}

Write exactly 3 watchlist items in this JSON format:
[
  {{
    "icon": "emoji like ⚠️ 📊 🔍 💰 🏛️",
    "title": "Brief watchlist title",
    "description": "One sentence explaining why to watch this."
  }}
]

Focus on accountability, large sums, public input opportunities.
Return ONLY valid JSON, no markdown."""


async def generate_ai_headlines(data: dict) -> list:
    """Generate compelling headlines using Gemini."""
    client = get_gemini_client()
    
    # Format contracts for prompt
    contracts_list = "\n".join([
        f"- {c['title']} ({c['agency']}): {c['amount_formatted']} - {c['status']}"
        for c in data.get("contracts", [])
    ])
    
    # Format events for prompt
    events_list = "\n".join([
        f"- {e['month']} {e['day']}: {e['title']} ({e['agency']})"
        for e in data.get("events", [])[:5]
    ])
    
    stats = data.get("stats", {})
    prompt = HEADLINE_PROMPT.format(
        pending_comptroller=stats.get("pending_comptroller_total", 0),
        contracts_queue=stats.get("contracts_in_queue", 0),
        notices_30d=stats.get("notices_30_days", 0),
        contracts_list=contracts_list or "No contracts data",
        events_list=events_list or "No events data",
    )
    
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
        )
        
        text = response.candidates[0].content.parts[0].text.strip()
        # Clean up any markdown code fences
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        
        headlines = json.loads(text)
        
        # Enrich with contract/org links from our data
        for i, h in enumerate(headlines):
            h["accent"] = "orange" if i % 2 == 0 else "blue"
            
            # Try to match ctr_id to get proper link
            if h.get("contract_ctr_id"):
                for c in data.get("contracts", []):
                    if str(c.get("ctr_id")) == str(h["contract_ctr_id"]):
                        h["contract_url"] = f"https://databook.nyc/procurement/contract/{c['ctr_id']}"
                        h["org_slug"] = c.get("org_slug")
                        break
        
        return headlines[:4]
        
    except Exception as e:
        print(f"AI headline generation error: {e}")
        # Fallback: generate basic headlines from data
        return _generate_fallback_headlines(data)


async def generate_ai_watchlist(data: dict) -> list:
    """Generate watchlist items using Gemini."""
    client = get_gemini_client()
    
    contracts_list = "\n".join([
        f"- {c['title']} ({c['agency']}): {c['amount_formatted']}"
        for c in data.get("contracts", [])
    ])
    
    events_list = "\n".join([
        f"- {e['month']} {e['day']}: {e['title']} ({e['agency']})"
        for e in data.get("events", [])[:5]
    ])
    
    prompt = WATCHLIST_PROMPT.format(
        contracts_list=contracts_list or "No contracts data",
        events_list=events_list or "No events data",
    )
    
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
        )
        
        text = response.candidates[0].content.parts[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        
        return json.loads(text)[:3]
        
    except Exception as e:
        print(f"AI watchlist generation error: {e}")
        return [
            {"icon": "📊", "title": "Large contracts pending approval", "description": "Monitor the Comptroller's registration queue."},
            {"icon": "🏛️", "title": "Public hearings this week", "description": "Opportunities for citizen input on city rules."},
            {"icon": "💰", "title": "Budget transparency", "description": "Track how agencies spend taxpayer dollars."},
        ]


def _generate_fallback_headlines(data: dict) -> list:
    """Generate basic headlines if AI fails."""
    headlines = []
    stats = data.get("stats", {})
    contracts = data.get("contracts", [])
    
    if contracts:
        c = contracts[0]
        headlines.append({
            "headline": f"{c['amount_formatted']} {c['title'][:40]} Contract Pending",
            "summary": f"A major contract from {c['agency']} awaits approval.",
            "accent": "orange",
            "contract_url": f"https://databook.nyc/procurement/contract/{c['ctr_id']}" if c.get('ctr_id') else None,
        })
    
    if stats.get("pending_comptroller_total"):
        headlines.append({
            "headline": f"${stats['pending_comptroller_total']/1e9:.1f}B in Contracts Await Comptroller Review",
            "summary": "The approval pipeline shows significant pending transactions.",
            "accent": "blue",
        })
    
    return headlines[:4]


# ============================================================================
# Utility Functions
# ============================================================================

def _format_currency(amount) -> str:
    """Format amount as currency with M/B suffix."""
    if amount is None:
        return "N/A"
    try:
        amt = float(amount)
        if amt >= 1e9:
            return f"${amt/1e9:.1f}B"
        elif amt >= 1e6:
            return f"${amt/1e6:.1f}M"
        elif amt >= 1e3:
            return f"${amt/1e3:.0f}K"
        else:
            return f"${amt:,.0f}"
    except (ValueError, TypeError):
        return "N/A"


def _get_agency_acronym(agency_name: str) -> str:
    """Extract acronym from agency name."""
    acronyms = {
        "Department of Transportation": "DOT",
        "Department of Sanitation": "DSNY",
        "Department of Homeless Services": "DHS",
        "Police Department": "NYPD",
        "Department of Parks and Recreation": "Parks",
        "Department of Health and Mental Hygiene": "DOHMH",
        "Department of Social Services": "DSS",
        "NYC Housing Authority": "NYCHA",
        "Department of Citywide Administrative Services": "DCAS",
        "Mayor's Office": "Mayor",
    }
    for name, acronym in acronyms.items():
        if name.lower() in agency_name.lower():
            return acronym
    return agency_name[:20]


def _extract_time(date_str: str) -> str:
    """Extract time from date string if present."""
    # Look for common time patterns
    import re
    match = re.search(r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)', str(date_str))
    if match:
        return match.group(1).upper()
    return ""


# ============================================================================
# Template Rendering
# ============================================================================

def render_newsletter(data: dict, headlines: list, watchlist: list) -> str:
    """Render the newsletter HTML using Jinja2 template."""
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(["html", "xml"])
    )
    
    # Add custom filters
    env.filters["currency"] = _format_currency
    
    template = env.get_template("newsletter_template.html")
    
    now = datetime.now()
    
    return template.render(
        edition_date=now.strftime("%A, %B %d, %Y"),
        stats=data.get("stats", {}),
        headlines=headlines,
        contracts=data.get("contracts", []),
        events=data.get("events", []),
        procurements=data.get("procurements", []),
        watchlist=watchlist,
        # New sections
        anomalies=data.get("anomalies", []),
        solicitations=data.get("solicitations", []),
        expiring=data.get("expiring", []),
        public_comments=data.get("public_comments", []),
        year=now.year,
    )


# ============================================================================
# Main Entry Point
# ============================================================================

async def generate_newsletter() -> str:
    """Generate the complete newsletter HTML."""
    print("Fetching newsletter data...")
    data = await get_all_newsletter_data()
    
    print("Generating AI headlines...")
    headlines = await generate_ai_headlines(data)
    
    print("Generating AI watchlist...")
    watchlist = await generate_ai_watchlist(data)
    
    print("Rendering template...")
    html = render_newsletter(data, headlines, watchlist)
    
    print(f"Newsletter generated: {len(html)} bytes")
    return html


async def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate Databook Weekly Newsletter")
    parser.add_argument("--preview", action="store_true", help="Save HTML to file for preview")
    parser.add_argument("--output", default="newsletter_preview.html", help="Output file path")
    args = parser.parse_args()
    
    html = await generate_newsletter()
    
    if args.preview:
        with open(args.output, "w") as f:
            f.write(html)
        print(f"Newsletter saved to {args.output}")
    else:
        print(html)


if __name__ == "__main__":
    asyncio.run(main())
