"""
Databook Chatbot - Gemini 2.5 Flash with Function Calling

Provides a conversational interface to NYC government data.
Self-contained - uses existing database connection pool.
"""

import os
from typing import Optional
from google import genai
from google.genai import types

# Import database module (use the shared connection pool)
from postgrex import PostgresModelAsync
from modules.errfmt import exc_str

# Gemini client (initialized lazily)
_client = None


def get_client():
    """Get or create Gemini client."""
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        _client = genai.Client(api_key=api_key)
    return _client


# ========== Tool Implementations (Database Queries) ==========

async def _live_orgs() -> str:
    """`AND retired_at IS NULL` — retired orgs are merged-away duplicates.
    See modules/orgfilter.py for why this is probed rather than inlined."""
    try:
        from modules import orgfilter
    except ImportError:
        import orgfilter
    return await orgfilter.live_clause(lambda sql: _query(sql))


async def _query(sql: str, *args):
    """Execute a database query using the shared connection pool."""
    try:
        result = await PostgresModelAsync.select(sql, args if args else None)
        return result.get("rows", [])
    except Exception as e:
        print(f"Database query error: {exc_str(e)}")
        return []


async def get_database_overview():
    """Get database overview stats."""
    stats = {}
    for table, desc in [
        ("wegov_orgs", "Organizations"),
        ("nyccivilservicetitles", "Civil Service Titles"),
        ("crol", "City Record Notices"),
        ("capitalprojectsdollarscomp", "Capital Projects"),
        ("contracts", "Contracts"),
        ("vendors", "Vendors"),
        ("solicitations", "Solicitations"),
    ]:
        try:
            rows = await _query(f'SELECT COUNT(*) as cnt FROM {table}')
            stats[desc] = rows[0]["cnt"] if rows else 0
        except:
            stats[desc] = "N/A"
    
    result = "# Databook NYC Database Overview\n\n"
    for key, val in stats.items():
        result += f"- **{key}**: {val:,} records\n" if isinstance(val, int) else f"- **{key}**: {val}\n"
    return result


async def search_organizations(query_text: str, limit: int = 20):
    """Search organizations by name."""
    rows = await _query(
        f'SELECT id, name, type FROM wegov_orgs WHERE name ILIKE $1'
        f'{await _live_orgs()} ORDER BY name LIMIT $2',
        f"%{query_text}%", limit
    )
    if not rows:
        return f"No organizations found matching '{query_text}'"
    
    result = f"Found {len(rows)} organizations:\n\n"
    for r in rows:
        result += f"- **{r['name']}** (ID: {r['id']}, Type: {r['type']})\n"
    return result


async def get_organization_profile(org_id: int):
    """Get organization profile."""
    # ⚠ The parent comes from the JOIN, not from a column. This used to render
    # `child_of` raw, so the chatbot answered "**Parent**: ["recIXPDD84xmPdV2s"]"
    # — an Airtable record id, JSON brackets and all. Phase 3 replaced that
    # string join with wegov_orgs.parent_org_id; orgfilter resolves whichever
    # mechanism this database has.
    try:
        from modules import orgfilter
    except ImportError:
        import orgfilter
    pjoin = await orgfilter.parent_join(_query, "o", "par")
    rows = await _query(
        f'SELECT o.*, par.name AS parent_name FROM wegov_orgs o{pjoin} '
        'WHERE o.id = $1', org_id)
    if not rows:
        return f"Organization {org_id} not found"

    org = rows[0]
    return f"""# {org['name']}

- **Type**: {org.get('type', 'N/A')}
- **Parent**: {org.get('parent_name') or 'N/A'}
- **URL**: {org.get('url', 'N/A')}
"""


async def search_capital_projects(query_text: str, limit: int = 20):
    """Search capital projects."""
    rows = await _query(
        '''SELECT "PROJECT_ID", "PROJECT_DESCR", "MANAGING_AGCY" as agency, "BUDG_CURR" as budget
           FROM capitalprojectsdollarscomp
           WHERE ("PROJECT_DESCR" ILIKE $1 OR "PROJECT_ID" ILIKE $1)
             AND "PUB_DATE" = (SELECT MAX("PUB_DATE") FROM capitalprojectsdollarscomp)
           ORDER BY "PROJECT_DESCR" LIMIT $2''',
        f"%{query_text}%", limit
    )
    if not rows:
        return f"No capital projects found matching '{query_text}'"
    
    result = f"Found {len(rows)} capital projects:\n\n"
    for r in rows:
        budget = f"${float(r['budget']):,.0f}" if r.get('budget') else "N/A"
        desc = (r.get('PROJECT_DESCR') or 'No Description')[:60]
        result += f"- **{desc}** [ID: {r['PROJECT_ID']}]\n  Agency: {r.get('agency', 'N/A')} | Budget: {budget}\n"
    return result


