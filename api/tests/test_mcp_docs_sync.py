"""Guard against MCP tool <-> docs drift.

Two independent drifts have bitten this page before:
  1. The /mcp docs page advertised the wrong tool count / a phantom tool.
  2. Tools were added to the server but never documented.

This test asserts the set of tools registered in api/mcp_server.py (functions
decorated with @mcp.tool) exactly matches the set documented on the public
/mcp page (app/resources/views/mcp.blade.php). It is a pure static check — no
database or running server required — so it runs in CI on every push.

Note: this catches *documentation* drift, not *schema* drift (a tool whose SQL
no longer matches the DB). That class only surfaces against real data — see
scripts/mcp-tool-audit.py, run against prod by the prod-smoke workflow.
"""
import ast
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MCP_SERVER = _REPO_ROOT / "api" / "mcp_server.py"
_MCP_PAGE = _REPO_ROOT / "app" / "resources" / "views" / "mcp.blade.php"


def _registered_tools() -> set[str]:
    """Names of functions decorated with @mcp.tool in mcp_server.py."""
    tree = ast.parse(_MCP_SERVER.read_text())
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            # Matches @mcp.tool(...) and @mcp.tool ; excludes @mcp.prompt, @log_tool_call
            target = dec.func if isinstance(dec, ast.Call) else dec
            if (isinstance(target, ast.Attribute) and target.attr == "tool"
                    and isinstance(target.value, ast.Name) and target.value.id == "mcp"):
                names.add(node.name)
    return names


def _documented_tools() -> set[str]:
    """Tool names documented in the /mcp page's tool tables."""
    html = _MCP_PAGE.read_text()
    return set(re.findall(r"<td><code>([a-z_]+)</code></td>", html))


def test_mcp_page_documents_exactly_the_registered_tools():
    registered = _registered_tools()
    documented = _documented_tools()

    assert registered, "No @mcp.tool functions found — parser or file changed?"
    assert documented, "No tool cells found on the /mcp page — markup changed?"

    undocumented = registered - documented
    phantom = documented - registered
    assert not undocumented, (
        f"Tools registered in mcp_server.py but missing from the /mcp page: "
        f"{sorted(undocumented)}")
    assert not phantom, (
        f"Tools documented on the /mcp page that do not exist in mcp_server.py: "
        f"{sorted(phantom)}")


def test_mcp_page_tool_count_header_matches():
    """The 'Available Tools (N total)' header must equal the real tool count."""
    html = _MCP_PAGE.read_text()
    m = re.search(r"Available Tools \((\d+) total\)", html)
    assert m, "Could not find the 'Available Tools (N total)' header on the /mcp page"
    assert int(m.group(1)) == len(_registered_tools()), (
        f"Header says {m.group(1)} tools but mcp_server.py registers "
        f"{len(_registered_tools())}")
