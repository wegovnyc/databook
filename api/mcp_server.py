#!/usr/bin/env python3
"""
Databook MCP Server - NYC Government Data for LLM clients.

Exposes NYC government data (organizations, titles, notices, capital projects)
via the Model Context Protocol (MCP) for use with Claude Desktop and other
MCP-compatible clients.

Usage:
    # Run with MCP inspector
    mcp dev mcp_server.py
    
    # Run directly  
    python mcp_server.py
"""
import os
import sys
import logging
import json
import time
import uuid
from datetime import datetime
from typing import Optional
from functools import wraps

import asyncpg
import aiohttp
from cachetools import TTLCache
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.server import TransportSecuritySettings

# Configure logging for detailed MCP request tracking
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [MCP] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("databook-mcp")

# Session tracking - captures transport session ID from MCP
_current_session = {"id": None, "start_time": None, "request_count": 0}

# Structured log storage for export
_tool_logs = []
MAX_LOGS = 1000  # Keep last 1000 logs in memory


def set_session_id(session_id: str):
    """Set the current session ID from MCP transport."""
    _current_session["id"] = session_id
    _current_session["start_time"] = datetime.now().isoformat()
    _current_session["request_count"] = 0
    logger.info(f"SESSION SET: {session_id}")


def get_logs():
    """Return all stored logs for export."""
    return _tool_logs


def clear_logs():
    """Clear all stored logs."""
    global _tool_logs
    _tool_logs = []


def log_tool_call(func):
    """Decorator to log all MCP tool calls with full details and structured output."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        tool_name = func.__name__
        session_id = _current_session.get("id") or "unknown"
        _current_session["request_count"] = _current_session.get("request_count", 0) + 1
        request_num = _current_session["request_count"]
        timestamp = datetime.now().isoformat()
        
        # Log the call with all arguments
        logger.info(f"{'='*60}")
        logger.info(f"TOOL CALL: {tool_name}")
        logger.info(f"SESSION: {session_id} | REQUEST #{request_num}")
        logger.info(f"ARGS: {args}")
        logger.info(f"KWARGS: {json.dumps(kwargs, default=str)}")
        
        start_time = time.time()
        error_msg = None
        result_preview = None
        row_count = None
        
        try:
            result = await func(*args, **kwargs)
            elapsed = (time.time() - start_time) * 1000
            
            # Log result summary
            result_str = str(result)
            result_preview = result_str[:500] if len(result_str) > 500 else result_str
            
            # Try to extract row count from result
            if "rows returned" in result_str.lower():
                try:
                    row_count = int(result_str.split("rows returned")[0].split()[-1])
                except:
                    pass
            elif result_str.startswith("**Found"):
                try:
                    row_count = int(result_str.split()[1])
                except:
                    pass
            
            logger.info(f"RESULT: {result_preview[:200]}...")
            logger.info(f"ELAPSED: {elapsed:.2f}ms")
            logger.info(f"{'='*60}")
            
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"ERROR: {error_msg}")
            logger.info(f"ELAPSED: {elapsed:.2f}ms")
            logger.info(f"{'='*60}")
            
            # Store log entry even on error
            log_entry = {
                "timestamp": timestamp,
                "session_id": session_id,
                "request_num": request_num,
                "tool_name": tool_name,
                "args": json.dumps(kwargs, default=str),
                "elapsed_ms": round(elapsed, 2),
                "row_count": None,
                "error": error_msg,
                "result_preview": None
            }
            _tool_logs.append(log_entry)
            if len(_tool_logs) > MAX_LOGS:
                _tool_logs.pop(0)
            
            raise
        
        # Store structured log entry for export
        log_entry = {
            "timestamp": timestamp,
            "session_id": session_id,
            "request_num": request_num,
            "tool_name": tool_name,
            "args": json.dumps(kwargs, default=str),
            "elapsed_ms": round(elapsed, 2),
            "row_count": row_count,
            "error": error_msg,
            "result_preview": result_preview[:200] if result_preview else None
        }
        _tool_logs.append(log_entry)
        if len(_tool_logs) > MAX_LOGS:
            _tool_logs.pop(0)
        
        # Also log as structured JSON for easy parsing
        logger.info(f"LOG_JSON: {json.dumps(log_entry)}")
        
        return result
    return wrapper


# Initialize MCP server with allowed hosts for production deployment
# Server description: NYC Government open data platform with 70+ datasets including
# agencies, employees, contracts, solicitations, capital projects, and City Record notices.
mcp = FastMCP(
    "DatabookNYC",
    instructions="NYC Government Databook - Open data platform with 70+ datasets covering agencies, employees, contracts, solicitations, capital projects, schools, and City Record notices. Start with get_database_overview() to explore available data.",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False  # Allow any host for production reverse proxy
    )
)

# Annotation preset for read-only search tools
READ_ONLY_ANNOTATIONS = {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False}

# ============================================================================
# Database Configuration
# ============================================================================

# Database connection pool (initialized on first use)
_pool: asyncpg.Pool = None


def get_db_config():
    """
    Get database configuration from environment or defaults.
    
    Environment variables:
        POSTGRES_HOST: Database host (default: localhost)
        POSTGRES_PORT: Database port (default: 5432)
        POSTGRES_DB: Database name (default: databook)
        POSTGRES_USER: Database user (default: postgres)
        POSTGRES_PASSWORD: Database password (required)
    """
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "database": os.getenv("POSTGRES_DB", "databook"),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", ""),
    }


async def get_pool() -> asyncpg.Pool:
    """Get or create the database connection pool."""
    global _pool
    if _pool is None:
        config = get_db_config()
        _pool = await asyncpg.create_pool(
            min_size=1,
            max_size=10,
            **config
        )
    return _pool


async def query(sql: str, *args):
    """Execute a query and return results as list of dicts."""
    logger.info(f"QUERY: {sql[:100]}... | ARGS: {args}")
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *args)
        result = [dict(r) for r in rows]
        logger.info(f"RESULT: {len(result)} rows returned")
        return result


async def query_one(sql: str, *args):
    """Execute a query and return a single result as dict."""
    logger.info(f"QUERY_ONE: {sql[:100]}... | ARGS: {args}")
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, *args)
        result = dict(row) if row else None
        logger.info(f"RESULT: {result}")
        return result


def format_currency(amount) -> str:
    """Format a number as currency."""
    if amount is None:
        return "N/A"
    try:
        return f"${float(amount):,.2f}"
    except (ValueError, TypeError):
        return "N/A"


def _num(col: str) -> str:
    """SQL expression that parses a *text* numeric column into numeric.

    Many Databook tables are imported straight from CSV, so numeric fields
    (salaries, budgets, headcounts, lat/long) are stored as text. Aggregating
    or comparing them (SUM/AVG/>) requires stripping any non-numeric characters
    and casting first. `col` must be an already-quoted identifier, e.g. '"Base Salary"'.

    Cleaned values are cast only when they form a well-formed number; anything
    else (empty, or placeholders like '-' or '.') becomes NULL rather than
    raising 'invalid input syntax for type numeric'. The column is cast to text
    first so this is safe whether the column is text, char, or already numeric
    (mixed types occur across Databook tables, e.g. capital-project budgets).
    """
    cleaned = f"regexp_replace(COALESCE({col}::text, ''), '[^0-9.-]', '', 'g')"
    return (f"(CASE WHEN {cleaned} ~ '^-?[0-9]+([.][0-9]+)?$' "
            f"THEN {cleaned}::numeric ELSE NULL END)")


def slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    import re
    if not text:
        return ""
    # Lowercase, replace spaces with hyphens, remove special chars
    slug = text.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug[:50]  # Limit length


# ============================================================================
# Database Overview Tool
# ============================================================================

@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_database_overview() -> str:
    """
    Get a summary of all available data in the Databook database.
    
    Returns counts for organizations, titles, notices, capital projects, and more.
    Use this to understand what data is available before diving into specifics.
    """
    tables = [
        ("wegov_orgs", "Organizations (agencies, boards, offices)"),
        ("civillist", "Civil service employees"),
        ("nyccivilservicetitles", "Civil service job titles"),
        ("crol", "City Record notices (CROL)"),
        ("capitalprojectsdollarscomp", "Capital projects"),
        ("contracts", "Procurement contracts"),
        ("vendors", "Registered vendors"),
        ("solicitations", "Active solicitations"),
    ]
    
    results = ["**Databook Database Overview**\n"]
    
    # Use pg_class estimated counts — instant instead of COUNT(*) full scans
    table_names = [t[0] for t in tables]
    try:
        rows = await query(
            """
            SELECT relname, reltuples::bigint AS c
            FROM pg_class
            WHERE relname = ANY($1)
              AND relkind = 'r'
            """,
            table_names
        )
        count_map = {r["relname"]: r["c"] for r in rows}
    except Exception:
        count_map = {}
    
    for table, description in tables:
        count = count_map.get(table, 0)
        if count >= 0:
            results.append(f"- **{description}**: {count:,} records")
        else:
            results.append(f"- **{description}**: (stats pending)")
    
    return "\n".join(results)


# ============================================================================
# Organization Tools
# ============================================================================

@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def search_organizations(query_text: str, limit: int = 20) -> str:
    """
    Search NYC organizations (agencies, boards, offices) by name.
    
    Args:
        query_text: Organization name to search for (partial match supported)
        limit: Maximum number of results (default 20, max 50)
    
    Returns:
        List of matching organizations with basic info
    """
    limit = min(limit, 50)
    
    rows = await query(
        """
        SELECT id, name, type, alternate_name AS acronym, parent_name
        FROM wegov_orgs
        WHERE name ILIKE $1 OR alternate_name ILIKE $1
        ORDER BY name
        LIMIT $2
        """,
        f"%{query_text}%", limit
    )
    
    if not rows:
        return f"No organizations found matching '{query_text}'"
    
    results = [f"**Found {len(rows)} organization(s) matching '{query_text}':**\n"]
    for r in rows:
        acronym = f" ({r['acronym']})" if r.get('acronym') else ""
        parent = f" - Part of: {r['parent_name']}" if r.get('parent_name') else ""
        results.append(f"- **{r['name']}**{acronym} [ID: {r['id']}]\n  Type: {r['type']}{parent}")
    
    return "\n".join(results)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_organization_profile(org_id: int) -> str:
    """
    Get detailed profile for a specific NYC organization.
    
    Args:
        org_id: The organization ID (from search_organizations)
    
    Returns:
        Complete organization profile with stats
    """
    org = await query_one(
        """
        SELECT id, name, type, alternate_name AS acronym, parent_name,
               url AS website, main_address AS address, main_phone AS phone,
               description
        FROM wegov_orgs
        WHERE id = $1
        """,
        org_id
    )
    
    if not org:
        return f"Organization with ID {org_id} not found"
    
    # Get headcount stats
    headcount = await query_one(
        f"""
        SELECT SUM({_num('"HEADCOUNT"')}) as total
        FROM headcountactualsfunding
        WHERE "wegov-org-id" = $1
        AND "FISCAL YEAR" = (SELECT MAX("FISCAL YEAR") FROM headcountactualsfunding)
        """,
        str(org_id)
    )

    # Get spending stats
    spending = await query_one(
        f"""
        SELECT SUM({_num('"AMOUNT"')} * 1000) as total
        FROM expenseactualsfunding
        WHERE "wegov-org-id" = $1
        AND "FISCAL YEAR" = (SELECT MAX("FISCAL YEAR") FROM expenseactualsfunding)
        """,
        str(org_id)
    )
    
    # Get capital projects count
    projects = await query_one(
        """
        SELECT count(*) as c 
        FROM capitalprojectsdollarscomp 
        WHERE "wegov-org-id" = $1
        AND "PUB_DATE" = (SELECT MAX("PUB_DATE") FROM capitalprojectsdollarscomp)
        """,
        str(org_id)
    )
    
    profile = f"""
**{org['name']}**
{f"({org['acronym']})" if org.get('acronym') else ""}

**Basic Info:**
- Type: {org['type']}
- ID: {org['id']}
- Website: {org.get('website') or 'N/A'}
- Phone: {org.get('phone') or 'N/A'}