async def get_agency_projects(agency: str, limit: int = 15):
    """Get capital projects for an agency."""
    # Get count first
    count_rows = await _query(
        '''SELECT COUNT(*) as cnt FROM capitalprojectsdollarscomp
           WHERE "wegov-org-name" ILIKE $1
             AND "PUB_DATE" = (SELECT MAX("PUB_DATE") FROM capitalprojectsdollarscomp)''',
        f"%{agency}%"
    )
    total = count_rows[0]["cnt"] if count_rows else 0
    
    # Get top projects
    rows = await _query(
        '''SELECT "PROJECT_ID", "PROJECT_DESCR", "BUDG_CURR" as budget
           FROM capitalprojectsdollarscomp
           WHERE "wegov-org-name" ILIKE $1
             AND "PUB_DATE" = (SELECT MAX("PUB_DATE") FROM capitalprojectsdollarscomp)
           ORDER BY "BUDG_CURR"::numeric DESC NULLS LAST LIMIT $2''',
        f"%{agency}%", limit
    )
    
    if total == 0:
        return f"No capital projects found for agency '{agency}'"
    
    result = f"# Capital Projects for '{agency}'\n\nTotal: **{total}** projects\n\nTop {len(rows)} by budget:\n\n"
    for r in rows:
        budget = f"${float(r['budget']):,.0f}" if r.get('budget') else "N/A"
        desc = (r.get('PROJECT_DESCR') or 'No Description')[:50]
        result += f"- **{desc}** [{r['PROJECT_ID']}] - {budget}\n"
    return result


async def search_contracts(query_text: Optional[str] = None, vendor: Optional[str] = None,
                           agency: Optional[str] = None, status: Optional[str] = None, limit: int = 20):
    """Search contracts."""
    conditions = []
    args = []
    arg_num = 1
    
    if query_text:
        conditions.append(f'contract_title ILIKE ${arg_num}')
        args.append(f"%{query_text}%")
        arg_num += 1
    if vendor:
        conditions.append(f'vendor_name ILIKE ${arg_num}')
        args.append(f"%{vendor}%")
        arg_num += 1
    if agency:
        conditions.append(f'agency ILIKE ${arg_num}')
        args.append(f"%{agency}%")
        arg_num += 1
    if status:
        conditions.append(f'status ILIKE ${arg_num}')
        args.append(f"%{status}%")
        arg_num += 1
    
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    args.append(limit)
    
    rows = await _query(
        f'''SELECT contract_id, contract_title, vendor_name, agency, current_amount, status
            FROM contracts {where} ORDER BY current_amount DESC NULLS LAST LIMIT ${arg_num}''',
        *args
    )
    
    if not rows:
        return "No contracts found matching criteria"
    
    result = f"Found {len(rows)} contracts:\n\n"
    for r in rows:
        amt = f"${float(r['current_amount']):,.0f}" if r.get('current_amount') else "N/A"
        title = (r.get('contract_title') or 'No Title')[:50]
        vendor_name = (r.get('vendor_name') or 'Unknown')[:30]
        agency_name = (r.get('agency') or 'Unknown')[:20]
        result += f"- **{title}**\n  Vendor: {vendor_name} | Agency: {agency_name} | Amount: {amt}\n"
    return result


async def search_vendors(query_text: str, limit: int = 20):
    """Search vendors."""
    rows = await _query(
        '''SELECT vendor_id, legal_name, primary_industry, entity_type
           FROM vendors WHERE legal_name ILIKE $1 ORDER BY legal_name LIMIT $2''',
        f"%{query_text}%", limit
    )
    
    if not rows:
        return f"No vendors found matching '{query_text}'"
    
    result = f"Found {len(rows)} vendors:\n\n"
    for r in rows:
        result += f"- **{r['legal_name']}** (ID: {r['vendor_id']}) - {r.get('primary_industry', 'N/A')}\n"
    return result


async def search_civil_titles(query_text: str, limit: int = 20):
    """Search civil service titles."""
    rows = await _query(
        '''SELECT DISTINCT "Title Code", "Title Description", "Assignment Level"
           FROM nyccivilservicetitles
           WHERE "Title Description" ILIKE $1 OR "Title Code" ILIKE $1
           ORDER BY "Title Description" LIMIT $2''',
        f"%{query_text}%", limit
    )
    
    if not rows:
        return f"No civil service titles found matching '{query_text}'"
    
    result = f"Found {len(rows)} titles:\n\n"
    for r in rows:
        result += f"- **{r['Title Description']}** (Code: {r['Title Code']}, Level: {r.get('Assignment Level', 'N/A')})\n"
    return result


# ========== Tool Function Registry ==========

TOOL_FUNCTIONS = {
    "get_database_overview": get_database_overview,
    "search_organizations": search_organizations,
    "get_organization_profile": get_organization_profile,
    "search_capital_projects": search_capital_projects,
    "get_agency_projects": get_agency_projects,
    "search_contracts": search_contracts,
    "search_vendors": search_vendors,
    "search_civil_titles": search_civil_titles,
}


