#!/usr/bin/env python3
"""
Databook MCP Remote Server - ASGI wrapper for Claude Online compatibility.

This script wraps the FastMCP instance in a Starlette application with
OAuth 2.1 discovery endpoints required by Claude Online (Web).

Usage:
    # Run with uvicorn
    uvicorn serve_mcp:app --host 0.0.0.0 --port 8082
    
    # Run directly
    python serve_mcp.py
"""

import secrets
import csv
import io
from contextlib import asynccontextmanager
from typing import Dict

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, HTMLResponse, Response
from starlette.routing import Mount, Route

from mcp_server import mcp, get_logs, clear_logs, set_session_id

# ============================================================================
# OAuth 2.1 Discovery Endpoints (Required for Claude Online)
# ============================================================================

# In-memory client registry for OAuth
registered_clients: Dict[str, dict] = {}


async def oauth_protected_resource(request: Request) -> JSONResponse:
    """RFC 9728: OAuth Protected Resource Metadata."""
    return JSONResponse({
        "resource": f"https://{request.headers.get('host', 'localhost')}/",
        "authorization_servers": [f"https://{request.headers.get('host', 'localhost')}/"],
        "bearer_methods_supported": ["header"]
    })


async def oauth_authorization_server(request: Request) -> JSONResponse:
    """RFC 8414: OAuth Authorization Server Metadata."""
    base_url = f"https://{request.headers.get('host', 'localhost')}"
    return JSONResponse({
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/authorize",
        "token_endpoint": f"{base_url}/token",
        "registration_endpoint": f"{base_url}/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "token_endpoint_auth_methods_supported": ["none"],
        "code_challenge_methods_supported": ["S256"]
    })


async def oauth_register(request: Request) -> JSONResponse:
    """RFC 7591: Dynamic Client Registration."""
    try:
        data = await request.json()
    except:
        data = {}
    
    client_id = secrets.token_urlsafe(16)
    registered_clients[client_id] = {
        "client_name": data.get("client_name", "Unknown"),
        "redirect_uris": data.get("redirect_uris", [])
    }
    
    return JSONResponse({
        "client_id": client_id,
        "client_name": data.get("client_name", "Unknown"),
        "redirect_uris": data.get("redirect_uris", []),
        "grant_types": ["authorization_code"],
        "token_endpoint_auth_method": "none"
    })


async def oauth_authorize(request: Request) -> HTMLResponse:
    """Authorization endpoint - auto-approves for MCP servers."""
    redirect_uri = request.query_params.get("redirect_uri", "")
    state = request.query_params.get("state", "")
    code = secrets.token_urlsafe(32)
    
    # Auto-redirect with authorization code
    return HTMLResponse(
        f'<html><head><meta http-equiv="refresh" content="0;url={redirect_uri}?code={code}&state={state}"></head></html>'
    )


async def oauth_token(request: Request) -> JSONResponse:
    """Token endpoint - returns a simple bearer token."""
    token = secrets.token_urlsafe(32)
    return JSONResponse({
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": 3600
    })


# ============================================================================
# Log Export Endpoints
# ============================================================================

async def get_logs_json(request: Request) -> JSONResponse:
    """Return all stored logs as JSON."""
    logs = get_logs()
    return JSONResponse({
        "count": len(logs),
        "logs": logs
    })


async def get_logs_csv(request: Request) -> Response:
    """Return all stored logs as CSV for Google Sheets import."""
    logs = get_logs()
    
    output = io.StringIO()
    if logs:
        fieldnames = ["timestamp", "session_id", "request_num", "tool_name", "args", "elapsed_ms", "row_count", "error", "result_preview"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for log in logs:
            writer.writerow(log)
    
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=mcp_logs.csv"}
    )


async def clear_logs_endpoint(request: Request) -> JSONResponse:
    """Clear all stored logs."""
    clear_logs()
    return JSONResponse({"status": "cleared"})


# ============================================================================
# Starlette Application
# ============================================================================

# Create admin routes handler
admin_routes = {
    "/admin/logs": ("GET", get_logs_json),
    "/admin/logs/csv": ("GET", get_logs_csv),
    "/admin/logs/clear": ("POST", clear_logs_endpoint),
}

oauth_routes = {
    "/.well-known/oauth-protected-resource": oauth_protected_resource,
    "/.well-known/oauth-authorization-server": oauth_authorization_server,
    "/register": oauth_register,
    "/authorize": oauth_authorize,
    "/token": oauth_token,
}


@asynccontextmanager
async def lifespan(app):
    """Manage MCP session lifecycle for Streamable HTTP."""
    async with mcp.session_manager.run():
        yield


# Get the MCP's streamable HTTP app
mcp_app = mcp.streamable_http_app()


async def combined_app(scope, receive, send):
    """Combined ASGI app that routes admin requests before MCP."""
    if scope["type"] == "lifespan":
        # Delegate lifespan to MCP app
        await mcp_app(scope, receive, send)
        return
    
    path = scope.get("path", "")
    method = scope.get("method", "GET")
    
    # Handle admin routes
    for route_path, (route_method, handler) in admin_routes.items():
        if path == route_path and method == route_method:
            request = Request(scope, receive, send)
            response = await handler(request)
            await response(scope, receive, send)
            return
    
    # Handle OAuth routes
    for route_path, handler in oauth_routes.items():
        if path == route_path:
            request = Request(scope, receive, send)
            response = await handler(request)
            await response(scope, receive, send)
            return
    
    # For MCP requests, extract session ID from headers
    if path.startswith("/mcp"):
        headers = dict(scope.get("headers", []))
        # MCP session ID is sent in the mcp-session-id header
        session_id = headers.get(b"mcp-session-id", b"").decode("utf-8")
        if session_id:
            set_session_id(session_id)
    
    # Fall through to MCP app for all other requests
    await mcp_app(scope, receive, send)


# Wrap with lifespan handler
app = Starlette(
    routes=[Mount("/", app=combined_app)],
    lifespan=lifespan
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8082)