**Current Statistics:**
- Headcount (FTE): {int(headcount['total']) if headcount and headcount.get('total') else 'N/A'}
- Annual Spending: {format_currency(spending['total']) if spending and spending.get('total') else 'N/A'}
- Active Capital Projects: {projects['c'] if projects else 0}
"""
    
    if org.get('description'):
        profile += f"\n**Description:**\n{org['description'][:500]}..."
    
    return profile.strip()


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_organization_notices(org_id: int, limit: int = 10) -> str:
    """
    Get recent City Record notices for an organization.
    
    Args:
        org_id: The organization ID
        limit: Maximum notices to return (default 10, max 50)
    
    Returns:
        List of recent notices for the organization
    """
    limit = min(limit, 50)
    
    rows = await query(
        """
        SELECT "StartDate", "SectionName", "ShortTitle", "RequestID",
               "TypeOfNoticeDescription"
        FROM crol
        WHERE "wegov-org-id" = $1
        ORDER BY start_date_parsed DESC
        LIMIT $2
        """,
        str(org_id), limit
    )
    
    if not rows:
        return f"No notices found for organization ID {org_id}"
    
    results = [f"**Recent City Record Notices ({len(rows)} shown):**\n"]
    for r in rows:
        results.append(
            f"- **{r['StartDate']}** [{r['SectionName']}]\n"
            f"  {r['ShortTitle'][:80]}...\n"
            f"  Type: {r.get('TypeOfNoticeDescription', 'N/A')} | ID: {r['RequestID']}\n"
            f"  📄 City Record: https://a856-cityrecord.nyc.gov/RequestDetail/{r['RequestID']}"
        )
    
    return "\n".join(results)


# ============================================================================
# Civil Service Title Tools
# ============================================================================

@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def search_civil_titles(query_text: str, limit: int = 20) -> str:
    """
    Search NYC civil service job titles.
    
    Args:
        query_text: Title name or code to search (partial match)
        limit: Maximum results (default 20, max 50)
    
    Returns:
        List of matching civil service titles
    """
    limit = min(limit, 50)
    
    rows = await query(
        """
        SELECT "Title Code" as code, "Title Description" as title, 
               "Minimum Salary Rate" as min_salary, "Maximum Salary Rate" as max_salary
        FROM nyccivilservicetitles
        WHERE "Title Description" ILIKE $1 OR "Title Code" ILIKE $1
        ORDER BY "Title Description"
        LIMIT $2
        """,
        f"%{query_text}%", limit
    )
    
    if not rows:
        return f"No civil service titles found matching '{query_text}'"
    
    results = [f"**Found {len(rows)} title(s) matching '{query_text}':**\n"]
    for r in rows:
        salary_range = ""
        if r.get('min_salary') and r.get('max_salary'):
            salary_range = f" | Salary: {format_currency(r['min_salary'])} - {format_currency(r['max_salary'])}"
        results.append(f"- **{r['title']}** (Code: {r['code']}){salary_range}")
    
    return "\n".join(results)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_title_positions(job_code: str, limit: int = 20) -> str:
    """
    Get employees currently holding a specific civil service title.
    
    Args:
        job_code: The job code (e.g., "10026" from search_civil_titles)
        limit: Maximum results (default 20, max 50)
    
    Returns:
        List of employees with this title
    """
    limit = min(limit, 50)
    
    # Get title info
    title = await query_one(
        """
        SELECT "Title Code" as code, "Title Description" as title
        FROM nyccivilservicetitles
        WHERE TRIM("Title Code") = $1
        """,
        job_code.strip()
    )
    
    if not title:
        return f"Title with code '{job_code}' not found"
    
    # Get current employees
    employees = await query(
        f"""
        SELECT "EMPLOYEE NAME" as name,
               "wegov-org-name" as agency, {_num('"SALARY RATE"')} as salary
        FROM civillist
        WHERE "wegov-service-title-id" = $1
        ORDER BY salary DESC NULLS LAST
        LIMIT $2
        """,
        job_code, limit
    )
    
    total = await query_one(
        """
        SELECT count(*) as c FROM civillist 
        WHERE "wegov-service-title-id" = $1
        """,
        job_code
    )
    
    result = f"**{title['title']}** (Code: {title['code']})\n"
    result += f"Total Positions: {total['c'] if total else 0}\n\n"
    
    if employees:
        result += f"**Sample Employees ({len(employees)} shown):**\n"
        for e in employees:
            result += f"- {e['name']} - {e['agency']} ({format_currency(e.get('salary'))})\n"
    
    return result.strip()


# ============================================================================
# Notices (CROL) Tools
# ============================================================================

@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def search_notices(
    query_text: Optional[str] = None,
    section: Optional[str] = None,
    limit: int = 20
) -> str:
    """
    Search City Record Online (CROL) notices.
    
    Args:
        query_text: Search in title or description (optional)
        section: Filter by section (e.g., "Contract Awards", "Public Hearings")
        limit: Maximum results (default 20, max 50)
    
    Returns:
        List of matching notices
    """
    limit = min(limit, 50)
    
    conditions = []
    params = []
    param_idx = 1
    
    if query_text:
        conditions.append(f'"ShortTitle" ILIKE ${param_idx}')
        params.append(f"%{query_text}%")
        param_idx += 1
    
    if section:
        conditions.append(f'"SectionName" ILIKE ${param_idx}')
        params.append(f"%{section}%")
        param_idx += 1
    
    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    params.append(limit)
    
    rows = await query(
        f"""
        SELECT "StartDate", "SectionName", "ShortTitle", "RequestID",
               "wegov-org-name", "TypeOfNoticeDescription"
        FROM crol
        {where_clause}
        ORDER BY start_date_parsed DESC
        LIMIT ${param_idx}
        """,
        *params
    )
    
    if not rows:
        return "No notices found matching the criteria"
    
    results = [f"**Found {len(rows)} notice(s):**\n"]
    for r in rows:
        results.append(
            f"- **{r['StartDate']}** [{r['SectionName']}]\n"
            f"  {r['ShortTitle'][:80]}...\n"
            f"  Agency: {r.get('wegov-org-name', 'N/A')} | ID: {r['RequestID']}\n"
            f"  📄 City Record: https://a856-cityrecord.nyc.gov/RequestDetail/{r['RequestID']}"
        )
    
    return "\n".join(results)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_notice_stats() -> str:
    """
    Get City Record notice statistics for the last 30 days.
    
    Returns summary by section type to understand recent government activity.
    """
    rows = await query(
        """
        SELECT "SectionName", COUNT(*) as count
        FROM crol
        WHERE start_date_parsed >= current_date - INTERVAL '30 days'
        GROUP BY "SectionName"
        ORDER BY count DESC
        """
    )
    
    if not rows:
        return "No recent notices found"
    
    total = sum(r['count'] for r in rows)
    
    results = [f"**City Record Notices (Last 30 Days)**\n"]
    results.append(f"Total: {total:,} notices\n")
    results.append("**By Section:**")
    
    for r in rows:
        pct = (r['count'] / total * 100) if total > 0 else 0
        results.append(f"- {r['SectionName']}: {r['count']:,} ({pct:.1f}%)")
    
    return "\n".join(results)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_recent_events(limit: int = 10) -> str:
    """
    Get upcoming public events and hearings from the City Record.
    
    Args:
        limit: Maximum events to return (default 10, max 30)
    
    Returns:
        List of upcoming events with dates and details
    """
    limit = min(limit, 30)
    
    rows = await query(
        """
        SELECT "EventDate", "SectionName", "ShortTitle", "RequestID",
               "wegov-org-name", "TypeOfNoticeDescription"
        FROM crol
        WHERE event_date_parsed IS NOT NULL
          AND event_date_parsed >= current_date
        ORDER BY event_date_parsed
        LIMIT $1
        """,
        limit
    )
    
    if not rows:
        return "No upcoming events found"
    
    results = [f"**Upcoming City Events ({len(rows)} shown):**\n"]
    for r in rows:
        results.append(
            f"- **{r['EventDate']}** [{r['SectionName']}]\n"
            f"  {r['ShortTitle'][:80]}...\n"
            f"  Agency: {r.get('wegov-org-name', 'N/A')} | ID: {r['RequestID']}\n"
            f"  📄 City Record: https://a856-cityrecord.nyc.gov/RequestDetail/{r['RequestID']}"
        )
    
    return "\n".join(results)


# ============================================================================
# Capital Projects Tools
# ============================================================================

@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def search_capital_projects(query_text: str, limit: int = 20) -> str:
    """
    Search NYC capital projects by name or ID.
    
    Args:
        query_text: Project name or ID to search
        limit: Maximum results (default 20, max 50)
    
    Returns:
        List of matching capital projects
    """
    limit = min(limit, 50)
    
    rows = await query(
        """
        SELECT "PROJECT_ID", "PROJECT_DESCR" as title, "wegov-org-name" as agency, 
               "wegov-org-id" as org_id, "BUDG_CURR" as budget
        FROM capitalprojectsdollarscomp
        WHERE ("PROJECT_DESCR" ILIKE $1 OR "PROJECT_ID" ILIKE $1)
          AND "PUB_DATE" = (SELECT MAX("PUB_DATE") FROM capitalprojectsdollarscomp)
        ORDER BY "PROJECT_DESCR"
        LIMIT $2
        """,
        f"%{query_text}%", limit
    )
    
    if not rows:
        return f"No capital projects found matching '{query_text}'"
    
    results = [f"**Found {len(rows)} project(s) matching '{query_text}':**\n"]
    for r in rows:
        title = r.get('title') or 'Untitled'
        results.append(
            f"- **{title[:60]}** [ID: {r['PROJECT_ID']}]\n"
            f"  Agency: {r.get('agency', 'N/A')} | Budget: {format_currency(r.get('budget'))}"
        )
    
    return "\n".join(results)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_project_details(project_id: str) -> str:
    """
    Get detailed information for a specific capital project.
    
    Args:
        project_id: The project ID (e.g., "HW1234")
    
    Returns:
        Full project details with budget and schedule
    """
    project = await query_one(
        f"""
        SELECT "PROJECT_ID",
               "PROJECT_DESCR" AS title,
               "wegov-org-name" AS agency,
               "TYP_CATEGORY_NAME" AS project_type,
               {_num('"BUDG_CURR"')} AS budg_curr,
               {_num('"BUDG_ORIG"')} AS budg_orig,
               {_num('"BUDG_DIFF"')} AS budg_diff,
               "START_CURR" AS start_date,
               "END_CURR" AS end_date
        FROM capitalprojectsdollarscomp
        WHERE "PROJECT_ID" = $1
          AND "PUB_DATE" = (SELECT MAX("PUB_DATE") FROM capitalprojectsdollarscomp)
        """,
        project_id
    )

    if not project:
        return f"Project '{project_id}' not found"

    details = f"""
**{project.get('title') or 'Untitled Project'}**

**Basic Info:**
- Project ID: {project['PROJECT_ID']}
- Managing Agency: {project.get('agency') or 'N/A'}
- Project Type: {project.get('project_type') or 'N/A'}

**Budget:**
- Current Budget: {format_currency(project.get('budg_curr'))}
- Original Budget: {format_currency(project.get('budg_orig'))}
- Budget Difference: {format_currency(project.get('budg_diff'))}

