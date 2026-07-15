#!/usr/bin/env python3
"""Test intro.nyc legislation and council hearing MCP tools against live APIs."""

import asyncio
import os
import sys

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def test_legislation_tools():
    """Test the legislation MCP tools."""
    from mcp_server import (
        get_legislation_detail,
        get_council_member,
        get_recent_legislation,
        get_local_laws,
    )

    print("=" * 60)
    print("Testing intro.nyc Legislation MCP Tools")
    print("=" * 60)

    # Test 1: Get detail for a known bill
    print("\n[1] get_legislation_detail('0001', 2024):")
    try:
        result = await get_legislation_detail("0001", 2024)
        print(result[:600] + "..." if len(result) > 600 else result)
    except Exception as e:
        print(f"ERROR: {e}")

    # Test 2: Get council member profile
    print("\n[2] get_council_member('lincoln-restler'):")
    try:
        result = await get_council_member("lincoln-restler")
        print(result[:500] + "..." if len(result) > 500 else result)
    except Exception as e:
        print(f"ERROR: {e}")

    # Test 3: Get recent legislation
    print("\n[3] get_recent_legislation(2024, limit=3):")
    try:
        result = await get_recent_legislation(2024, limit=3)
        print(result[:600] + "..." if len(result) > 600 else result)
    except Exception as e:
        print(f"ERROR: {e}")

    # Test 4: Get local laws
    print("\n[4] get_local_laws(2024, limit=3):")
    try:
        result = await get_local_laws(2024, limit=3)
        print(result[:600] + "..." if len(result) > 600 else result)
    except Exception as e:
        print(f"ERROR: {e}")


async def test_hearing_tools():
    """Test the council hearing MCP tools."""
    from mcp_server import (
        get_upcoming_hearings,
        get_hearing_detail,
        _extract_themes,
    )

    print("\n" + "=" * 60)
    print("Testing Council Hearing MCP Tools")
    print("=" * 60)

    # Test 5: Get upcoming hearings
    print("\n[5] get_upcoming_hearings(days_ahead=14, days_behind=30, limit=5):")
    try:
        result = await get_upcoming_hearings(days_ahead=14, days_behind=30, limit=5)
        print(result[:800] + "..." if len(result) > 800 else result)
    except Exception as e:
        print(f"ERROR: {e}")

    # Test 6: Get hearing detail for a known event
    print("\n[6] get_hearing_detail('22144', year=2026):")
    try:
        result = await get_hearing_detail("22144", year=2026)
        print(result[:800] + "..." if len(result) > 800 else result)
    except Exception as e:
        print(f"ERROR: {e}")

    # Test 7: Theme extraction
    print("\n[7] _extract_themes (unit test):")
    test_titles = [
        "A Local Law to amend the administrative code in relation to street safety",
        "Guidance relating to the child care program permitting process",
        "A Law in relation to housing preservation and development",
    ]
    themes = _extract_themes(test_titles)
    print(f"  Input titles: {len(test_titles)}")
    print(f"  Themes found: {len(themes)}")
    for t in themes:
        print(f"    - {t['label']} (agencies: {t['agencies']})")
    assert len(themes) > 0, "Expected at least one theme extracted"
    print("  ✅ Theme extraction passed!")


async def test_hearing_briefing():
    """Test the hearing briefing tool (requires DB connection)."""
    from mcp_server import get_hearing_briefing

    print("\n" + "=" * 60)
    print("Testing Hearing Briefing (requires DB)")
    print("=" * 60)

    # Test 8: Hearing briefing for health committee hearing
    print("\n[8] get_hearing_briefing('22144', year=2026):")
    try:
        result = await get_hearing_briefing("22144", year=2026)
        print(result[:1200] + "..." if len(result) > 1200 else result)
        # Verify it has the expected structure
        assert "Hearing Data Brief" in result, "Expected 'Hearing Data Brief' header"
        assert "Bills Under Consideration" in result, "Expected bills section"
        print("\n  ✅ Hearing briefing structure validated!")
    except Exception as e:
        print(f"ERROR (may be expected without DB): {e}")


async def main():
    """Run all tests."""
    await test_legislation_tools()
    await test_hearing_tools()

    # Only run DB-dependent test if we can connect
    if os.getenv("POSTGRES_HOST") or os.getenv("DATABASE_URL"):
        await test_hearing_briefing()
    else:
        print("\n⚠️  Skipping hearing briefing test (no DB connection)")
        print("  Set POSTGRES_HOST to enable")

    print("\n" + "=" * 60)
    print("All tests complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