def get_tools():
    """Define tool declarations for Gemini function calling."""
    return [
        types.Tool(function_declarations=[
            types.FunctionDeclaration(
                name="get_database_overview",
                description="Get a summary of all available data in the Databook database. Use this first to understand what data is available.",
                parameters=types.Schema(type="OBJECT", properties={})
            ),
            types.FunctionDeclaration(
                name="search_organizations",
                description="Search NYC organizations (agencies, boards, offices) by name.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query_text": types.Schema(type="STRING", description="Organization name to search for"),
                        "limit": types.Schema(type="INTEGER", description="Max results (default 20)")
                    },
                    required=["query_text"]
                )
            ),
            types.FunctionDeclaration(
                name="get_organization_profile",
                description="Get detailed profile for a specific NYC organization.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "org_id": types.Schema(type="INTEGER", description="Organization ID from search_organizations")
                    },
                    required=["org_id"]
                )
            ),
            types.FunctionDeclaration(
                name="search_capital_projects",
                description="Search NYC capital projects by name or ID.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query_text": types.Schema(type="STRING", description="Project name or ID"),
                        "limit": types.Schema(type="INTEGER", description="Max results (default 20)")
                    },
                    required=["query_text"]
                )
            ),
            types.FunctionDeclaration(
                name="get_agency_projects",
                description="Get capital projects for a specific agency. Returns total count and top projects by budget.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "agency": types.Schema(type="STRING", description="Agency name (partial match, e.g., 'Parks', 'Health')"),
                        "limit": types.Schema(type="INTEGER", description="Max results (default 15)")
                    },
                    required=["agency"]
                )
            ),
            types.FunctionDeclaration(
                name="search_contracts",
                description="Search NYC procurement contracts with filters.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query_text": types.Schema(type="STRING", description="Search in contract title"),
                        "vendor": types.Schema(type="STRING", description="Filter by vendor name"),
                        "agency": types.Schema(type="STRING", description="Filter by agency name"),
                        "status": types.Schema(type="STRING", description="Filter by status"),
                        "limit": types.Schema(type="INTEGER", description="Max results (default 20)")
                    }
                )
            ),
            types.FunctionDeclaration(
                name="search_vendors",
                description="Search registered NYC vendors by name.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query_text": types.Schema(type="STRING", description="Vendor name"),
                        "limit": types.Schema(type="INTEGER", description="Max results (default 20)")
                    },
                    required=["query_text"]
                )
            ),
            types.FunctionDeclaration(
                name="search_civil_titles",
                description="Search NYC civil service job titles.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query_text": types.Schema(type="STRING", description="Title name or code to search"),
                        "limit": types.Schema(type="INTEGER", description="Max results (default 20)")
                    },
                    required=["query_text"]
                )
            ),
        ])
    ]


async def execute_function(name: str, args: dict) -> str:
    """Execute a tool function and return the result."""
    func = TOOL_FUNCTIONS.get(name)
    if not func:
        return f"Unknown function: {name}"
    
    try:
        return await func(**args)
    except Exception as e:
        return f"Error executing {name}: {str(e)}"


SYSTEM_PROMPT = """You are a helpful assistant for Databook NYC (databook.nyc), a platform for exploring NYC government data.

You have access to tools that let you:
- Search organizations (agencies, boards, offices) and get their profiles
- Search capital projects and get agency project counts
- Search contracts by vendor, agency, or keywords
- Search vendors
- Search civil service job titles

When answering questions:
- Use the appropriate tools to find accurate data
- Format monetary values as currency ($X,XXX.XX)
- Be concise but informative
- For agency questions, use get_agency_projects to get project counts

You are embedded on databook.nyc and help users explore NYC government data."""


async def chat(message: str, history: list = None) -> str:
    """
    Process a chat message and return a response.
    
    Args:
        message: User's message
        history: Optional conversation history
        
    Returns:
        Assistant's response
    """
    client = get_client()
    tools = get_tools()
    
    # Build conversation contents
    contents = []
    
    # Add history if provided
    if history:
        for msg in history:
            # Gemini uses 'model' instead of 'assistant'
            role = "model" if msg["role"] == "assistant" else msg["role"]
            contents.append(types.Content(
                role=role,
                parts=[types.Part(text=msg["content"])]
            ))
    
    # Add current message
    contents.append(types.Content(
        role="user",
        parts=[types.Part(text=message)]
    ))
    
    # Generate response
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            tools=tools,
            system_instruction=SYSTEM_PROMPT
        )
    )
    
    # Check for function calls
    max_iterations = 5
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        
        if not response.candidates or not response.candidates[0].content.parts:
            return "I couldn't generate a response. Please try again."
        
        part = response.candidates[0].content.parts[0]
        
        if hasattr(part, 'function_call') and part.function_call:
            fc = part.function_call
            # Execute the async function
            result = await execute_function(fc.name, dict(fc.args))
            
            contents.append(response.candidates[0].content)
            contents.append(types.Content(
                role="user",
                parts=[types.Part(function_response=types.FunctionResponse(
                    name=fc.name,
                    response={"result": result}
                ))]
            ))
            
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    tools=tools,
                    system_instruction=SYSTEM_PROMPT
                )
            )
        else:
            return part.text
    
    return "I'm having trouble processing this request. Please try a simpler question."