**Schedule:**
- Start Date: {project.get('start_date') or 'N/A'}
- End Date: {project.get('end_date') or 'N/A'}
"""

    return details.strip()


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_agency_projects(agency: str, limit: int = 15) -> str:
    """
    Get capital projects for a specific agency.
    
    Args:
        agency: Agency name (partial match, e.g., "Parks", "DOT")
        limit: Maximum results (default 15, max 50)
    
    Returns:
        List of capital projects for the agency
    """
    limit = min(limit, 50)
    
    # Get aggregate stats
    stats = await query_one(
        """
        SELECT COUNT(*) as count,
               SUM(CAST(REPLACE(COALESCE("BUDG_CURR", '0'), ',', '') AS NUMERIC)) as total_budget
        FROM capitalprojectsdollarscomp
        WHERE "wegov-org-name" ILIKE $1
          AND "PUB_DATE" = (SELECT MAX("PUB_DATE") FROM capitalprojectsdollarscomp)
        """,
        f"%{agency}%"
    )
    
    rows = await query(
        """
        SELECT "PROJECT_ID", "PROJECT_DESCR" as title, "BUDG_CURR" as budget
        FROM capitalprojectsdollarscomp
        WHERE "wegov-org-name" ILIKE $1
          AND "PUB_DATE" = (SELECT MAX("PUB_DATE") FROM capitalprojectsdollarscomp)
        ORDER BY CAST(REPLACE(COALESCE("BUDG_CURR", '0'), ',', '') AS NUMERIC) DESC
        LIMIT $2
        """,
        f"%{agency}%", limit
    )
    
    if not rows:
        return f"No capital projects found for agency '{agency}'"
    
    result = f"**Capital Projects: {agency}**\n\n"
    result += f"**Summary:**\n"
    result += f"- Total Projects: {stats['count'] if stats else 0}\n"
    result += f"- Total Budget: {format_currency(stats.get('total_budget')) if stats else 'N/A'}\n\n"
    result += f"**Top Projects by Budget ({len(rows)} shown):**\n"
    
    for r in rows:
        title = r.get('title') or 'Untitled'
        result += f"- **{title[:50]}** [ID: {r['PROJECT_ID']}]\n"
        result += f"  Budget: {format_currency(r.get('budget'))}\n"
    
    return result.strip()


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_project_milestones(days_back: int = 7, days_forward: int = 7, limit: int = 20) -> str:
    """
    Get largest capital projects with any milestones (start, end, or intermediate) within a date range.
    
    Queries the capitalprojectsmilestones table for actual milestone dates and joins
    with project details for budget info. Returns the largest projects by current budget.
    
    Args:
        days_back: Days to look back for past milestones (default 7)
        days_forward: Days to look ahead for upcoming milestones (default 7)
        limit: Maximum results (default 20, max 50)
    
    Returns:
        Largest projects with recent or upcoming milestones, grouped by timing
    """
    limit = min(limit, 50)
    
    # Get projects with milestones in last N days (from capitalprojectsmilestones table)
    # Join with dollarscomp for budget info, order by budget desc for "largest projects"
    # capitalprojectsmilestones dates are "Mon YYYY" (e.g. "Jun 2006");
    # capitalprojectsdollarscomp dates are "MM/DD/YYYY". Both are text, so
    # each date is regex-guarded before TO_DATE to avoid parse exceptions.
    budget_num = _num('d."BUDG_CURR"')
    dc_budget_num = _num('"BUDG_CURR"')
    past_milestones = await query(
        f"""
        SELECT DISTINCT ON (m."PROJECT_ID")
               m."PROJECT_ID",
               m."TASK_DESCRIPTION" as milestone_name,
               m."TASK_END_DATE" as milestone_date,
               m."PROJECT_DESCR" as title,
               m."wegov-org-name" as agency,
               {budget_num} as budget
        FROM capitalprojectsmilestones m
        LEFT JOIN capitalprojectsdollarscomp d
          ON m."PROJECT_ID" = d."PROJECT_ID"
          AND d."PUB_DATE" = (SELECT MAX("PUB_DATE") FROM capitalprojectsdollarscomp)
        WHERE m."PUB_DATE" = (SELECT MAX("PUB_DATE") FROM capitalprojectsmilestones)
          AND m."TASK_END_DATE" ~ '^[A-Za-z]{{3}} [0-9]{{4}}$'
          AND TO_DATE(m."TASK_END_DATE", 'Mon YYYY') >= current_date - make_interval(days => $1)
          AND TO_DATE(m."TASK_END_DATE", 'Mon YYYY') <= current_date
        ORDER BY m."PROJECT_ID", {budget_num} DESC NULLS LAST
        LIMIT $2
        """,
        days_back, limit // 2
    )

    # Get projects with upcoming milestones
    upcoming_milestones = await query(
        f"""
        SELECT DISTINCT ON (m."PROJECT_ID")
               m."PROJECT_ID",
               m."TASK_DESCRIPTION" as milestone_name,
               m."TASK_END_DATE" as milestone_date,
               m."PROJECT_DESCR" as title,
               m."wegov-org-name" as agency,
               {budget_num} as budget
        FROM capitalprojectsmilestones m
        LEFT JOIN capitalprojectsdollarscomp d
          ON m."PROJECT_ID" = d."PROJECT_ID"
          AND d."PUB_DATE" = (SELECT MAX("PUB_DATE") FROM capitalprojectsdollarscomp)
        WHERE m."PUB_DATE" = (SELECT MAX("PUB_DATE") FROM capitalprojectsmilestones)
          AND m."TASK_END_DATE" ~ '^[A-Za-z]{{3}} [0-9]{{4}}$'
          AND TO_DATE(m."TASK_END_DATE", 'Mon YYYY') > current_date
          AND TO_DATE(m."TASK_END_DATE", 'Mon YYYY') <= current_date + make_interval(days => $1)
        ORDER BY m."PROJECT_ID", {budget_num} DESC NULLS LAST
        LIMIT $2
        """,
        days_forward, limit // 2
    )

    # Also get projects that started or are ending (for completeness)
    started = await query(
        f"""
        SELECT "PROJECT_ID", "PROJECT_DESCR" as title, "wegov-org-name" as agency,
               {dc_budget_num} as budget,
               "START_CURR" as "START_DATE", "END_CURR" as "END_DATE"
        FROM capitalprojectsdollarscomp
        WHERE "PUB_DATE" = (SELECT MAX("PUB_DATE") FROM capitalprojectsdollarscomp)
          AND "START_CURR" ~ '^[0-9]{{2}}/[0-9]{{2}}/[0-9]{{4}}$'
          AND TO_DATE("START_CURR", 'MM/DD/YYYY') >= current_date - make_interval(days => $1)
          AND TO_DATE("START_CURR", 'MM/DD/YYYY') <= current_date
        ORDER BY {dc_budget_num} DESC NULLS LAST
        LIMIT $2
        """,
        days_back, limit // 4
    )

    ending = await query(
        f"""
        SELECT "PROJECT_ID", "PROJECT_DESCR" as title, "wegov-org-name" as agency,
               {dc_budget_num} as budget,
               "START_CURR" as "START_DATE", "END_CURR" as "END_DATE"
        FROM capitalprojectsdollarscomp
        WHERE "PUB_DATE" = (SELECT MAX("PUB_DATE") FROM capitalprojectsdollarscomp)
          AND "END_CURR" ~ '^[0-9]{{2}}/[0-9]{{2}}/[0-9]{{4}}$'
          AND TO_DATE("END_CURR", 'MM/DD/YYYY') >= current_date
          AND TO_DATE("END_CURR", 'MM/DD/YYYY') <= current_date + make_interval(days => $1)
        ORDER BY {dc_budget_num} DESC NULLS LAST
        LIMIT $2
        """,
        days_forward, limit // 4
    )
    
    result = f"**Capital Project Milestones (Largest by Budget)**\n\n"
    
    def format_project(p):
        """Format a project with its Databook URL."""
        title = p.get('title') or 'Untitled'
        project_id = p['PROJECT_ID']
        slug = slugify(title)
        databook_url = f"https://databook.nyc/p/{project_id}_{slug}" if project_id else "N/A"
        return title, project_id, databook_url
    
    # Past milestones section
    if past_milestones:
        result += f"**Milestones Completed (Last {days_back} Days):** {len(past_milestones)} projects\n\n"
        for p in past_milestones:
            title, project_id, databook_url = format_project(p)
            result += f"- **{title[:55]}**\n"
            result += f"  Agency: {p.get('agency', 'N/A')} | Budget: {format_currency(p.get('budget'))}\n"
            result += f"  Milestone: {p.get('milestone_name', 'N/A')} on {p.get('milestone_date', 'N/A')}\n"
            result += f"  📊 Databook URL: {databook_url}\n"
    
    if started:
        result += f"\n**Projects Started (Last {days_back} Days):** {len(started)} projects\n\n"
        for p in started:
            title, project_id, databook_url = format_project(p)
            result += f"- **{title[:55]}**\n"
            result += f"  Agency: {p.get('agency', 'N/A')} | Budget: {format_currency(p.get('budget'))}\n"
            result += f"  Started: {p.get('START_DATE', 'N/A')} | Scheduled End: {p.get('END_DATE', 'N/A')}\n"
            result += f"  📊 Databook URL: {databook_url}\n"
    
    # Upcoming milestones section
    if upcoming_milestones:
        result += f"\n**Upcoming Milestones (Next {days_forward} Days):** {len(upcoming_milestones)} projects\n\n"
        for p in upcoming_milestones:
            title, project_id, databook_url = format_project(p)
            result += f"- **{title[:55]}**\n"
            result += f"  Agency: {p.get('agency', 'N/A')} | Budget: {format_currency(p.get('budget'))}\n"
            result += f"  Milestone: {p.get('milestone_name', 'N/A')} on {p.get('milestone_date', 'N/A')}\n"
            result += f"  📊 Databook URL: {databook_url}\n"
    
    if ending:
        result += f"\n**Projects Ending (Next {days_forward} Days):** {len(ending)} projects\n\n"
        for p in ending:
            title, project_id, databook_url = format_project(p)
            result += f"- **{title[:55]}**\n"
            result += f"  Agency: {p.get('agency', 'N/A')} | Budget: {format_currency(p.get('budget'))}\n"
            result += f"  Scheduled End: {p.get('END_DATE', 'N/A')}\n"
            result += f"  📊 Databook URL: {databook_url}\n"
    
    if not (past_milestones or started or upcoming_milestones or ending):
        result += "No project milestones found in the specified date range.\n"
    
    return result.strip()


# ============================================================================
# People Search Tools
# ============================================================================

@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def search_people(query_text: str, limit: int = 20) -> str:
    """
    Search NYC government employees by name.
    
    Args:
        query_text: Name to search (first or last name)
        limit: Maximum results (default 20, max 50)
    
    Returns:
        List of matching employees with title and agency
    """
    limit = min(limit, 50)
    
    rows = await query(
        f"""
        SELECT "EMPLOYEE NAME" as name,
               "wegov-service-title-desc" as title,
               "wegov-org-name" as agency,
               {_num('"SALARY RATE"')} as salary
        FROM civillist
        WHERE "EMPLOYEE NAME" ILIKE $1
        ORDER BY "EMPLOYEE NAME"
        LIMIT $2
        """,
        f"%{query_text}%", limit
    )

    if not rows:
        return f"No employees found matching '{query_text}'"

    results = [f"**Found {len(rows)} employee(s) matching '{query_text}':**\n"]
    for r in rows:
        salary_info = f" - {format_currency(r['salary'])}" if r.get('salary') else ""
        results.append(
            f"- **{r['name']}**\n"
            f"  {r.get('title', 'N/A')} at {r.get('agency', 'N/A')}{salary_info}"
        )
    
    return "\n".join(results)


# ============================================================================
# Procurement - Vendor Tools
# ============================================================================

@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def search_vendors(query_text: str, limit: int = 20) -> str:
    """
    Search registered NYC vendors by name.
    
    Args:
        query_text: Vendor name to search (partial match)
        limit: Maximum results (default 20, max 50)
    
    Returns:
        List of matching vendors with basic info
    """
    limit = min(limit, 50)
    
    rows = await query(
        """
        SELECT "PASSPort Supplier-ID" AS passport_supplier_id,
               "Vendor Name" AS name,
               "Certification Type" AS certification_type,
               "Ethnicity" AS ethnicity,
               "Business Category" AS business_category
        FROM vendors
        WHERE "Vendor Name" ILIKE $1
        ORDER BY "Vendor Name"
        LIMIT $2
        """,
        f"%{query_text}%", limit
    )
    
    if not rows:
        return f"No vendors found matching '{query_text}'"
    
    results = [f"**Found {len(rows)} vendor(s) matching '{query_text}':**\n"]
    for r in rows:
        cert = f" [{r['certification_type']}]" if r.get('certification_type') else ""
        results.append(
            f"- **{r['name']}**{cert}\n"
            f"  ID: {r['passport_supplier_id']} | Category: {r.get('business_category', 'N/A')}"
        )
    
    return "\n".join(results)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_vendor_profile(vendor_id: str) -> str:
    """
    Get detailed profile for a specific vendor.
    
    Args:
        vendor_id: The vendor's passport_supplier_id (from search_vendors)
    
    Returns:
        Complete vendor profile with contract statistics
    """
    vendor = await query_one(
        """
        SELECT "PASSPort Supplier-ID" AS passport_supplier_id,
               "Vendor Name" AS name,
               "FMS Vendor Code" AS fms_vendor_code,
               "DUNS Number" AS duns_number,
               "Certification Type" AS certification_type,
               "Ethnicity" AS ethnicity,
               "Business Category" AS business_category,
               "Corporate Structure" AS corporate_structure
        FROM vendors WHERE "PASSPort Supplier-ID" = $1
        """,
        vendor_id
    )
    
    if not vendor:
        return f"Vendor with ID '{vendor_id}' not found"
    
    # Get contract stats
    contracts = await query(
        """
        SELECT contract_id, contract_title, award_amount, status, agency
        FROM contracts
        WHERE vendor_name = $1
        ORDER BY award_amount DESC NULLS LAST
        LIMIT 10
        """,
        vendor['name']
    )
    
    total_contracts = await query_one(
        "SELECT count(*) as c, SUM(award_amount) as total FROM contracts WHERE vendor_name = $1",
        vendor['name']
    )
    
    profile = f"""
**{vendor['name']}**

**Basic Info:**
- Vendor ID: {vendor['passport_supplier_id']}
- FMS Code: {vendor.get('fms_vendor_code', 'N/A')}
- DUNS: {vendor.get('duns_number', 'N/A')}

**Classification:**
- Certification: {vendor.get('certification_type', 'None')}
- Ethnicity: {vendor.get('ethnicity', 'N/A')}
- Business Category: {vendor.get('business_category', 'N/A')}
- Corporate Structure: {vendor.get('corporate_structure', 'N/A')}

**Contract Statistics:**
- Total Contracts: {total_contracts['c'] if total_contracts else 0}
- Total Awarded: {format_currency(total_contracts.get('total')) if total_contracts else 'N/A'}
"""
    
    if contracts:
        profile += "\n**Recent Contracts:**\n"
        for c in contracts[:5]:
            profile += f"- {c['contract_title'][:40]}... ({format_currency(c.get('award_amount'))}) - {c['status']}\n"
    
    return profile.strip()


# ============================================================================
# Procurement - Contract Tools
# ============================================================================

@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def search_contracts(
    query_text: Optional[str] = None,
    vendor: Optional[str] = None,
    agency: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20
) -> str:
    """
    Search NYC procurement contracts with various filters.
    
    Args:
        query_text: Search in contract title (optional)
        vendor: Filter by vendor name (partial match)
        agency: Filter by agency name (partial match)
        status: Filter by status (e.g., "Active", "Registered")
        limit: Maximum results (default 20, max 50)
    
    Returns:
        List of matching contracts
    """
    limit = min(limit, 50)
    
    conditions = []
    params = []
    param_idx = 1
    
    if query_text:
        conditions.append(f"contract_title ILIKE ${param_idx}")
        params.append(f"%{query_text}%")
        param_idx += 1
    
    if vendor:
        conditions.append(f"vendor_name ILIKE ${param_idx}")
        params.append(f"%{vendor}%")
        param_idx += 1
    
    if agency:
        conditions.append(f"agency ILIKE ${param_idx}")
        params.append(f"%{agency}%")
        param_idx += 1
    
    if status:
        conditions.append(f"status ILIKE ${param_idx}")
        params.append(f"%{status}%")
        param_idx += 1
    
    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    params.append(limit)
    
    rows = await query(
        f"""
        SELECT contract_id, ctr_id, epin, normalized_epin, agency_id,
               contract_title, vendor_name, agency, 
               award_amount, status, start_date, end_date
        FROM contracts
        {where_clause}
        ORDER BY award_amount DESC NULLS LAST
        LIMIT ${param_idx}
        """,
        *params
    )
    
    if not rows:
        return "No contracts found matching the criteria"
    
    results = [f"**Found {len(rows)} contract(s):**\n"]
    for r in rows:
        # Build ready-to-use Databook URL using ctr_id (preferred) or contract_id
        ctr_id = r.get('ctr_id') or r.get('contract_id')
        databook_url = f"https://databook.nyc/procurement/contract/{ctr_id}" if ctr_id else "N/A"
        
        results.append(
            f"- **{r['contract_title'][:50]}...**\n"
            f"  Vendor: {r['vendor_name'][:30]} | Agency: {r['agency']}\n"
            f"  Amount: {format_currency(r.get('award_amount'))} | Status: {r['status']}\n"
            f"  Start: {r.get('start_date', 'N/A')} | End: {r.get('end_date', 'N/A')}\n"
            f"  📊 Databook URL: {databook_url}"
        )
    
    return "\n".join(results)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_contract_details(contract_id: str) -> str:
    """
    Get detailed information for a specific contract.
    
    Args:
        contract_id: The contract ID (e.g., "CT1-100-2024")
    
    Returns:
        Full contract details
    """
    contract = await query_one(
        "SELECT * FROM contracts WHERE contract_id = $1",
        contract_id
    )
    
    if not contract:
        return f"Contract '{contract_id}' not found"
    
    details = f"""
