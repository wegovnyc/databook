#!/usr/bin/env python3
"""Quick test of MCP server tools against production database via SSH tunnel."""

import asyncio
import os
import sys

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set environment for SSH tunnel
os.environ['DB_HOST'] = 'localhost'
os.environ['DB_PORT'] = '15432'  # SSH tunnel port
os.environ['DB_NAME'] = 'databook'
os.environ['DB_USER'] = 'postgres'
os.environ['DB_PASSWORD'] = ''  # Usually empty for local trust auth

async def test_tools():
    """Test the primary MCP tools."""
    # Import after setting env
    from mcp_server import (
        get_database_overview,
        search_organizations,
        search_civil_titles,
        get_notice_stats,
        search_capital_projects
    )
    
    print("=" * 60)
    print("Testing Databook MCP Server Tools")
    print("=" * 60)
    
    # Test 1: Database Overview
    print("\n[1] get_database_overview():")
    try:
        result = await get_database_overview()
        print(result[:500] + "..." if len(result) > 500 else result)
    except Exception as e:
        print(f"ERROR: {e}")
    
    # Test 2: Search Organizations
    print("\n[2] search_organizations('Parks'):")
    try:
        result = await search_organizations("Parks", limit=3)
        print(result[:400] + "..." if len(result) > 400 else result)
    except Exception as e:
        print(f"ERROR: {e}")
    
    # Test 3: Search Titles
    print("\n[3] search_civil_titles('analyst'):")
    try:
        result = await search_civil_titles("analyst", limit=3)
        print(result[:400] + "..." if len(result) > 400 else result)
    except Exception as e:
        print(f"ERROR: {e}")
    
    # Test 4: Notice Stats
    print("\n[4] get_notice_stats():")
    try:
        result = await get_notice_stats()
        print(result[:400] + "..." if len(result) > 400 else result)
    except Exception as e:
        print(f"ERROR: {e}")
    
    # Test 5: Capital Projects
    print("\n[5] search_capital_projects('park'):")
    try:
        result = await search_capital_projects("park", limit=3)
        print(result[:400] + "..." if len(result) > 400 else result)
    except Exception as e:
        print(f"ERROR: {e}")
    
    print("\n" + "=" * 60)
    print("Testing complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_tools())
