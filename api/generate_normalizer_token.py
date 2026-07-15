#!/usr/bin/env python3
"""
Generate a long-lived API token with write scope for the normalizer service.
This token should be added to the normalizer's _config.php as API_TOKEN.

Usage (on production API server):
    docker exec databook-api python3 generate_normalizer_token.py
"""

import datetime
from fastapi_login import LoginManager

# Must match the SECRET in main.py
SECRET = "your-secret-key"
TOKEN_URL = "/login"

manager = LoginManager(SECRET, TOKEN_URL, use_cookie=False, use_header=True, default_expiry=datetime.timedelta(hours=1))

# Generate a token that expires in 10 years with read+write scopes
token = manager.create_access_token(
    data={'sub': 'normalizer-service'},
    expires=datetime.timedelta(days=3650),  # 10 years
    scopes=['read', 'write']
)

print("=" * 60)
print("NORMALIZER API TOKEN (10-year validity)")
print("=" * 60)
print()
print(token)
print()
print("=" * 60)
print("Add this to normalizer _config.php:")
print("  define('API_TOKEN', '" + token + "');")
print("=" * 60)