**Contract: {contract['contract_id']}**

**{contract.get('contract_title', 'Untitled')}**

**Databook IDs (for joining records):**
- Contract ID: {contract.get('contract_id', 'N/A')}
- CTR ID: {contract.get('ctr_id', 'N/A')}
- EPIN: {contract.get('epin', 'N/A')}
- Normalized EPIN: {contract.get('normalized_epin', 'N/A')}
- Agency ID: {contract.get('agency_id', 'N/A')}
- Normalized Contract ID: {contract.get('normalized_contract_id', 'N/A')}

**Parties:**
- Agency: {contract.get('agency', 'N/A')}
- Vendor: {contract.get('vendor_name', 'N/A')}

**Financial:**
- Award Amount: {format_currency(contract.get('award_amount'))}
- Current Amount: {format_currency(contract.get('current_amount'))}

**Details:**
- Status: {contract.get('status', 'N/A')}
- Contract Type: {contract.get('contract_type', 'N/A')}
- Procurement Method: {contract.get('procurement_method', 'N/A')}
- Program: {contract.get('program', 'N/A')}
- Industry: {contract.get('industry', 'N/A')}

**Timeline:**
- Start Date: {contract.get('start_date', 'N/A')}
- End Date: {contract.get('end_date', 'N/A')}
"""
    
    return details.strip()


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_contract_stats(
    agency: Optional[str] = None,
    fiscal_year: Optional[int] = None
) -> str:
    """
    Get aggregated contract statistics for analysis.
    
    Useful for understanding overall procurement activity, budget allocation,
    and contract distribution across agencies.
    
    Args:
        agency: Filter by agency name (optional)
        fiscal_year: Filter by fiscal year (optional)
    
    Returns:
        Summary statistics including counts, totals, and breakdowns
    """
    conditions = []
    params = []
    param_idx = 1
    
    if agency:
        conditions.append(f"agency ILIKE ${param_idx}")
        params.append(f"%{agency}%")
        param_idx += 1
    
    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    
    # Overall stats
    stats = await query_one(
        f"""
        SELECT COUNT(*) as count,
               SUM(award_amount) as total,
               AVG(award_amount) as avg,
               MIN(award_amount) as min,
               MAX(award_amount) as max
        FROM contracts
        {where_clause}
        """,
        *params
    )
    
    # By status
    status_rows = await query(
        f"""
        SELECT status, COUNT(*) as count, SUM(award_amount) as total
        FROM contracts
        {where_clause}
        GROUP BY status
        ORDER BY total DESC NULLS LAST
        """,
        *params
    )
    
    title = agency if agency else "All Agencies"
    
    result = f"""
**Contract Statistics: {title}**

**Summary:**
- Total Contracts: {stats['count'] if stats else 0:,}
- Total Value: {format_currency(stats.get('total')) if stats else 'N/A'}
- Average Contract: {format_currency(stats.get('avg')) if stats else 'N/A'}

**By Status:**
"""
    
    for s in status_rows:
        result += f"- {s['status']}: {s['count']:,} contracts ({format_currency(s.get('total'))})\n"
    
    # Top agencies if no agency filter
    if not agency:
        top_agencies = await query(
            """
            SELECT agency, COUNT(*) as count, SUM(award_amount) as total
            FROM contracts
            GROUP BY agency
            ORDER BY total DESC NULLS LAST
            LIMIT 10
            """
        )
        result += "\n**Top Agencies by Contract Value:**\n"
        for a in top_agencies:
            result += f"- {a['agency']}: {a['count']:,} contracts ({format_currency(a.get('total'))})\n"
    
    return result.strip()


# ============================================================================
# Procurement - Solicitation Tools
# ============================================================================

@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def search_solicitations(
    query_text: Optional[str] = None,
    agency: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20
) -> str:
    """
    Search NYC procurement solicitations (RFPs, bids).
    
    Args:
        query_text: Search in procurement name (optional)
        agency: Filter by agency name (partial match)
        status: Filter by status (e.g., "Open", "Closed")
        limit: Maximum results (default 20, max 50)
    
    Returns:
        List of matching solicitations
    """
    limit = min(limit, 50)
    
    conditions = []
    params = []
    param_idx = 1
    
    if query_text:
        conditions.append(f""""Procurement Name" ILIKE ${param_idx}""")
        params.append(f"%{query_text}%")
        param_idx += 1
    
    if agency:
        conditions.append(f""""Agency" ILIKE ${param_idx}""")
        params.append(f"%{agency}%")
        param_idx += 1
    
    if status:
        conditions.append(f""""RFx Status" ILIKE ${param_idx}""")
        params.append(f"%{status}%")
        param_idx += 1
    
    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    params.append(limit)
    
    rows = await query(
        f"""
        SELECT *
        FROM solicitations
        {where_clause}
        ORDER BY "Release Date" DESC NULLS LAST
        LIMIT ${param_idx}
        """,
        *params
    )
    
    if not rows:
        return "No solicitations found matching the criteria"
    
    # Cross-reference with CROL to find City Record notice links
    epins = [r.get('EPIN', '') for r in rows if r.get('EPIN')]
    crol_map = {}
    if epins:
        epin_conditions = []
        epin_params = []
        for i, epin in enumerate(epins):
            epin_conditions.append(f'"ShortTitle" ILIKE ${i + 1}')
            epin_params.append(f"%{epin}%")
        
        crol_rows = await query(
            f"""
            SELECT "RequestID", "ShortTitle"
            FROM crol
            WHERE {" OR ".join(epin_conditions)}
            ORDER BY start_date_parsed DESC
            """,
            *epin_params
        )
        
        for cr in crol_rows:
            title = cr.get('ShortTitle', '')
            for epin in epins:
                if epin in title and epin not in crol_map:
                    crol_map[epin] = cr['RequestID']
    
    results = [f"**Found {len(rows)} solicitation(s):**\n"]
    for r in rows:
        epin = r.get('EPIN', '')
        ids = f"epin={epin}"
        if r.get('RFP-ID'):
            ids += f", rfp_id={r['RFP-ID']}"
        if r.get('BPM-ID'):
            ids += f", bpm_id={r['BPM-ID']}"
        if r.get('wegov-org-id'):
            ids += f", agency_id={r['wegov-org-id']}"
        
        databook_url = f"https://databook.nyc/procurement/solicitation/{epin}" if epin else "N/A"
        crol_request_id = crol_map.get(epin) if epin else None
        crol_url = f"https://a856-cityrecord.nyc.gov/RequestDetail/{crol_request_id}" if crol_request_id else "N/A"
        
        pname = r.get('Procurement Name', 'Unknown')
        results.append(
            f"- **{pname[:50]}...**\n"
            f"  IDs: [{ids}]\n"
            f"  Agency: {r.get('Agency', 'N/A')} | Status: {r.get('RFx Status', 'N/A')}\n"
            f"  Due: {r.get('Due Date', 'N/A')} | Method: {r.get('Procurement Method', 'N/A')}\n"
            f"  📊 Databook URL: {databook_url}\n"
            f"  📄 City Record: {crol_url}"
        )
    
    return "\n".join(results)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_solicitation_details(epin: str) -> str:
    """
    Get detailed information for a specific solicitation.
    
    Args:
        epin: The solicitation EPIN
    
    Returns:
        Full solicitation details with related contracts
    """
    solicitation = await query_one(
        """SELECT * FROM solicitations WHERE "EPIN" = $1""",
        epin
    )
    
    if not solicitation:
        return f"Solicitation with EPIN '{epin}' not found"
    
    # Check for resulting contracts
    contracts = await query(
        """
        SELECT contract_id, contract_title, vendor_name, award_amount, status
        FROM contracts
        WHERE epin = $1 OR epin LIKE $2
        LIMIT 10
        """,
        solicitation.get('EPIN', ''), f"%{epin}%"
    )
    
    details = f"""
**Solicitation: {solicitation.get('EPIN', 'N/A')}**

**{solicitation.get('Procurement Name', 'Untitled')}**

**Details:**
- Agency: {solicitation.get('Agency', 'N/A')}
- Status: {solicitation.get('RFx Status', 'N/A')}
- Procurement Method: {solicitation.get('Procurement Method', 'N/A')}
- Industry: {solicitation.get('Industry', 'N/A')}
- Main Commodity: {solicitation.get('Main Commodity', 'N/A')}

**Timeline:**
- Release Date: {solicitation.get('Release Date', 'N/A')}
- Due Date: {solicitation.get('Due Date', 'N/A')}

**Databook IDs (for joining records):**
- EPIN: {solicitation.get('EPIN', 'N/A')}
- RFP ID: {solicitation.get('RFP-ID', 'N/A')}
- BPM ID: {solicitation.get('BPM-ID', 'N/A')}
- Agency ID: {solicitation.get('wegov-org-id', 'N/A')}
"""
    
    if contracts:
        details += "\n**Resulting Contracts:**\n"
        for c in contracts:
            details += f"- {c['contract_id']}: {c['vendor_name'][:30]} ({format_currency(c.get('award_amount'))}) - {c['status']}\n"
    
    return details.strip()


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_open_solicitations(limit: int = 20) -> str:
    """
    Get currently open solicitations (upcoming due dates).
    
    Args:
        limit: Maximum results (default 20, max 50)
    
    Returns:
        List of open solicitations sorted by due date, with Databook and City Record links
    """
    limit = min(limit, 50)
    
    rows = await query(
        """
        SELECT *
        FROM solicitations
        WHERE "RFx Status" ILIKE '%open%' OR "RFx Status" ILIKE '%active%'
        ORDER BY "Due Date" ASC NULLS LAST
        LIMIT $1
        """,
        limit
    )
    
    if not rows:
        return "No open solicitations found"
    
    # Cross-reference with CROL to find City Record notice links
    epins = [r.get('EPIN', '') for r in rows if r.get('EPIN')]
    crol_map = {}
    if epins:
        # Build OR conditions to search CROL for notices mentioning any EPIN
        epin_conditions = []
        epin_params = []
        for i, epin in enumerate(epins):
            epin_conditions.append(f'"ShortTitle" ILIKE ${i + 1}')
            epin_params.append(f"%{epin}%")
        
        crol_rows = await query(
            f"""
            SELECT "RequestID", "ShortTitle"
            FROM crol
            WHERE {" OR ".join(epin_conditions)}
            ORDER BY start_date_parsed DESC
            """,
            *epin_params
        )
        
        # Map each EPIN to its CROL RequestID
        for cr in crol_rows:
            title = cr.get('ShortTitle', '')
            for epin in epins:
                if epin in title and epin not in crol_map:
                    crol_map[epin] = cr['RequestID']
    
    results = [f"**Open Solicitations ({len(rows)} shown):**\n"]
    for r in rows:
        epin = r.get('EPIN', '')
        databook_url = f"https://databook.nyc/procurement/solicitation/{epin}" if epin else "N/A"
        crol_request_id = crol_map.get(epin) if epin else None
        crol_url = f"https://a856-cityrecord.nyc.gov/RequestDetail/{crol_request_id}" if crol_request_id else "N/A"
        
        pname = r.get('Procurement Name', 'Unknown')
        results.append(
            f"- **{pname[:50]}...**\n"
            f"  Agency: {r.get('Agency', 'N/A')} | Method: {r.get('Procurement Method', 'N/A')}\n"
            f"  Due: {r.get('Due Date', 'N/A')} | Status: {r.get('RFx Status', 'N/A')}\n"
            f"  📊 Databook URL: {databook_url}\n"
            f"  📄 City Record: {crol_url}"
        )
    
    return "\n".join(results)


# ============================================================================
# NYC Jobs Tools
# ============================================================================

@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def search_jobs(
    query_text: Optional[str] = None,
    agency: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 20
) -> str:
    """
    Search NYC government job postings.
    
    Args:
        query_text: Search in job title or description (optional)
        agency: Filter by agency name (partial match)
        category: Filter by job category (e.g., "Engineering", "Legal")
        limit: Maximum results (default 20, max 50)
    
    Returns:
        List of matching job postings with salary info
    """
    limit = min(limit, 50)
    
    conditions = []
    params = []
    param_idx = 1
    
    if query_text:
        conditions.append(f"""("Business Title" ILIKE ${param_idx} OR "Job Description" ILIKE ${param_idx})""")
        params.append(f"%{query_text}%")
        param_idx += 1
    
    if agency:
        conditions.append(f""""Agency" ILIKE ${param_idx}""")
        params.append(f"%{agency}%")
        param_idx += 1
    
    if category:
        conditions.append(f""""Job Category" ILIKE ${param_idx}""")
        params.append(f"%{category}%")
        param_idx += 1
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    sql = f"""
        SELECT "Job ID", "Agency", "Business Title", "Civil Service Title",
               "Salary Range From", "Salary Range To", "Salary Frequency",
               "Job Category", "Career Level", "Work Location", "Posting Date"
        FROM nycjobs
        WHERE {where_clause}
        ORDER BY "Posting Date" DESC
        LIMIT ${param_idx}
    """
    params.append(limit)
    
    rows = await query(sql, *params)
    
    if not rows:
        return "No job postings found matching your criteria."
    
    results = [f"Found {len(rows)} job postings:\n"]
    for r in rows:
        salary_low = format_currency(r.get('Salary Range From', 0))
        salary_high = format_currency(r.get('Salary Range To', 0))
        results.append(
            f"- **{r['Business Title']}** [ID: {r['Job ID']}]\n"
            f"  Agency: {r['Agency']}\n"
            f"  Salary: {salary_low} - {salary_high} ({r.get('Salary Frequency', 'Annual')})\n"
            f"  Category: {r.get('Job Category', 'N/A')} | Level: {r.get('Career Level', 'N/A')}"
        )
    
    return "\n".join(results)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_job_details(job_id: str) -> str:
    """
    Get detailed information for a specific job posting.

    Args:
        job_id: The job ID (e.g., "784250" from search_jobs)
    
    Returns:
        Full job posting details including requirements and how to apply
    """
    sql = """
        SELECT * FROM nycjobs WHERE "Job ID" = $1
    """
    row = await query_one(sql, job_id)
    
    if not row:
        return f"Job posting {job_id} not found."
    
    salary_low = format_currency(row.get('Salary Range From', 0))
    salary_high = format_currency(row.get('Salary Range To', 0))
    
    return f"""# {row['Business Title']}

