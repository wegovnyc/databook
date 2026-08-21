"""Guard: the MCP server's `mcp` dependency must stay below 2.0.

⚠⚠ THE INCIDENT THIS EXISTS TO PREVENT, 2026-08-18. `api/Dockerfile.mcp` ran a
bare `pip install mcp`. The package released 2.0.0, which REMOVED
`mcp.server.fastmcp` — imported twice by mcp_server.py — and the next full
rebuild picked it up. `databook-mcp` crash-looped **961 times** from 00:53Z and
`api.databook.nyc/mcp`, a published product surface with 40 tools, served **502
for ~16.5 hours**.

⚠ NOTHING ALERTED, for two compounding reasons worth remembering:
  * the container has `restart: unless-stopped`, so it is perpetually "Restarting"
    rather than "Exited" — a crash loop reads as liveness to anything watching
    container state;
  * `MCP Tool Audit (prod)`, the CI job written to call all 40 tools and fail on
    any exception, is gated `if: github.event_name == 'workflow_dispatch'`. The
    guard for exactly this defect had never run on its own.

An unpinned dependency in a Dockerfile that rebuilds from PyPI is a scheduled
outage with no date on it.
"""
import io
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
DOCKERFILE = os.path.join(ROOT, 'api/Dockerfile.mcp')
MCP_SERVER = os.path.join(ROOT, 'api/mcp_server.py')


def _read(path):
    with io.open(path, encoding='utf-8') as fh:
        return fh.read()


def _install_args():
    """The pip install arguments, with COMMENTS STRIPPED.

    ⚠ Comments are stripped because the block above the install carries a long
    explanation that names `mcp`, `2.0` and `fastmcp`. A scan that reads prose as
    code reports problems that are not there — this repo has paid for that
    mistake three times, most recently earlier today.
    """
    src = _read(DOCKERFILE)
    code = '\n'.join(l for l in src.splitlines() if not l.lstrip().startswith('#'))
    m = re.search(r'RUN pip install[^\n]*((?:\n[^\n]*)*?)(?=\n[A-Z]{2,}|\Z)', code)
    assert m, "could not find the pip install block in Dockerfile.mcp"
    body = m.group(0)
    args = re.findall(r"['\"]?([A-Za-z0-9_.\-]+(?:[<>=!,][^\s'\"\\]+)*)['\"]?",
                      body.replace('\\', ' '))
    return body, [a for a in args if a not in ('RUN', 'pip', 'install', 'no-cache-dir')]


def test_the_mcp_package_is_pinned_below_2():
    """2.x removed `mcp.server.fastmcp`; the code imports it."""
    body, _args = _install_args()
    m = re.search(r"mcp(?P<spec>[<>=!,\d.]*)", body)
    assert m, "the mcp requirement vanished from Dockerfile.mcp"
    spec = m.group('spec')
    assert spec, (
        "`mcp` is INSTALLED UNPINNED again. It released 2.0.0, which removed "
        "mcp.server.fastmcp, and the next rebuild took the MCP server down for "
        "16.5 hours.")
    assert re.search(r'<\s*2', spec), (
        f"`mcp` is pinned as '{spec}' with no upper bound below 2.0 — 2.x does "
        "not provide mcp.server.fastmcp")


def test_the_imports_that_2x_removed_are_still_the_ones_we_depend_on():
    """Pins WHY the bound exists. If mcp_server.py ever stops importing
    fastmcp, this guard's reason is gone and someone should re-decide the bound
    rather than cargo-culting it."""
    src = _read(MCP_SERVER)
    assert 'from mcp.server.fastmcp import FastMCP' in src, (
        "mcp_server.py no longer imports FastMCP — the <2 bound may no longer be "
        "needed; re-decide it rather than leaving it unexplained")
    assert 'from mcp.server.fastmcp.server import' in src, \
        "mcp_server.py no longer imports from mcp.server.fastmcp.server"


def test_the_guard_can_see_a_real_unpinned_dependency():
    """⚠ ASSERT THE SCANNER WORKS. A parser that finds nothing passes every
    other test in this file vacuously. The five siblings are genuinely unpinned,
    so if the parser cannot see them it is not reading the install block at all.
    """
    _body, args = _install_args()
    bare = [a for a in args if not re.search(r'[<>=]', a)]
    assert len(args) >= 5, f"only parsed {len(args)} install args: {args}"
    assert bare, (
        "the parser found no unpinned args at all — either everything is now "
        "pinned (good, update this test) or the parser is broken (likelier)")
