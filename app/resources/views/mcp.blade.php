@extends('layout')


@section('head')
	<meta name="description" content="Connect to NYC government data using the Model Context Protocol (MCP). 40 read-only tools spanning organizations, people, salaries, jobs, contracts, vendors, capital projects, budgets, legislation, schools, facilities, and City Record notices. Works with Claude, Cursor, VS Code, and any MCP client." />
	<meta rel="canonical" href="{{ url('/mcp') }}" />
	<style>
		/* Page-local code block — dark navy surface, mono, token-driven (see handoff5 spec 03-mcp) */
		.codeblock {
			position: relative;
			background: var(--db-navy-900);
			color: #e7ecf3;
			padding: var(--db-space-4, 32px);
			border-radius: var(--db-radius);
			border: 1px solid var(--db-navy-800);
			font-family: var(--db-font-mono);
			font-size: var(--db-text-sm);
			line-height: 1.6;
			overflow-x: auto;
		}
		.codeblock .tok-key { color: #8fd6ff; }
		.codeblock .tok-str { color: #8fe0a3; }
		.codeblock .tok-com { color: #7e93ad; }
		.codeblock .codeblock-copy {
			position: absolute;
			top: var(--db-space-2, 16px);
			right: var(--db-space-2, 16px);
			padding: 0.2rem 0.6rem;
			font-size: var(--db-text-xs, 0.8125rem);
			background: rgba(255,255,255,0.08);
			color: #e7ecf3;
			border: 1px solid rgba(255,255,255,0.18);
			border-radius: var(--db-radius-sm);
			cursor: pointer;
		}
		.codeblock .codeblock-copy:hover { background: rgba(255,255,255,0.16); }
		/* Inline path token — light surface, mono */
		.config-path {
			display: inline-block;
			background: var(--db-bg-secondary);
			border: 1px solid var(--db-border);
			padding: 0.2rem 0.6rem;
			border-radius: var(--db-radius-sm);
			font-family: var(--db-font-mono);
			font-size: var(--db-text-sm);
		}
	</style>
@endsection


@section('menubar')
	@include('sub.menubar', ['active' => 'about'])
@endsection

@section('content')

{{-- Navy hero band — "For developers" treatment (handoff5 b3-mcp) --}}
<div class="db-hero">
	<div class="inner_container">
		<div class="container db-hero-inner">
			<div class="db-hero-copy">
				<div class="db-eyebrow" style="color:var(--db-accent);">For developers</div>
				<h1><i class="bi bi-plug me-2"></i>Databook MCP Server</h1>
				<p>Query NYC government data from any Model Context Protocol client &mdash; Claude, Cursor, VS Code, ChatGPT, or your own agent &mdash; through Databook's normalized datasets: organizations and people, salaries and jobs, contracts, vendors and solicitations, capital projects and budgets, legislation, schools, facilities, and City Record notices.</p>
				<div class="mt-3">
					<span id="mcpStatus" class="db-badge db-badge-neutral"><span class="db-dot"></span> Checking status</span>
					<span class="db-badge db-badge-neutral ms-2">v1 &middot; read-only</span>
				</div>
			</div>
		</div>
	</div>
</div>

<div class="inner_container">
	<div class="container" style="padding-top: var(--db-space-4); padding-bottom: var(--db-space-5);">

		{{-- Readable prose measure (~70ch) for the intro --}}
		<div class="db-prose" style="max-width: 70ch;">
			<p class="db-page-lead">
				The Databook MCP server exposes our normalized civic datasets as tools any MCP-compatible
				client can call. It's the same data behind this site, served in a machine-readable shape —
				read-only and backed by the same official NYC sources documented on each
				<a href="{{ route('about.data') }}">data sources page</a>.
			</p>
		</div>

		{{-- ───────────────────────── Quick Start ───────────────────────── --}}
		<div class="db-eyebrow" style="margin-top: var(--db-space-5);">Connect</div>
		<h2 class="mb-4">Quick Start</h2>

		<div class="db-alert db-alert-info mb-4" role="alert">
			<i class="bi bi-plug"></i>
			<div class="db-alert-body">
				<strong>Works with any MCP client &mdash; not just Claude.</strong> This is a standard
				remote MCP server (Streamable HTTP, no authentication), so any MCP-compatible client or
				agent can use it &mdash; Claude, Claude Code, Cursor, VS Code, ChatGPT / OpenAI Agents,
				Gemini, or your own app built on an MCP SDK. Just point the client at the endpoint:
				<code>https://api.databook.nyc/mcp</code>. The steps below use Claude Desktop as one example, and <a href="https://modelcontextprotocol.io" target="_blank" rel="noopener">MCP</a> is the open standard behind it &mdash; a common way for AI assistants to call external tools and data.
			</div>
		</div>

		<div class="db-card mb-4">
			<div class="db-card-body">
				<h4 class="db-card-title"><i class="bi bi-mouse me-2" style="color: var(--db-accent);"></i>Option 1: Add via Claude Desktop UI (Easiest)</h4>
				<p>In Claude Desktop, click on the <strong>MCP Servers</strong> icon in the sidebar, then click <strong>"Add custom connector"</strong>:</p>

				<div class="row">
					<div class="col-md-6">
						<div class="mb-3">
							<label class="form-label fw-bold">Name</label>
							<div class="input-group">
								<input type="text" class="db-input form-control" value="DatabookNYC" id="connectorName" readonly>
								<button class="db-btn db-btn-outline btn-outline-secondary" onclick="copyField('connectorName')" type="button" aria-label="Copy name"><i class="bi bi-clipboard" aria-hidden="true"></i></button>
							</div>
						</div>
					</div>
					<div class="col-md-6">
						<div class="mb-3">
							<label class="form-label fw-bold">Remote MCP server URL</label>
							<div class="input-group">
								<input type="text" class="db-input form-control" value="https://api.databook.nyc/mcp" id="connectorUrl" readonly>
								<button class="db-btn db-btn-outline btn-outline-secondary" onclick="copyField('connectorUrl')" type="button" aria-label="Copy URL"><i class="bi bi-clipboard" aria-hidden="true"></i></button>
							</div>
						</div>
					</div>
				</div>
				<p class="mb-0" style="color: var(--db-text-muted);"><i class="bi bi-info-circle me-1"></i> Leave OAuth fields empty — no authentication required.</p>
			</div>
		</div>

		<div class="db-card mb-4">
			<div class="db-card-body">
				<h4 class="db-card-title"><i class="bi bi-file-earmark-code me-2" style="color: var(--db-accent);"></i>Option 2: Edit Config File</h4>
				<p>Alternatively, add to your Claude Desktop configuration file:</p>

				<div class="mb-3">
					<strong>macOS:</strong>
					<code class="config-path">~/Library/Application Support/Claude/claude_desktop_config.json</code>
				</div>
				<div class="mb-4">
					<strong>Windows:</strong>
					<code class="config-path">%APPDATA%\Claude\claude_desktop_config.json</code>
				</div>

				<div class="codeblock mb-4">
					<button class="codeblock-copy" onclick="copyConfig()" type="button" aria-label="Copy configuration"><i class="bi bi-clipboard me-1" aria-hidden="true"></i>Copy</button>
<pre class="mb-0" id="mcp-config">{
  <span class="tok-key">"mcpServers"</span>: {
    <span class="tok-key">"databook-nyc"</span>: {
      <span class="tok-key">"url"</span>: <span class="tok-str">"https://api.databook.nyc/mcp"</span>
    }
  }
}</pre>
				</div>

				<div class="db-alert db-alert-info" role="alert">
					<i class="bi bi-info-circle"></i>
					<div class="db-alert-body">
						<strong>Note:</strong> Restart Claude Desktop after adding the connector. You'll then have access to 40 tools for querying NYC government data.
					</div>
				</div>
			</div>
		</div>

		{{-- ───────────────────────── Available Tools ───────────────────────── --}}
		<div class="db-card mb-4">
			<div class="db-card-body">
				<h4 class="db-card-title"><i class="bi bi-terminal me-2" style="color: var(--db-accent);" aria-hidden="true"></i>Option 3: Other MCP clients</h4>
				<p>Any MCP client connects to the same endpoint &mdash; no API key. For example, with the Claude Code CLI:</p>
				<div class="codeblock mb-3">
					<button class="codeblock-copy" onclick="copyCmd()" type="button" aria-label="Copy command"><i class="bi bi-clipboard me-1" aria-hidden="true"></i>Copy</button>
<pre class="mb-0" id="mcp-cmd">claude mcp add --transport http databook-nyc https://api.databook.nyc/mcp</pre>
				</div>
				<p class="mb-0" style="color: var(--db-text-muted);">Cursor, VS Code, Cline, Continue, Zed, and the OpenAI / Gemini agent SDKs all accept the same remote MCP URL.</p>
			</div>
		</div>

		<div class="db-eyebrow" style="margin-top: var(--db-space-5);">Reference</div>
		<h2 class="mb-4">Available Tools (40 total)</h2>

		<div class="row">
			<div class="col-md-6">
				<div class="db-card mb-4">
					<div class="db-card-body">
						<h5 class="db-card-title"><i class="bi bi-building me-2" style="color: var(--db-accent);"></i>Organizations</h5>
						<table class="db-table table table-sm">
							<tbody>
								<tr><td><code>search_organizations</code></td><td>Search agencies, boards, offices by name</td></tr>
								<tr><td><code>get_organization_profile</code></td><td>Get detailed org profile with headcount and spending</td></tr>
								<tr><td><code>get_organization_notices</code></td><td>Get recent City Record notices for an org</td></tr>
							</tbody>
						</table>
					</div>
				</div>

				<div class="db-card mb-4">
					<div class="db-card-body">
						<h5 class="db-card-title"><i class="bi bi-people me-2" style="color: var(--db-accent);"></i>People</h5>
						<table class="db-table table table-sm">
							<tbody>
								<tr><td><code>search_people</code></td><td>Search NYC government employees by name</td></tr>
							</tbody>
						</table>
					</div>
				</div>

				<div class="db-card mb-4">
					<div class="db-card-body">
						<h5 class="db-card-title"><i class="bi bi-person-badge me-2" style="color: var(--db-accent);"></i>Civil Service Titles</h5>
						<table class="db-table table table-sm">
							<tbody>
								<tr><td><code>search_civil_titles</code></td><td>Search civil service job titles</td></tr>
								<tr><td><code>get_title_positions</code></td><td>Get employees holding a specific title</td></tr>
							</tbody>
						</table>
					</div>
				</div>

				<div class="db-card mb-4">
					<div class="db-card-body">
						<h5 class="db-card-title"><i class="bi bi-briefcase me-2" style="color: var(--db-accent);"></i>Jobs &amp; Salaries</h5>
						<table class="db-table table table-sm">
							<tbody>
								<tr><td><code>search_jobs</code></td><td>Search NYC government job postings</td></tr>
								<tr><td><code>get_job_details</code></td><td>Get details for a specific job posting</td></tr>
								<tr><td><code>get_salary_stats</code></td><td>Get salary statistics for city employees</td></tr>
								<tr><td><code>get_top_salaries</code></td><td>Get highest-paid city employees</td></tr>
							</tbody>
						</table>
					</div>
				</div>

				<div class="db-card mb-4">
					<div class="db-card-body">
						<h5 class="db-card-title"><i class="bi bi-hammer me-2" style="color: var(--db-accent);"></i>Capital Projects</h5>
						<table class="db-table table table-sm">
							<tbody>
								<tr><td><code>search_capital_projects</code></td><td>Search capital projects by name or ID</td></tr>
								<tr><td><code>get_project_details</code></td><td>Get full project details and timeline</td></tr>
								<tr><td><code>get_agency_projects</code></td><td>Get projects for a specific agency</td></tr>
								<tr><td><code>get_project_milestones</code></td><td>Get largest projects with milestones in a date range</td></tr>
							</tbody>
						</table>
					</div>
				</div>

				<div class="db-card mb-4">
					<div class="db-card-body">
						<h5 class="db-card-title"><i class="bi bi-file-earmark-text me-2" style="color: var(--db-accent);"></i>Contracts &amp; Procurement</h5>
						<table class="db-table table table-sm">
							<tbody>
								<tr><td><code>search_contracts</code></td><td>Search contracts with filters</td></tr>
								<tr><td><code>get_contract_details</code></td><td>Get full contract information</td></tr>
								<tr><td><code>get_contract_stats</code></td><td>Get aggregate contract statistics</td></tr>
								<tr><td><code>search_solicitations</code></td><td>Search RFPs and bids</td></tr>
								<tr><td><code>get_solicitation_details</code></td><td>Get solicitation details</td></tr>
								<tr><td><code>get_open_solicitations</code></td><td>Get currently open opportunities</td></tr>
							</tbody>
						</table>
					</div>
				</div>
			</div>

			<div class="col-md-6">
				<div class="db-card mb-4">
					<div class="db-card-body">
						<h5 class="db-card-title"><i class="bi bi-shop me-2" style="color: var(--db-accent);"></i>Vendors</h5>
						<table class="db-table table table-sm">
							<tbody>
								<tr><td><code>search_vendors</code></td><td>Search registered NYC vendors</td></tr>
								<tr><td><code>get_vendor_profile</code></td><td>Get vendor details with contract history</td></tr>
							</tbody>
						</table>
					</div>
				</div>

				<div class="db-card mb-4">
					<div class="db-card-body">
						<h5 class="db-card-title"><i class="bi bi-cash-stack me-2" style="color: var(--db-accent);"></i>Budget</h5>
						<table class="db-table table table-sm">
							<tbody>
								<tr><td><code>get_agency_budget</code></td><td>Get budget breakdown for a specific agency</td></tr>
								<tr><td><code>compare_agency_budgets</code></td><td>Compare budgets across NYC agencies</td></tr>
							</tbody>
						</table>
					</div>
				</div>

				<div class="db-card mb-4">
					<div class="db-card-body">
						<h5 class="db-card-title"><i class="bi bi-bank me-2" style="color: var(--db-accent);"></i>Legislation</h5>
						<table class="db-table table table-sm">
							<tbody>
								<tr><td><code>search_legislation</code></td><td>Search Council legislation by keyword</td></tr>
								<tr><td><code>get_legislation_detail</code></td><td>Get full details for a specific bill</td></tr>
								<tr><td><code>get_council_member</code></td><td>Get a Council member profile and committees</td></tr>
								<tr><td><code>get_recent_legislation</code></td><td>Get recently introduced or enacted bills</td></tr>
								<tr><td><code>get_local_laws</code></td><td>Get local laws enacted in a given year</td></tr>
							</tbody>
						</table>
					</div>
				</div>

				<div class="db-card mb-4">
					<div class="db-card-body">
						<h5 class="db-card-title"><i class="bi bi-calendar-event me-2" style="color: var(--db-accent);"></i>Council Hearings</h5>
						<table class="db-table table table-sm">
							<tbody>
								<tr><td><code>get_upcoming_hearings</code></td><td>Get upcoming and recent committee hearings</td></tr>
								<tr><td><code>get_hearing_detail</code></td><td>Get full details for a specific hearing</td></tr>
								<tr><td><code>get_hearing_briefing</code></td><td>Generate a data briefing for a hearing</td></tr>
							</tbody>
						</table>
					</div>
				</div>

				<div class="db-card mb-4">
					<div class="db-card-body">
						<h5 class="db-card-title"><i class="bi bi-newspaper me-2" style="color: var(--db-accent);"></i>City Record (CROL)</h5>
						<table class="db-table table table-sm">
							<tbody>
								<tr><td><code>search_notices</code></td><td>Search City Record notices</td></tr>
								<tr><td><code>get_notice_stats</code></td><td>Get notice statistics (last 30 days)</td></tr>
								<tr><td><code>get_recent_events</code></td><td>Get upcoming public events and hearings</td></tr>
							</tbody>
						</table>
					</div>
				</div>

				<div class="db-card mb-4">
					<div class="db-card-body">
						<h5 class="db-card-title"><i class="bi bi-mortarboard me-2" style="color: var(--db-accent);"></i>Schools</h5>
						<table class="db-table table table-sm">
							<tbody>
								<tr><td><code>search_schools</code></td><td>Search public, charter, private and after-school programs</td></tr>
								<tr><td><code>get_school_stats</code></td><td>Get school counts by type and borough</td></tr>
							</tbody>
						</table>
					</div>
				</div>

				<div class="db-card mb-4">
					<div class="db-card-body">
						<h5 class="db-card-title"><i class="bi bi-geo-alt me-2" style="color: var(--db-accent);"></i>Facilities</h5>
						<table class="db-table table table-sm">
							<tbody>
								<tr><td><code>search_facilities</code></td><td>Search city facilities (buildings, parks, offices)</td></tr>
								<tr><td><code>get_facility_types</code></td><td>Get all facility types and their counts</td></tr>
							</tbody>
						</table>
					</div>
				</div>

				<div class="db-card mb-4">
					<div class="db-card-body">
						<h5 class="db-card-title"><i class="bi bi-database me-2" style="color: var(--db-accent);"></i>General</h5>
						<table class="db-table table table-sm">
							<tbody>
								<tr><td><code>get_database_overview</code></td><td>Get summary of all available data</td></tr>
							</tbody>
						</table>
					</div>
				</div>
			</div>
		</div>

		{{-- ───────────────────────── Example Prompts ───────────────────────── --}}
		<div class="row">
			<div class="col-lg-12">
				<div class="db-card mb-4 h-100">
					<div class="db-card-body">
						<h2 class="mb-4"><i class="bi bi-chat-dots me-2" style="color: var(--db-accent);"></i>Example Prompts</h2>
						<p>Once connected, try asking your AI assistant:</p>
						<ul class="db-prose list-unstyled mb-0">
							<li class="mb-2"><i class="bi bi-chevron-right me-2" style="color: var(--db-text-muted);"></i>"How many capital projects does the Department of Parks and Recreation have?"</li>
							<li class="mb-2"><i class="bi bi-chevron-right me-2" style="color: var(--db-text-muted);"></i>"Search for IT contracts with the Department of Education"</li>
							<li class="mb-2"><i class="bi bi-chevron-right me-2" style="color: var(--db-text-muted);"></i>"Find civil service titles related to engineer"</li>
							<li class="mb-2"><i class="bi bi-chevron-right me-2" style="color: var(--db-text-muted);"></i>"What solicitations are currently open?"</li>
							<li class="mb-2"><i class="bi bi-chevron-right me-2" style="color: var(--db-text-muted);"></i>"Get the profile for the Health Department"</li>
							<li class="mb-2"><i class="bi bi-chevron-right me-2" style="color: var(--db-text-muted);"></i>"Show me recent City Record notices about public hearings"</li>
							<li class="mb-2"><i class="bi bi-chevron-right me-2" style="color: var(--db-text-muted);"></i>"Find NYC Council legislation about housing"</li>
							<li class="mb-2"><i class="bi bi-chevron-right me-2" style="color: var(--db-text-muted);"></i>"What are the upcoming Council committee hearings?"</li>
						</ul>
					</div>
				</div>
			</div>
		</div>

		{{-- ───────────────────────── Limits & terms / Technical ───────────────────────── --}}
		<div class="db-eyebrow" style="margin-top: var(--db-space-5);">Limits &amp; terms</div>
		<h2 class="mb-4">Technical Details</h2>

		<div class="db-card mb-4">
			<div class="db-card-body">
				<h5 class="db-card-title"><i class="bi bi-braces me-2" style="color: var(--db-accent);" aria-hidden="true"></i>Example call</h5>
				<p>Tools are invoked with a standard MCP <code>tools/call</code> request and return a text result. For example, <code>search_organizations</code>:</p>
				<div class="codeblock mb-3">
<pre class="mb-0">POST https://api.databook.nyc/mcp
{
  "method": "tools/call",
  "params": {
    "name": "search_organizations",
    "arguments": { "query_text": "parks", "limit": 1 }
  }
}</pre>
				</div>
				<div class="codeblock mb-0">
<pre class="mb-0">Found 1 organization(s) matching 'parks':
- Department of Parks and Recreation (DPR) [ID: 170010846]
  Type: Mayoral Agency</pre>
				</div>
			</div>
		</div>

		<div class="db-card mb-4">
			<div class="db-card-body">
				<h5 class="db-card-title"><i class="bi bi-info-circle me-2" style="color: var(--db-accent);" aria-hidden="true"></i>Usage &amp; data</h5>
				<ul class="db-prose mb-0">
					<li><strong>No key or quota.</strong> The endpoint is public and read-only. It sits behind Cloudflare, so very rapid automated bursts may be briefly rate-limited (HTTP 429); normal interactive use is unaffected.</li>
					<li><strong>Protocol.</strong> MCP revision <code>2025-06-18</code> over Streamable HTTP.</li>
					<li><strong>Freshness.</strong> Tools read the same normalized datasets as this site, refreshed on Databook's regular schedule &mdash; see the <a href="{{ route('about.data') }}">data sources</a> for per-dataset provenance.</li>
					<li><strong>Attribution.</strong> Data originates from official NYC sources and is provided as-is for public use. Verify against the official source of record before relying on it for decisions.</li>
				</ul>
			</div>
		</div>

		<div class="db-card mb-4">
			<div class="db-card-body">
				<div class="row">
					<div class="col-md-4 mb-3 mb-md-0">
						<strong><i class="bi bi-hdd-network me-1" style="color: var(--db-accent);"></i> MCP Endpoint:</strong><br>
						<code>https://api.databook.nyc/mcp</code>
					</div>
					<div class="col-md-4 mb-3 mb-md-0">
						<strong><i class="bi bi-shield-lock me-1" style="color: var(--db-accent);"></i> Authentication:</strong><br>
						None &mdash; public, read-only. Leave OAuth fields empty.
					</div>
					<div class="col-md-4">
						<strong><i class="bi bi-book me-1" style="color: var(--db-accent);"></i> API Documentation:</strong><br>
						<a href="https://api.databook.nyc/docs" target="_blank" rel="noopener">api.databook.nyc/docs</a>
					</div>
				</div>
			</div>
		</div>

		<div class="mt-4">
			<a href="https://api.databook.nyc/docs" target="_blank" rel="noopener" class="db-btn db-btn-primary"><i class="bi bi-book me-1"></i> Full docs</a>
			<a href="https://github.com/wegovnyc" target="_blank" rel="noopener" class="db-btn db-btn-outline ms-2"><i class="bi bi-github me-1"></i> GitHub</a>
		</div>

	</div>
</div>

<script>
function copyField(fieldId) {
	const field = document.getElementById(fieldId);
	navigator.clipboard.writeText(field.value).then(() => {
		const btn = field.nextElementSibling;
		btn.innerHTML = '<i class="bi bi-check2"></i>';
		setTimeout(() => {
			btn.innerHTML = '<i class="bi bi-clipboard"></i>';
		}, 2000);
	});
}

function copyConfig() {
	const configText = `{
  "mcpServers": {
    "databook-nyc": {
      "url": "https://api.databook.nyc/mcp"
    }
  }
}`;
	navigator.clipboard.writeText(configText).then(() => {
		const btn = document.querySelector('.codeblock-copy');
		btn.innerHTML = '<i class="bi bi-check2 me-1"></i>Copied!';
		setTimeout(() => {
			btn.innerHTML = '<i class="bi bi-clipboard me-1"></i>Copy';
		}, 2000);
	});
}

function copyCmd() {
	const pre = document.getElementById('mcp-cmd');
	navigator.clipboard.writeText(pre.innerText).then(() => {
		const btn = pre.parentElement.querySelector('.codeblock-copy');
		btn.innerHTML = '<i class="bi bi-check2 me-1" aria-hidden="true"></i>Copied!';
		setTimeout(() => {
			btn.innerHTML = '<i class="bi bi-clipboard me-1" aria-hidden="true"></i>Copy';
		}, 2000);
	});
}

// Live status badge: reflect the real API health rather than a hardcoded "Online".
(function () {
	const el = document.getElementById('mcpStatus');
	if (!el) return;
	const set = (cls, txt) => {
		el.className = 'db-badge ' + cls;
		el.innerHTML = '<span class="db-dot"></span> ' + txt;
	};
	fetch('https://api.databook.nyc/health', { mode: 'cors' })
		.then(r => (r.ok ? r.json() : null))
		.then(d => set(d && d.status === 'ok' ? 'db-badge-success' : 'db-badge-neutral',
			d && d.status === 'ok' ? 'Online' : 'Status unavailable'))
		.catch(() => set('db-badge-neutral', 'Status unavailable'));
})();
</script>
@endsection