**Agency:** {row['Agency']}
**Job ID:** {row['Job ID']}
**Posting Date:** {row.get('Posting Date', 'N/A')}
**Post Until:** {row.get('Post Until', 'N/A')}

## Position Details
- **Civil Service Title:** {row.get('Civil Service Title', 'N/A')}
- **Title Code:** {row.get('Title Code No', 'N/A')}
- **Job Category:** {row.get('Job Category', 'N/A')}
- **Career Level:** {row.get('Career Level', 'N/A')}
- **Full/Part Time:** {row.get('Full-Time/Part-Time indicator', 'N/A')}
- **Work Location:** {row.get('Work Location', 'N/A')}

## Salary
**{salary_low} - {salary_high}** ({row.get('Salary Frequency', 'Annual')})

## Job Description
{(row.get('Job Description') or 'N/A')[:1500]}

## Minimum Qualifications
{(row.get('Minimum Qual Requirements') or 'N/A')[:1000]}

## Preferred Skills
{(row.get('Preferred Skills') or 'N/A')[:500]}

## How to Apply
{row.get('To Apply', 'N/A')}

## Residency Requirement
{row.get('Residency Requirement', 'N/A')}
"""


# ============================================================================
# Payroll/Salary Tools
# ============================================================================

@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_salary_stats(
    agency: Optional[str] = None,
    title: Optional[str] = None,
    fiscal_year: Optional[int] = None
) -> str:
    """
    Get salary statistics for NYC government employees.
    
    Args:
        agency: Filter by agency name (partial match, optional)
        title: Filter by job title (partial match, optional)
        fiscal_year: Filter by fiscal year (e.g., 2024, optional)
    
    Returns:
        Salary statistics including averages, ranges, and totals
    """
    conditions = []
    params = []
    param_idx = 1
    
    if agency:
        conditions.append(f""""Agency Name" ILIKE ${param_idx}""")
        params.append(f"%{agency}%")
        param_idx += 1
    
    if title:
        conditions.append(f""""Title Description" ILIKE ${param_idx}""")
        params.append(f"%{title}%")
        param_idx += 1
    
    if fiscal_year:
        conditions.append(f""""Fiscal Year" = ${param_idx}""")
        params.append(fiscal_year)
        param_idx += 1
    else:
        # Default to most recent fiscal year
        conditions.append(""""Fiscal Year" = (SELECT MAX("Fiscal Year") FROM payrolldata)""")
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    sql = f"""
        SELECT
            COUNT(*) as employee_count,
            AVG({_num('"Base Salary"')}) as avg_salary,
            MIN({_num('"Base Salary"')}) as min_salary,
            MAX({_num('"Base Salary"')}) as max_salary,
            SUM({_num('"Regular Gross Paid"')}) as total_regular_pay,
            SUM({_num('"Total OT Paid"')}) as total_ot_pay,
            AVG({_num('"OT Hours"')}) as avg_ot_hours,
            MAX("Fiscal Year") as fiscal_year
        FROM payrolldata
        WHERE {where_clause} AND {_num('"Base Salary"')} > 0
    """
    
    row = await query_one(sql, *params)
    
    if not row or row['employee_count'] == 0:
        return "No payroll data found matching your criteria."
    
    return f"""# Payroll Statistics (FY{row['fiscal_year']})

**Employees:** {row['employee_count']:,}

## Base Salary
- Average: {format_currency(row['avg_salary'])}
- Range: {format_currency(row['min_salary'])} - {format_currency(row['max_salary'])}

## Compensation Totals
- Total Regular Pay: {format_currency(row['total_regular_pay'])}
- Total Overtime Pay: {format_currency(row['total_ot_pay'])}
- Average OT Hours: {(float(row['avg_ot_hours']) if row.get('avg_ot_hours') is not None else 0):.1f} hours/year
"""


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_top_salaries(
    agency: Optional[str] = None,
    fiscal_year: Optional[int] = None,
    limit: int = 20
) -> str:
    """
    Get highest paid NYC government employees.
    
    Args:
        agency: Filter by agency name (optional)
        fiscal_year: Fiscal year (defaults to most recent)
        limit: Maximum results (default 20, max 50)
    
    Returns:
        List of highest paid employees with salary details
    """
    limit = min(limit, 50)
    
    base_salary_num = _num('"Base Salary"')
    ot_paid_num = _num('"Total OT Paid"')

    conditions = [f"{base_salary_num} > 0"]
    params = []
    param_idx = 1

    if agency:
        conditions.append(f""""Agency Name" ILIKE ${param_idx}""")
        params.append(f"%{agency}%")
        param_idx += 1

    if fiscal_year:
        conditions.append(f""""Fiscal Year" = ${param_idx}""")
        params.append(fiscal_year)
        param_idx += 1
    else:
        conditions.append(""""Fiscal Year" = (SELECT MAX("Fiscal Year") FROM payrolldata)""")

    where_clause = " AND ".join(conditions)

    sql = f"""
        SELECT "First Name", "Last Name", "Title Description",
               "Agency Name", {base_salary_num} as base_salary,
               {ot_paid_num} as total_ot, "Fiscal Year"
        FROM payrolldata
        WHERE {where_clause}
        ORDER BY base_salary DESC NULLS LAST
        LIMIT ${param_idx}
    """
    params.append(limit)

    rows = await query(sql, *params)

    if not rows:
        return "No payroll data found."

    fy = rows[0]['Fiscal Year']
    results = [f"# Top {len(rows)} Salaries (FY{fy})\n"]

    for i, r in enumerate(rows, 1):
        base = r.get('base_salary') or 0
        ot = r.get('total_ot') or 0
        total_comp = base + ot
        results.append(
            f"{i}. **{r['First Name']} {r['Last Name']}** - {format_currency(base)}\n"
            f"   {r['Title Description']}\n"
            f"   {r['Agency Name']}\n"
            f"   (+ {format_currency(ot)} OT = {format_currency(total_comp)} total)"
        )
    
    return "\n".join(results)


# ============================================================================
# City Facilities Tools
# ============================================================================

@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def search_facilities(
    query_text: Optional[str] = None,
    facility_type: Optional[str] = None,
    borough: Optional[str] = None,
    limit: int = 25
) -> str:
    """
    Search NYC city facilities (buildings, parks, offices).
    
    Args:
        query_text: Search facility name (optional)
        facility_type: Filter by type (e.g., "School", "Library", "Police Station")
        borough: Filter by borough (Manhattan, Brooklyn, Queens, Bronx, Staten Island)
        limit: Maximum results (default 25, max 50)
    
    Returns:
        List of matching facilities with addresses
    """
    limit = min(limit, 50)
    
    conditions = []
    params = []
    param_idx = 1
    
    if query_text:
        conditions.append(f"""facname ILIKE ${param_idx}""")
        params.append(f"%{query_text}%")
        param_idx += 1
    
    if facility_type:
        conditions.append(f"""(factype ILIKE ${param_idx} OR facsubgrp ILIKE ${param_idx})""")
        params.append(f"%{facility_type}%")
        param_idx += 1
    
    if borough:
        conditions.append(f"""boro ILIKE ${param_idx}""")
        params.append(f"%{borough}%")
        param_idx += 1
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    sql = f"""
        SELECT uid, facname, address, boro, zipcode, facgroup, facsubgrp, 
               factype, latitude, longitude, optype
        FROM facilitydb
        WHERE {where_clause}
        ORDER BY facname
        LIMIT ${param_idx}
    """
    params.append(limit)
    
    rows = await query(sql, *params)
    
    if not rows:
        return "No facilities found matching your criteria."
    
    results = [f"Found {len(rows)} facilities:\n"]
    for r in rows:
        coords = ""
        if r.get('latitude') and r.get('longitude'):
            try:
                coords = f"({float(r['latitude']):.4f}, {float(r['longitude']):.4f})"
            except (ValueError, TypeError):
                coords = ""
        results.append(
            f"- **{r['facname']}** [{r['factype']}]\n"
            f"  {r['address']}, {r['boro']} {r['zipcode']}\n"
            f"  Group: {r['facgroup']} > {r['facsubgrp']} {coords}"
        )
    
    return "\n".join(results)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_facility_types() -> str:
    """
    Get list of all facility types and their counts.
    
    Returns:
        Breakdown of facility types across NYC
    """
    sql = """
        SELECT facgroup, facsubgrp, factype, COUNT(*) as count
        FROM facilitydb
        GROUP BY facgroup, facsubgrp, factype
        ORDER BY count DESC
        LIMIT 50
    """
    rows = await query(sql)
    
    results = ["# NYC Facility Types\n"]
    current_group = None
    
    for r in rows:
        if r['facgroup'] != current_group:
            current_group = r['facgroup']
            results.append(f"\n## {current_group}")
        results.append(f"- {r['facsubgrp']} > {r['factype']}: {r['count']:,}")
    
    return "\n".join(results)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def search_schools(
    query_text: Optional[str] = None,
    school_type: Optional[str] = None,
    borough: Optional[str] = None,
    limit: int = 25
) -> str:
    """
    Search NYC schools (public, charter, private, after-school programs).
    
    Args:
        query_text: Search school name (optional)
        school_type: Filter by type (e.g., "elementary", "high school", "charter", "after-school")
        borough: Filter by borough (Manhattan, Brooklyn, Queens, Bronx, Staten Island)
        limit: Maximum results (default 25, max 50)
    
    Returns:
        List of matching schools with addresses and details
    """
    limit = min(limit, 50)
    
    conditions = ["(facgroup ILIKE '%education%' OR facsubgrp ILIKE '%school%')"]
    params = []
    param_idx = 1
    
    if query_text:
        conditions.append(f"""facname ILIKE ${param_idx}""")
        params.append(f"%{query_text}%")
        param_idx += 1
    
    if school_type:
        conditions.append(f"""(factype ILIKE ${param_idx} OR facsubgrp ILIKE ${param_idx})""")
        params.append(f"%{school_type}%")
        param_idx += 1
    
    if borough:
        conditions.append(f"""boro ILIKE ${param_idx}""")
        params.append(f"%{borough}%")
        param_idx += 1
    
    where_clause = " AND ".join(conditions)
    
    sql = f"""
        SELECT uid, facname, address, boro, zipcode, facsubgrp, 
               factype, latitude, longitude
        FROM facilitydb
        WHERE {where_clause}
        ORDER BY facname
        LIMIT ${param_idx}
    """
    params.append(limit)
    
    rows = await query(sql, *params)
    
    if not rows:
        return "No schools found matching your criteria."
    
    results = [f"Found {len(rows)} schools:\n"]
    for r in rows:
        coords = ""
        if r.get('latitude') and r.get('longitude'):
            try:
                coords = f"({float(r['latitude']):.4f}, {float(r['longitude']):.4f})"
            except (ValueError, TypeError):
                coords = ""
        results.append(
            f"- **{r['facname']}** [{r['factype']}]\n"
            f"  {r['address']}, {r['boro']} {r['zipcode']}\n"
            f"  Category: {r['facsubgrp']} {coords}"
        )
    
    return "\n".join(results)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_school_stats() -> str:
    """
    Get overview of NYC schools by type and borough.
    
    Returns:
        Breakdown of school counts by category and location
    """
    sql = """
        SELECT boro, facsubgrp, COUNT(*) as count
        FROM facilitydb
        WHERE facgroup ILIKE '%education%' OR facsubgrp ILIKE '%school%'
        GROUP BY boro, facsubgrp
        ORDER BY boro, count DESC
    """
    rows = await query(sql)
    
    # Get totals
    total_sql = """
        SELECT COUNT(*) as total FROM facilitydb
        WHERE facgroup ILIKE '%education%' OR facsubgrp ILIKE '%school%'
    """
    total = await query_one(total_sql)
    
    results = [f"# NYC Schools Overview\n\n**Total: {total['total']:,} education facilities**\n"]
    
    current_boro = None
    for r in rows:
        if r['boro'] != current_boro:
            current_boro = r['boro']
            results.append(f"\n## {current_boro.strip()}")
        results.append(f"- {r['facsubgrp']}: {r['count']:,}")
    
    return "\n".join(results)


# ============================================================================
# Budget Tools  
# ============================================================================

@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_agency_budget(
    agency: str,
    fiscal_year: Optional[int] = None
) -> str:
    """
    Get budget breakdown for a specific agency.
    
    Args:
        agency: Agency name (partial match)
        fiscal_year: Fiscal year (defaults to most recent)
    
    Returns:
        Budget details by category with adopted vs modified amounts
    """
    conditions = [f""""Agency Name" ILIKE $1"""]
    params = [f"%{agency}%"]
    
    if fiscal_year:
        conditions.append(f""""Fiscal Year" = $2""")
        params.append(fiscal_year)
    else:
        conditions.append(""""Fiscal Year" = (SELECT MAX("Fiscal Year") FROM expensebudgetonnycopendata)""")
    
    where_clause = " AND ".join(conditions)

    adopted_num = _num('"Adopted Budget Amount"')
    modified_num = _num('"Current Modified Budget Amount"')
    planned_num = _num('"Financial Plan Amount"')

    # Summary by object class
    sql = f"""
        SELECT
            "Agency Name",
            "Fiscal Year",
            "Object Class Name",
            SUM({adopted_num}) as adopted,
            SUM({modified_num}) as modified,
            SUM({planned_num}) as planned
        FROM expensebudgetonnycopendata
        WHERE {where_clause}
        GROUP BY "Agency Name", "Fiscal Year", "Object Class Name"
        ORDER BY modified DESC NULLS LAST
        LIMIT 20
    """
    
    rows = await query(sql, *params)
    
    if not rows:
        return f"No budget data found for agency matching '{agency}'."
    
    agency_name = rows[0]['Agency Name']
    fy = rows[0]['Fiscal Year']
    
    # Also get totals
    totals_sql = f"""
        SELECT
            SUM({adopted_num}) as total_adopted,
            SUM({modified_num}) as total_modified
        FROM expensebudgetonnycopendata
        WHERE {where_clause}
    """
    totals = await query_one(totals_sql, *params)
    
    results = [f"# {agency_name} Budget (FY{fy})\n"]
    results.append(f"**Total Adopted:** {format_currency(totals['total_adopted'])}")
    results.append(f"**Total Modified:** {format_currency(totals['total_modified'])}\n")
    results.append("## By Category")
    
    for r in rows:
        mod = r['modified'] or 0
        adp = r['adopted'] or 0
        if mod > 0:
            change = ((mod - adp) / adp * 100) if adp else 0
            change_str = f"({change:+.1f}%)" if change != 0 else ""
            results.append(
                f"- **{r['Object Class Name']}**\n"
                f"  Adopted: {format_currency(adp)} -> "
                f"Modified: {format_currency(mod)} {change_str}"
            )
    
    return "\n".join(results)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def compare_agency_budgets(
    fiscal_year: Optional[int] = None,
    limit: int = 20
) -> str:
    """
    Compare budgets across NYC agencies.
    
    Args:
        fiscal_year: Fiscal year (defaults to most recent)
        limit: Number of agencies to show (default 20)
    
    Returns:
        Top agencies by budget with year-over-year comparison
    """
    limit = min(limit, 50)
    
    if fiscal_year:
        fy_condition = f""""Fiscal Year" = ${1}"""
        params = [fiscal_year, limit]
    else:
        fy_condition = """"Fiscal Year" = (SELECT MAX("Fiscal Year") FROM expensebudgetonnycopendata)"""
        params = [limit]
    
    adopted_num = _num('"Adopted Budget Amount"')
    modified_num = _num('"Current Modified Budget Amount"')

    sql = f"""
        SELECT
            "Agency Name",
            "Fiscal Year",
            SUM({adopted_num}) as adopted,
            SUM({modified_num}) as modified
        FROM expensebudgetonnycopendata
        WHERE {fy_condition}
        GROUP BY "Agency Name", "Fiscal Year"
        ORDER BY modified DESC NULLS LAST
        LIMIT ${len(params)}
    """
    
    rows = await query(sql, *params)
    
    if not rows:
        return "No budget data available."
    
    fy = rows[0]['Fiscal Year']
    total_budget = sum((r['modified'] or 0) for r in rows)

    results = [f"# NYC Agency Budgets (FY{fy})\n"]
    results.append(f"**Total (Top {len(rows)} agencies):** {format_currency(total_budget)}\n")

    for i, r in enumerate(rows, 1):
        mod = r['modified'] or 0
        pct = (mod / total_budget * 100) if total_budget else 0
        results.append(
            f"{i}. **{r['Agency Name']}**: {format_currency(mod)} ({pct:.1f}%)"
        )
    
    return "\n".join(results)


# ============================================================================
# Prompts - Reusable templates for common analysis patterns
# ============================================================================

@mcp.prompt()
def analyze_agency(agency_name: str) -> str:
    """Generate a comprehensive analysis request for a NYC agency."""
    return f"""Please provide a comprehensive analysis of the {agency_name}:

