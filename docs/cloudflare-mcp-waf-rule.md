# Cloudflare rule for the MCP endpoint (reference — NOT currently applied)

> Status as of 2026-07-06: **Not needed / not applied.** The MCP endpoint
> `https://api.databook.nyc/mcp` works for every client type tested — browser
> and non-browser (`python-httpx`, `node-fetch`, `mcp-python`, `OpenAI/*`,
> `curl`, and no-UA all complete the handshake with HTTP 200). This document is
> kept only so the rule is ready if a future tightening of Cloudflare bot
> protection ever starts blocking MCP clients, or if MCP clients begin hitting
> rate limits (HTTP 429).

## Why this might be needed later

- `api.databook.nyc` sits behind Cloudflare. Infra docs note a bot rule that
  "403s non-browser UAs" — it currently does **not** apply to `/mcp`, but MCP
  clients are inherently non-browser automated agents, so if Bot Fight Mode /
  managed challenges are ever tightened on this zone they could start catching
  legitimate MCP traffic.
- Cloudflare rate-limiting returns 429 on rapid bursts (this is what the
  automated prod-smoke Playwright run trips). Normal MCP tool-calling is
  low-volume per user and won't hit default limits, but heavy usage could.

## 1. WAF custom rule — skip bot protection for the MCP endpoint

Dashboard: **Security → WAF → Custom rules → Create rule**

- **Rule name:** `Allow MCP endpoint`
- **Expression** (use "Edit expression"):

  ```
  (http.host eq "api.databook.nyc" and (http.request.uri.path eq "/mcp" or starts_with(http.request.uri.path, "/mcp/")))
  ```

- **Action:** `Skip`
- **Skip components:** check **Browser Integrity Check**; under "More components
  to skip" enable **Super Bot Fight Mode** (if shown on the plan).
- **Placement:** put it **first** — custom rules run top-down and a Skip must be
  evaluated before any block rule.

Leave **WAF Managed Rules ON** (do not skip them): JSON-RPC MCP traffic should
not trip them, and they still protect the endpoint. Only add "All managed rules"
to the skip list if legitimate MCP calls are later seen blocked with a WAF event.

**Scoping note:** this targets only `api.databook.nyc/mcp` (the real endpoint).
It deliberately does NOT touch `databook.nyc/mcp`, which is the public docs page
and should keep normal browser protections.

## 2. Rate-limiting relaxation (only if MCP clients get 429s)

Dashboard: **Security → WAF → Rate limiting rules**

- Exclude the endpoint from an existing global rule by appending to its match:

  ```
  and not (http.host eq "api.databook.nyc" and starts_with(http.request.uri.path, "/mcp"))
  ```

- Or create a dedicated, more generous rule scoped to
  `(http.host eq "api.databook.nyc" and starts_with(http.request.uri.path, "/mcp"))`
  with a high per-IP threshold (e.g. 300 requests / 1 min). Bursty but low-volume
  MCP usage stays under it while abuse is still stopped.

Skip this piece unless throttling is actually observed.

## 3. Terraform equivalent (for the `databook_infra` repo)

```hcl
resource "cloudflare_ruleset" "mcp_allow" {
  zone_id = var.databook_zone_id
  name    = "Allow MCP endpoint"
  kind    = "zone"
  phase   = "http_request_firewall_custom"

  rules {
    ref         = "allow_mcp_skip"
    description = "Skip bot protection for the api.databook.nyc/mcp endpoint"
    expression  = "(http.host eq \"api.databook.nyc\" and (http.request.uri.path eq \"/mcp\" or starts_with(http.request.uri.path, \"/mcp/\")))"
    action      = "skip"
    action_parameters {
      phases   = ["http_ratelimit"] # skip rate-limiting rules
      products = ["bic"]            # Browser Integrity Check; SBFM added via UI if applicable
    }
    logging { enabled = true }
  }
}
```

The exact `products`/`phases` values depend on the plan (Bot Fight vs Super Bot
Fight Mode). If Terraform errors on a product name, do the skip toggles in the UI
and keep Terraform for just the rate-limit phase.

## 4. Sanity check after applying

It works today, so the goal after applying is to confirm nothing broke:

```bash
curl -sS -X POST https://api.databook.nyc/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"c","version":"1"}}}'
```

Expect HTTP `200` with a `"serverInfo"` block (not a Cloudflare challenge page).
For a full check, `scripts/mcp-tool-audit.py` exercises all 40 tools.
