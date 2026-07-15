# DatabookNYC MCP Server

Connect to NYC government data using the Model Context Protocol (MCP). Query organizations, capital projects, contracts, vendors, civil service titles, and City Record notices.

## Quick Start

### Claude Desktop (Remote)

Add to your Claude Desktop config:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "databook-nyc": {
      "url": "https://api.databook.nyc/mcp"
    }
  }
}
```

Restart Claude Desktop after saving. You'll now have access to 21 tools for querying NYC government data.

> [!NOTE]
> The remote endpoint uses OAuth 2.1 discovery at `https://api.databook.nyc/.well-known/oauth-protected-resource`

---


## Available Tools (21 total)

### Organizations
| Tool | Description |
|------|-------------|
| `search_organizations` | Search agencies, boards, offices by name |
| `get_organization_profile` | Get detailed org profile with headcount and spending |
| `get_organization_notices` | Get recent City Record notices for an org |
| `get_organization_stats` | Get aggregate organization statistics |

### Capital Projects
| Tool | Description |
|------|-------------|
| `search_capital_projects` | Search capital projects by name or ID |
| `get_project_details` | Get full project details and timeline |
| `get_agency_projects` | Get projects for a specific agency |

### Contracts & Procurement
| Tool | Description |
|------|-------------|
| `search_contracts` | Search contracts with filters |
| `get_contract_details` | Get full contract information |
| `get_contract_stats` | Get aggregate contract statistics |
| `search_solicitations` | Search RFPs and bids |
| `get_solicitation_details` | Get solicitation details |
| `get_open_solicitations` | Get currently open opportunities |

### Vendors
| Tool | Description |
|------|-------------|
| `search_vendors` | Search registered NYC vendors |
| `get_vendor_profile` | Get vendor details with contract history |

### Civil Service Titles
| Tool | Description |
|------|-------------|
| `search_civil_titles` | Search job titles by name or code |
| `get_title_positions` | Get employees holding a specific title |

### City Record (CROL)
| Tool | Description |
|------|-------------|
| `search_notices` | Search City Record notices |
| `get_notice_stats` | Get notice statistics (last 30 days) |
| `get_recent_events` | Get upcoming public events and hearings |

### General
| Tool | Description |
|------|-------------|
| `get_database_overview` | Get summary of all available data |

---

## Example Prompts

Once connected, try asking Claude:

- "How many capital projects does the Department of Parks and Recreation have?"
- "Search for IT contracts with the Department of Education"
- "Find civil service titles related to engineer"
- "What solicitations are currently open?"
- "Get the profile for the Health Department"
- "Show me recent City Record notices about public hearings"

---

## Data Sources

| Dataset | Description |
|---------|-------------|
| Organizations | 600+ NYC agencies, boards, offices from WeGov registry |
| Capital Projects | 8,000+ projects from NYC Capital Projects Tracker |
| Contracts | NYC procurement contracts from Checkbook NYC |
| Vendors | Registered vendors from PASSPort |
| Civil Titles | NYC civil service job titles and positions |
| City Record | CROL notices, events, and announcements |

---

## Support

- Website: [databook.nyc](https://databook.nyc)
- API Docs: [api.databook.nyc/docs](https://api.databook.nyc/docs)
- Chat Assistant: Available on databook.nyc (squirrel icon)