1. Search for the organization and get its profile
2. Find recent City Record notices related to this agency
3. Search for capital projects they're managing
4. Look up their procurement contracts and solicitations
5. Check their budget allocation
6. Summarize key findings about budget, staffing, and current initiatives"""


@mcp.prompt()
def procurement_research(vendor_or_topic: str) -> str:
    """Research NYC procurement activity for a vendor or topic."""
    return f"""Research NYC procurement for "{vendor_or_topic}":

1. Search for relevant vendors and contracts
2. Look up open solicitations matching this topic
3. Get contract statistics by agency
4. Identify key spending patterns and trends"""


@mcp.prompt()  
def explore_database() -> str:
    """Get an overview of available NYC government data."""
    return """Help me understand what data is available in the NYC Government Databook:

1. Get the database overview to see all available data categories
2. Explain the key entities: organizations, people, contracts, capital projects
3. Show me some example searches I can do
4. Highlight any interesting statistics or trends"""


@mcp.prompt()
def job_search(criteria: str) -> str:
    """Search for NYC government job opportunities."""
    return f"""Search for NYC government jobs matching: "{criteria}"

1. Search available job postings
2. Show salary ranges and requirements
3. Identify which agencies are hiring for these roles
4. List any related civil service titles"""


# ============================================================================
# NYC Council Legislation Tools (intro.nyc)
# ============================================================================

# TTL cache for intro.nyc HTTP responses (5-minute expiry, 200 items max)
_legislation_cache = TTLCache(maxsize=200, ttl=300)


async def _fetch_json(url: str) -> dict | list | None:
    """Fetch JSON from a URL with TTL caching to reduce load on intro.nyc."""
    if url in _legislation_cache:
        logger.info(f"CACHE HIT: {url}")
        return _legislation_cache[url]

    logger.info(f"HTTP FETCH: {url}")
    headers = {"User-Agent": "DatabookNYC-MCP/1.0"}

    for ssl_mode in [None, False]:  # Try verified first, then unverified (macOS dev)
        try:
            connector = aiohttp.TCPConnector(ssl=ssl_mode) if ssl_mode is False else None
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 404:
                        return None
                    resp.raise_for_status()
                    data = await resp.json(content_type=None)
                    _legislation_cache[url] = data
                    return data
        except aiohttp.ClientConnectorCertificateError:
            if ssl_mode is None:
                logger.warning(f"SSL verification failed for {url}, retrying without verification")
                continue
            return None
        except Exception as e:
            logger.error(f"HTTP FETCH ERROR ({url}): {e}")
            return None


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def search_legislation(
    query_text: str,
    year: int = 2024,
    status: Optional[str] = None,
    limit: int = 20
) -> str:
    """
    Search NYC Council legislation (introductions) by keyword.

    Searches bill titles and names from the NYC Council for a given year.
    Data sourced from intro.nyc / jehiah/nyc_legislation.

    Args:
        query_text: Keyword to search in bill title/name
        year: Legislative year to search (default 2024)
        status: Filter by status (e.g., "Enacted", "Committee", "Approved"). Optional.
        limit: Maximum results (default 20, max 50)

    Returns:
        List of matching bills with status and sponsor info
    """
    limit = min(limit, 50)

    # Fetch the year's resubmit/index data to get bill numbers
    # Try the GitHub raw listing of introduction files
    url = f"https://api.github.com/repos/jehiah/nyc_legislation/contents/introduction/{year}"
    entries = await _fetch_json(url)

    if not entries or not isinstance(entries, list):
        return f"No legislation data found for year {year}"

    # Filter to .json files and extract bill numbers
    bill_files = [e["name"].replace(".json", "") for e in entries if e.get("name", "").endswith(".json")]

    # Search through bills - fetch a subset to find matches
    results = []
    query_lower = query_text.lower()
    checked = 0

    for bill_num in bill_files:
        if len(results) >= limit:
            break

        bill_url = f"https://intro.nyc/{bill_num}-{year}.json"
        bill = await _fetch_json(bill_url)
        if not bill:
            continue
        checked += 1

        title = (bill.get("Title") or bill.get("Name") or "").lower()
        if query_lower not in title:
            continue

        if status and status.lower() not in (bill.get("StatusName") or "").lower():
            continue

        sponsors = bill.get("Sponsors", [])
        sponsor_str = ", ".join(s.get("FullName", "") for s in sponsors[:3])
        if len(sponsors) > 3:
            sponsor_str += f" +{len(sponsors)-3} more"

        results.append(
            f"- **Int {bill_num}-{year}**: {bill.get('Title', 'Untitled')[:80]}\n"
            f"  Status: {bill.get('StatusName', 'Unknown')} | "
            f"Sponsors: {sponsor_str}\n"
            f"  [View on intro.nyc](https://intro.nyc/{bill_num}-{year})"
        )

        # Avoid hammering the API - stop after checking 100 bills
        if checked >= 100:
            break

    if not results:
        return f"No legislation matching '{query_text}' found in {year} (checked {checked} bills)"

    header = f"**Found {len(results)} bill(s) matching '{query_text}' in {year}:**\n"
    return header + "\n".join(results)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_legislation_detail(intro_number: str, year: int = 2024) -> str:
    """
    Get full details for a specific NYC Council bill.

    Returns sponsors, status, legislative history, vote records, and bill text.
    Data sourced from intro.nyc.

    Args:
        intro_number: The introduction number (e.g., "0001", "1234")
        year: The legislative year (e.g., 2024)

    Returns:
        Complete bill details with sponsors, history, and text summary
    """
    url = f"https://intro.nyc/{intro_number}-{year}.json"
    bill = await _fetch_json(url)

    if not bill:
        return f"Bill Int {intro_number}-{year} not found"

    # Format sponsors
    sponsors = bill.get("Sponsors", [])
    sponsor_list = "\n".join(f"  - {s.get('FullName', 'Unknown')}" for s in sponsors)

    # Format history (last 5 events)
    history = bill.get("History", [])
    history_list = ""
    for h in history[-5:]:
        date = h.get("Date", "")[:10]
        action = h.get("Action", "")
        body = h.get("BodyName", "")
        history_list += f"  - **{date}**: {action} ({body})\n"

    # Format vote summary (from most recent vote event)
    vote_summary = ""
    for h in reversed(history):
        if h.get("Votes"):
            votes = h["Votes"]
            aff = sum(1 for v in votes if v.get("Vote") == "Affirmative")
            neg = sum(1 for v in votes if v.get("Vote") == "Negative")
            absent = sum(1 for v in votes if v.get("Vote") in ("Absent", "Medical", "Parental"))
            vote_summary = f"\n**Most Recent Vote** ({h.get('Date', '')[:10]}, {h.get('BodyName', '')}): "
            vote_summary += f"{aff} Yes / {neg} No / {absent} Absent\n"
            break

    # Build result
    local_law = f" → Local Law {bill['LocalLaw']}" if bill.get("LocalLaw") else ""
    summary = bill.get("Summary", "") or bill.get("Name", "")

    result = f"""
**Int {bill.get('File', f'{intro_number}-{year}')}**{local_law}

**{bill.get('Title', 'Untitled')}**

Status: **{bill.get('StatusName', 'Unknown')}**
Committee: {bill.get('BodyName', 'N/A')}
Introduced: {(bill.get('IntroDate') or '')[:10]}
Passed: {(bill.get('PassedDate') or 'N/A')[:10] if bill.get('PassedDate') else 'N/A'}

**Summary:** {summary[:300]}

**Sponsors ({len(sponsors)}):**
{sponsor_list}
{vote_summary}
**Legislative History (recent):**
{history_list}
[View on intro.nyc](https://intro.nyc/{intro_number}-{year})
"""
    return result.strip()


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_council_member(slug: str) -> str:
    """
    Get NYC Council member profile with committee assignments.

    Data sourced from jehiah/nyc_legislation.

    Args:
        slug: Council member slug (e.g., "lincoln-restler", "carlina-rivera")

    Returns:
        Council member profile with contact info and committee memberships
    """
    url = f"https://raw.githubusercontent.com/jehiah/nyc_legislation/master/people/{slug}.json"
    person = await _fetch_json(url)

    if not person:
        return f"Council member '{slug}' not found. Try a slug like 'lincoln-restler', 'carlina-rivera', etc."

    # Active committee assignments
    offices = person.get("OfficeRecords", [])
    active = [o for o in offices if o.get("End", "") >= datetime.now().strftime("%Y")]
    committees = []
    for o in active:
        body = o.get("BodyName", "")
        title = o.get("Title", "")
        if body and body != "City Council":
            committees.append(f"  - {title}: {body}")

    committee_list = "\n".join(committees) if committees else "  No active committee assignments found"

    result = f"""
**{person.get('FullName', slug)}**

Active: {'Yes' if person.get('IsActive') else 'No'}
Email: {person.get('Email', 'N/A')}
Website: {person.get('WWW', 'N/A')}

**Current Committee Assignments ({len(committees)}):**
{committee_list}

[View legislative record on intro.nyc](https://intro.nyc/councilmembers/{slug})
"""
    return result.strip()


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_recent_legislation(
    year: int = 2024,
    status: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    Get recently introduced or enacted NYC Council legislation.

    Fetches the most recent bills for a given year, optionally filtered by status.
    Useful for newsletter content about recent council activity.

    Args:
        year: Legislative year (default 2024)
        status: Filter by status (e.g., "Enacted", "Committee"). Optional.
        limit: Maximum results (default 10, max 30)

    Returns:
        List of recent legislation with key details
    """
    limit = min(limit, 30)

    # Fetch directory listing from GitHub (sorted by name = by number)
    url = f"https://api.github.com/repos/jehiah/nyc_legislation/contents/introduction/{year}"
    entries = await _fetch_json(url)

    if not entries or not isinstance(entries, list):
        return f"No legislation data found for year {year}"

    # Get the most recent bill numbers (highest numbers = most recently introduced)
    bill_files = sorted(
        [e["name"].replace(".json", "") for e in entries if e.get("name", "").endswith(".json")],
        reverse=True
    )

    results = []
    checked = 0

    for bill_num in bill_files:
        if len(results) >= limit:
            break

        bill_url = f"https://intro.nyc/{bill_num}-{year}.json"
        bill = await _fetch_json(bill_url)
        if not bill:
            continue
        checked += 1

        if status and status.lower() not in (bill.get("StatusName") or "").lower():
            if checked >= 50:  # Don't check too many
                break
            continue

        sponsors = bill.get("Sponsors", [])
        primary_sponsor = sponsors[0].get("FullName", "Unknown") if sponsors else "Unknown"
        local_law = f" → LL {bill['LocalLaw']}" if bill.get("LocalLaw") else ""

        results.append(
            f"- **Int {bill_num}-{year}**{local_law}: "
            f"{bill.get('Title', 'Untitled')[:70]}\n"
            f"  Status: {bill.get('StatusName', 'Unknown')} | "
            f"Introduced: {(bill.get('IntroDate') or '')[:10]} | "
            f"Lead: {primary_sponsor}\n"
            f"  [View →](https://intro.nyc/{bill_num}-{year})"
        )

    if not results:
        filter_note = f" with status '{status}'" if status else ""
        return f"No recent legislation found for {year}{filter_note}"

    status_note = f" (status: {status})" if status else ""
    header = f"**Recent NYC Council Legislation — {year}{status_note}:**\n\n"
    return header + "\n".join(results)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_local_laws(year: int = 2024, limit: int = 20) -> str:
    """
    Get local laws enacted by the NYC Council in a given year.

    Local laws are bills that have been passed by the Council and signed by the Mayor.
    Useful for understanding what legislation has been recently enacted.

    Args:
        year: Year to retrieve local laws for (default 2024)
        limit: Maximum results (default 20, max 50)

    Returns:
        List of enacted local laws with bill references
    """
    limit = min(limit, 50)

    # Fetch directory listing and look for enacted bills
    url = f"https://api.github.com/repos/jehiah/nyc_legislation/contents/introduction/{year}"
    entries = await _fetch_json(url)

    if not entries or not isinstance(entries, list):
        return f"No legislation data found for year {year}"

    bill_files = [e["name"].replace(".json", "") for e in entries if e.get("name", "").endswith(".json")]

    results = []
    checked = 0

    for bill_num in bill_files:
        if len(results) >= limit:
            break

        bill_url = f"https://intro.nyc/{bill_num}-{year}.json"
        bill = await _fetch_json(bill_url)
        if not bill:
            continue
        checked += 1

        if bill.get("StatusName") != "Enacted" or not bill.get("LocalLaw"):
            if checked >= 200:
                break
            continue

        sponsors = bill.get("Sponsors", [])
        primary = sponsors[0].get("FullName", "Unknown") if sponsors else "Unknown"

        results.append(
            f"- **Local Law {bill['LocalLaw']}** (Int {bill_num}-{year}): "
            f"{bill.get('Title', 'Untitled')[:70]}\n"
            f"  Enacted: {(bill.get('EnactmentDate') or '')[:10]} | "
            f"Lead: {primary}\n"
            f"  [View →](https://intro.nyc/{bill_num}-{year}/local-law)"
        )

    if not results:
        return f"No enacted local laws found for {year} (checked {checked} bills)"

    header = f"**NYC Local Laws — {year} ({len(results)} found):**\n\n"
    return header + "\n".join(results)


# ============================================================================
# NYC Council Hearing / Event Tools
# ============================================================================

# Theme-to-agency mapping for cross-referencing hearing topics with Databook.
# Keys are keywords found in bill titles; values are agency name patterns
# and topic labels used to query contracts, budget, capital projects, etc.
_THEME_MAP = {
    "transportation": {"agencies": ["%transportation%", "%DOT%"], "label": "Transportation & Infrastructure"},
    "street": {"agencies": ["%transportation%", "%DOT%"], "label": "Street Safety & Infrastructure"},
    "traffic": {"agencies": ["%transportation%", "%DOT%"], "label": "Traffic & Street Safety"},
    "bicycle": {"agencies": ["%transportation%", "%DOT%"], "label": "Transportation & Cycling"},
    "sanitation": {"agencies": ["%sanitation%"], "label": "Sanitation & Waste Management"},
    "waste": {"agencies": ["%sanitation%"], "label": "Sanitation & Waste Management"},
    "housing": {"agencies": ["%housing%", "%HPD%", "%NYCHA%"], "label": "Housing & Development"},
    "homeless": {"agencies": ["%homeless%", "%DHS%"], "label": "Homelessness Services"},
    "shelter": {"agencies": ["%homeless%", "%DHS%"], "label": "Homelessness Services"},
    "education": {"agencies": ["%education%", "%DOE%"], "label": "Education"},
    "school": {"agencies": ["%education%", "%DOE%", "%school construction%"], "label": "Schools & Education"},
    "police": {"agencies": ["%police%", "%NYPD%"], "label": "Public Safety & Policing"},
    "fire": {"agencies": ["%fire%", "%FDNY%"], "label": "Fire & Emergency Services"},
    "health": {"agencies": ["%health%", "%DOHMH%"], "label": "Public Health"},
    "mental health": {"agencies": ["%health%", "%DOHMH%"], "label": "Mental Health"},
    "parks": {"agencies": ["%parks%", "%DPR%"], "label": "Parks & Recreation"},
    "environment": {"agencies": ["%environment%", "%DEP%"], "label": "Environmental Protection"},
    "water": {"agencies": ["%environment%", "%DEP%"], "label": "Water & Environmental"},
    "buildings": {"agencies": ["%buildings%", "%DOB%"], "label": "Buildings & Construction"},
    "construction": {"agencies": ["%buildings%", "%DOB%", "%design and construction%", "%DDC%"], "label": "Construction & Infrastructure"},
    "budget": {"agencies": ["%budget%", "%OMB%"], "label": "Budget & Finance"},
    "technology": {"agencies": ["%technology%", "%OTI%", "%DoITT%"], "label": "Technology & Innovation"},
    "consumer": {"agencies": ["%consumer%", "%DCWP%"], "label": "Consumer Protection"},
    "correction": {"agencies": ["%correction%", "%DOC%"], "label": "Criminal Justice & Corrections"},
    "youth": {"agencies": ["%youth%", "%DYCD%"], "label": "Youth & Community Development"},
    "child": {"agencies": ["%child%", "%ACS%"], "label": "Children & Family Services"},
    "planning": {"agencies": ["%planning%", "%DCP%"], "label": "City Planning & Land Use"},
    "zoning": {"agencies": ["%planning%", "%DCP%"], "label": "Zoning & Land Use"},
}


def _extract_themes(texts: list[str]) -> list[dict]:
    """Extract themes from bill titles by keyword matching against _THEME_MAP."""
    found = {}  # theme_key -> theme_dict (dedup)
    for text in texts:
        lower = text.lower()
        for keyword, theme in _THEME_MAP.items():
            if keyword in lower and theme["label"] not in found:
                found[theme["label"]] = theme
    return list(found.values())


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_upcoming_hearings(
    days_ahead: int = 14,
    days_behind: int = 7,
    limit: int = 25
) -> str:
    """
    Get upcoming (and recent) NYC Council committee hearings.

    Fetches council events from the city council calendar. Shows hearings
    within a date window, including the committee, agenda item count, and
    links to the official Legistar page and intro.nyc.

    Data sourced from jehiah/nyc_legislation (Legistar API mirror).

    Args:
        days_ahead: How many days ahead to look (default 14)
        days_behind: How many days back to include (default 7)
        limit: Maximum events to return (default 25, max 50)

    Returns:
        List of upcoming/recent hearings with committee and agenda info
    """
    from datetime import timedelta
    limit = min(limit, 50)
    now = datetime.now()
    window_start = now - timedelta(days=days_behind)
    window_end = now + timedelta(days=days_ahead)
    current_year = now.year

    # Fetch the events directory for current year
    years_to_check = [current_year]
    if window_start.year < current_year:
        years_to_check.insert(0, window_start.year)
    if window_end.year > current_year:
        years_to_check.append(window_end.year)

    matching_events = []

    for year in years_to_check:
        url = f"https://api.github.com/repos/jehiah/nyc_legislation/contents/events/{year}"
        entries = await _fetch_json(url)
        if not entries or not isinstance(entries, list):
            continue

        # Parse filenames: YYYY-MM-DD_HH_MM_committee-slug_ID.json
        for e in entries:
            fname = e.get("name", "")
            if not fname.endswith(".json"):
                continue
            # Extract date from filename
            parts = fname.replace(".json", "").split("_")
            if len(parts) < 4:
                continue
            try:
                event_date = datetime.strptime(parts[0], "%Y-%m-%d")
            except ValueError:
                continue

            if not (window_start <= event_date <= window_end):
                continue

            # Extract committee slug (parts between HH_MM and final ID)
            committee_slug = "-".join(parts[3:-1]) if len(parts) > 4 else parts[3] if len(parts) > 3 else "unknown"
            event_id = parts[-1] if parts[-1].isdigit() else ""

            matching_events.append({
                "filename": fname,
                "date": event_date,
                "date_str": parts[0],
                "time": f"{parts[1]}:{parts[2]}" if len(parts) > 2 else "",
                "committee_slug": committee_slug,
                "event_id": event_id,
                "year": year,
            })

    # Sort by date
    matching_events.sort(key=lambda x: x["date"])

    if not matching_events:
        return f"No council hearings found between {window_start.strftime('%Y-%m-%d')} and {window_end.strftime('%Y-%m-%d')}"

    # Fetch details for each event (limited to avoid API abuse)
    results = []
    for ev in matching_events[:limit]:
        event_url = f"https://raw.githubusercontent.com/jehiah/nyc_legislation/master/events/{ev['year']}/{ev['filename']}"
        event_data = await _fetch_json(event_url)

        committee = ev["committee_slug"].replace("-", " ").title()
        agenda_count = 0
        bills = []

        if event_data:
            committee = event_data.get("BodyName", committee)
            items = event_data.get("Items", [])
            # Filter to substantive agenda items (skip roll call, procedural)
            for item in items:
                if item.get("MatterFile") and item.get("AgendaSequence", 0) > 0:
                    agenda_count += 1
                    matter = item.get("MatterFile", "")
                    name = (item.get("MatterName") or item.get("Title") or "")[:60]
                    bills.append(f"{matter}: {name}")

        location = event_data.get("Location", "") if event_data else ""
        is_past = ev["date"] < now
        time_label = "📅" if not is_past else "📋"

        bill_preview = ""
        if bills:
            bill_preview = f"\n  Agenda ({agenda_count} items): " + "; ".join(bills[:3])
            if len(bills) > 3:
                bill_preview += f" +{len(bills)-3} more"

        legistar_url = f"https://legistar.council.nyc.gov/MeetingDetail.aspx?LEGID={ev['event_id']}&GID=61" if ev["event_id"] else ""

        results.append(
            f"- {time_label} **{ev['date_str']} {ev['time']}** — {committee}\n"
            f"  {location}{bill_preview}\n"
            f"  [Legistar]({legistar_url})" + (f" · Event ID: {ev['event_id']}" if ev["event_id"] else "")
        )

    header = f"**NYC Council Hearings ({window_start.strftime('%b %d')} – {window_end.strftime('%b %d, %Y')}):**\n\n"
    return header + "\n".join(results)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_hearing_detail(event_id: str, year: int = 2026) -> str:
    """
    Get full details for a specific NYC Council hearing/event.

    Returns the committee, date, location, full agenda with linked legislation,
    roll call attendance, and video/document links.

    Data sourced from jehiah/nyc_legislation.

    Args:
        event_id: The Legistar event ID (e.g., "22144")
        year: Year of the event (default 2026)

    Returns:
        Complete hearing details with agenda items, attendance, and links
    """
    # Search for the event file by ID in the year's directory
    dir_url = f"https://api.github.com/repos/jehiah/nyc_legislation/contents/events/{year}"
    entries = await _fetch_json(dir_url)

    if not entries or not isinstance(entries, list):
        return f"No events found for year {year}"

    # Find the file matching this event ID
    target_file = None
    for e in entries:
        fname = e.get("name", "")
        if fname.endswith(f"_{event_id}.json"):
            target_file = fname
            break

    if not target_file:
        return f"Event {event_id} not found in {year}. Use get_upcoming_hearings to find valid event IDs."

    event_url = f"https://raw.githubusercontent.com/jehiah/nyc_legislation/master/events/{year}/{target_file}"
    event = await _fetch_json(event_url)

    if not event:
        return f"Could not fetch event {event_id}"

    # Format agenda items
    items = event.get("Items", [])
    agenda_items = []
    for item in items:
        if item.get("RollCallFlag"):
            continue  # Skip roll call entries
        matter_file = item.get("MatterFile", "")
        matter_name = item.get("MatterName") or item.get("Title") or ""
        matter_type = item.get("MatterType", "")
        action = item.get("ActionName", "")
        seq = item.get("AgendaSequence", 0)

        if not matter_name and not matter_file:
            continue

        # Build intro.nyc link if this is a legislation item
        intro_link = ""
        if matter_file and matter_file.startswith("Int "):
            # Parse "Int 0323-2026" → "0323-2026"
            num_year = matter_file.replace("Int ", "")
            intro_link = f" [View on intro.nyc](https://intro.nyc/{num_year})"

        agenda_items.append(
            f"  {seq}. **{matter_file}** ({matter_type}){intro_link}\n"
            f"     {matter_name[:120]}\n"
            f"     Action: {action}" if action else
            f"  {seq}. **{matter_file}** ({matter_type}){intro_link}\n"
            f"     {matter_name[:120]}"
        )

    # Format roll call
    roll_call = ""
    for item in items:
        if item.get("RollCall"):
            present = [r["FullName"] for r in item["RollCall"] if r.get("Value") == "Present"]
            absent = [r["FullName"] for r in item["RollCall"] if r.get("Value") in ("Absent", "Medical")]
            roll_call = f"\n**Attendance** ({len(present)} present, {len(absent)} absent):\n"
            roll_call += f"  Present: {', '.join(present)}\n"
            if absent:
                roll_call += f"  Absent: {', '.join(absent)}\n"
            break

    # Links
    links = []
    if event.get("AgendaFile"):
        links.append(f"[Agenda PDF]({event['AgendaFile']})")
    if event.get("MinutesFile"):
        links.append(f"[Minutes PDF]({event['MinutesFile']})")
    if event.get("VideoPath"):
        links.append(f"[Video]({event['VideoPath']})")
    if event.get("InSiteURL"):
        links.append(f"[Legistar]({event['InSiteURL']})")

    link_line = " · ".join(links) if links else ""

    date_str = (event.get("Date") or "")[:16].replace("T", " ")

    result = f"""# {event.get('BodyName', 'Committee Hearing')}

**Date:** {date_str}
**Location:** {event.get('Location', 'N/A')}
**Status:** Agenda: {event.get('AgendaStatusName', 'N/A')} / Minutes: {event.get('MinutesStatusName', 'N/A')}

## Agenda ({len(agenda_items)} items)

{chr(10).join(agenda_items) if agenda_items else '  No substantive agenda items listed.'}
{roll_call}
{link_line}
"""
    return result.strip()


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
@log_tool_call
async def get_hearing_briefing(event_id: str, year: int = 2026) -> str:
    """
    Generate a data briefing for an upcoming NYC Council hearing.

    Cross-references the hearing's agenda items (legislation) with Databook's
    existing datasets to surface relevant context: contracts, budget data,
    capital projects, City Record notices, and job postings from agencies
    related to the hearing's topics.

    This is the most powerful hearing tool — it connects council activity
    to real government data.

    Data sourced from jehiah/nyc_legislation + Databook PostgreSQL.

    Args:
        event_id: The Legistar event ID (e.g., "22144")
        year: Year of the event (default 2026)

    Returns:
        A structured data brief organized by theme, with relevant Databook records
    """
    # Step 1: Fetch the hearing details
    dir_url = f"https://api.github.com/repos/jehiah/nyc_legislation/contents/events/{year}"
    entries = await _fetch_json(dir_url)
    if not entries or not isinstance(entries, list):
        return f"No events found for year {year}"

    target_file = None
    for e in entries:
        if e.get("name", "").endswith(f"_{event_id}.json"):
            target_file = e["name"]
            break

    if not target_file:
        return f"Event {event_id} not found in {year}"

    event_url = f"https://raw.githubusercontent.com/jehiah/nyc_legislation/master/events/{year}/{target_file}"
    event = await _fetch_json(event_url)
    if not event:
        return f"Could not fetch event {event_id}"

    committee = event.get("BodyName", "Unknown Committee")
    event_date = (event.get("Date") or "")[:10]

    # Step 2: Collect bill titles from agenda items
    bill_titles = []
    bill_refs = []
    items = event.get("Items", [])
    for item in items:
        matter_name = item.get("MatterName") or item.get("Title") or ""
        matter_file = item.get("MatterFile", "")
        if matter_name and not item.get("RollCallFlag"):
            bill_titles.append(matter_name)
            if matter_file:
                bill_refs.append(matter_file)

    if not bill_titles:
        return f"No agenda items found for event {event_id} ({committee} on {event_date})"

    # Step 3: Extract themes from bill titles
    themes = _extract_themes(bill_titles)

    # Also match based on the committee name itself
    committee_themes = _extract_themes([committee])
    for ct in committee_themes:
        if ct not in themes:
            themes.append(ct)

    # Step 4: Build the briefing header
    sections = []
    sections.append(f"# Hearing Data Brief: {committee}")
    sections.append(f"**Date:** {event_date}")
    sections.append(f"**Agenda Items:** {len(bill_titles)}")
    sections.append("")

    # List the bills
    sections.append("## Bills Under Consideration")
    for i, (title, ref) in enumerate(zip(bill_titles, bill_refs + [""] * len(bill_titles)), 1):
        intro_link = ""
        if ref and ref.startswith("Int "):
            num_year = ref.replace("Int ", "")
            intro_link = f" [→ intro.nyc](https://intro.nyc/{num_year})"
        sections.append(f"{i}. **{ref}**: {title[:100]}{intro_link}")
    sections.append("")

    if not themes:
        sections.append("*No specific data themes identified from agenda items. "
                        "Try using `get_agency_budget` or `search_contracts` directly.*")
        return "\n".join(sections)

    # Step 5: Query Databook for each theme
    sections.append(f"## Relevant Databook Context ({len(themes)} themes identified)\n")

    for theme_info in themes[:5]:  # Cap at 5 themes to keep response manageable
        label = theme_info["label"]
        agency_patterns = theme_info["agencies"]
        sections.append(f"### 📊 {label}\n")

        # 5a. Recent contracts
        try:
            contract_conditions = " OR ".join(f"agency ILIKE ${i+1}" for i in range(len(agency_patterns)))
            params = list(agency_patterns)
            limit_param = f"${len(params)+1}"
            sql = f"""
                SELECT contract_title, vendor_name, agency, award_amount, start_date, ctr_id
                FROM contracts
                WHERE ({contract_conditions})
                  AND start_date IS NOT NULL AND start_date != ''
                ORDER BY award_amount DESC NULLS LAST
                LIMIT {limit_param}
            """
            params.append(5)
            rows = await query(sql, *params)
            if rows:
                sections.append("**Recent Contracts:**")
                for r in rows:
                    amt = format_currency(r.get("award_amount")) if r.get("award_amount") else "N/A"
                    ctr_id = r.get("ctr_id", "")
                    sections.append(
                        f"- {(r.get('contract_title') or 'Untitled')[:60]} — {amt}\n"
                        f"  Vendor: {(r.get('vendor_name') or 'N/A')[:40]} | "
                        f"[View](/procurement/contract/{ctr_id})" if ctr_id else
                        f"- {(r.get('contract_title') or 'Untitled')[:60]} — {amt}\n"
                        f"  Vendor: {(r.get('vendor_name') or 'N/A')[:40]}"
                    )
                sections.append("")
        except Exception as e:
            logger.warning(f"[hearing-brief] contracts query error: {e}")

        # 5b. Budget summary
        try:
            budget_conditions = " OR ".join(f""""Agency Name" ILIKE ${i+1}""" for i in range(len(agency_patterns)))
            params = list(agency_patterns)
            sql = f"""
                SELECT "Agency Name",
                       SUM("Current Modified Budget Amount") as total_budget,
                       "Fiscal Year"
                FROM expensebudgetonnycopendata
                WHERE ({budget_conditions})
                  AND "Fiscal Year" = (SELECT MAX("Fiscal Year") FROM expensebudgetonnycopendata)
                GROUP BY "Agency Name", "Fiscal Year"
                ORDER BY total_budget DESC
                LIMIT 3
            """
            rows = await query(sql, *params)
            if rows:
                sections.append("**Budget (Current FY):**")
                for r in rows:
                    sections.append(
                        f"- {r['Agency Name']}: {format_currency(r['total_budget'])} (FY{r['Fiscal Year']})"
                    )
                sections.append("")
        except Exception as e:
            logger.warning(f"[hearing-brief] budget query error: {e}")

        # 5c. Capital projects
        try:
            cap_conditions = " OR ".join(f""""MAN_AGENCY_NAME" ILIKE ${i+1}""" for i in range(len(agency_patterns)))
            params = list(agency_patterns)
            limit_param = f"${len(params)+1}"
            sql = f"""
                SELECT "PROJECT_ID", "SHORT_DESCRIPTION", "TOTAL_PLAN_COMMTMTS" as budget,
                       "MAN_AGENCY_NAME"
                FROM capitalprojectslist
                WHERE ({cap_conditions})
                ORDER BY "TOTAL_PLAN_COMMTMTS" DESC NULLS LAST
                LIMIT {limit_param}
            """
            params.append(3)
            rows = await query(sql, *params)
            if rows:
                sections.append("**Capital Projects:**")
                for r in rows:
                    budget = format_currency(r.get("budget")) if r.get("budget") else "N/A"
                    prj_id = r.get("PROJECT_ID", "")
                    sections.append(
                        f"- {prj_id}: {(r.get('SHORT_DESCRIPTION') or 'N/A')[:60]} — {budget}"
                    )
                sections.append("")
        except Exception as e:
            logger.warning(f"[hearing-brief] capital projects query error: {e}")

        # 5d. Recent CROL notices
        try:
            crol_conditions = " OR ".join(f""""wegov-org-name" ILIKE ${i+1}""" for i in range(len(agency_patterns)))
            params = list(agency_patterns)
            limit_param = f"${len(params)+1}"
            sql = f"""
                SELECT "ShortTitle", "SectionName", "wegov-org-name", "RequestID"
                FROM crol
                WHERE ({crol_conditions})
                  AND "StartDate" <> ''
                  AND "StartDate" ~ '^[0-9]{{1,2}}/'
                  AND TO_DATE(SPLIT_PART("StartDate", ' ', 1), 'MM/DD/YYYY')
                      >= current_date - interval '30 days'
                ORDER BY TO_DATE(SPLIT_PART("StartDate", ' ', 1), 'MM/DD/YYYY') DESC
                LIMIT {limit_param}
            """
            params.append(3)
            rows = await query(sql, *params)
            if rows:
                sections.append("**Recent City Record Notices:**")
                for r in rows:
                    sections.append(
                        f"- [{r.get('SectionName', '')}] {(r.get('ShortTitle') or 'N/A')[:60]}\n"
                        f"  [City Record](https://a856-cityrecord.nyc.gov/RequestDetail/{r.get('RequestID', '')})"
                    )
                sections.append("")
        except Exception as e:
            logger.warning(f"[hearing-brief] CROL query error: {e}")

        # 5e. Open jobs
        try:
            job_conditions = " OR ".join(f""""Agency" ILIKE ${i+1}""" for i in range(len(agency_patterns)))
            params = list(agency_patterns)
            sql = f"""
                SELECT COUNT(*) as open_jobs
                FROM nycjobs
                WHERE ({job_conditions})
            """
            row = await query_one(sql, *params)
            if row and row.get("open_jobs", 0) > 0:
                sections.append(f"**Open Positions:** {row['open_jobs']} job(s) currently posted\n")
        except Exception as e:
            logger.warning(f"[hearing-brief] jobs query error: {e}")

    sections.append("---")
    sections.append("*Data from Databook.NYC. Use individual tools (e.g., `get_agency_budget`, "
                    "`search_contracts`) for deeper analysis on any section.*")

    return "\n".join(sections)


@mcp.prompt()
def hearing_prep(event_description: str) -> str:
    """Research and prepare a data brief for an upcoming NYC Council hearing."""
    return f"""Prepare a comprehensive data briefing for an NYC Council hearing about: "{event_description}"

1. Use `get_upcoming_hearings()` to find the relevant hearing
2. Use `get_hearing_detail()` to get the full agenda and linked legislation
3. Use `get_hearing_briefing()` to get cross-referenced data from Databook
4. For each bill on the agenda, use `get_legislation_detail()` to understand the legislative history
5. Identify the key agencies involved and use `get_agency_budget()` to check their budgets
6. Search for related contracts with `search_contracts()`
7. Synthesize into a structured briefing: hearing overview, bills summary, relevant data, and key takeaways"""


# ============================================================================
# Resources - Static data for context
# ============================================================================

@mcp.resource("resource://databook/overview")
def databook_overview() -> str:
    """Overview of NYC Government Databook capabilities and data categories."""
    return """# NYC Government Databook - MCP Server

## Available Data Categories

- **Organizations**: 100+ NYC agencies, boards, commissions, and offices
- **People**: City employee directory with titles, agencies, and salaries
- **Civil Service Titles**: Job classifications, salary grades, and exam info
- **City Record Notices**: Public hearings, contract awards, bid opportunities
- **Capital Projects**: Infrastructure and construction projects with budgets
- **Procurement**: Active contracts, solicitations, and registered vendors
- **Schools**: K-12 school data, enrollment, and facilities
- **City Facilities**: Buildings, parks, and public spaces
- **NYC Council Legislation**: Bills, resolutions, local laws, council members (via intro.nyc)

## Getting Started

Use `get_database_overview()` to see current record counts for each category.
Search tools use partial matching - try "Parks" or "DOT" for agencies.

## Key IDs for Joining Records

- `org_id` / `agency_id`: Links to organizations
- `epin` / `normalized_epin`: Links contracts to solicitations
- `contract_id` / `ctr_id`: Unique contract identifiers"""


@mcp.resource("resource://databook/joinable-ids")
def joinable_ids_reference() -> str:
    """Reference guide for IDs that enable joining records across tables."""
    import json
    return json.dumps({
        "description": "Key IDs for joining records across Databook tables",
        "contracts": {
            "primary": "contract_id",
            "alternate": ["ctr_id"],
            "joins_to_solicitations": "epin",
            "joins_to_agencies": "agency_id"
        },
        "solicitations": {
            "primary": "epin",
            "alternate": ["rfp_id", "bpm_id", "normalized_epin"],
            "joins_to_agencies": "agency_id"
        },
        "organizations": {
            "primary": "org_id",
            "alternate": ["agency_id", "acronym"]
        },
        "capital_projects": {
            "primary": "project_id",
            "joins_to_agencies": "managing_agency"
        },
        "people": {
            "joins_to_agencies": "agency",
            "joins_to_titles": "title_code"
        }
    }, indent=2)


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    mcp.run()

