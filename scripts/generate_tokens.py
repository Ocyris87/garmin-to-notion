"""Generate Garmin OAuth tokens locally and output JSON string for GitHub secret.

Usage:
    python scripts/generate_tokens.py

Reads GARMIN_EMAIL and GARMIN_PASSWORD from the environment or .env file,
prompting for any missing credentials.
Prompts for an MFA verification code when Garmin requires one.
Outputs the tokens JSON string to set as the GARMIN_TOKENS_JSON GitHub secret.
"""

import json
import os
import sys
from getpass import getpass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

email = os.getenv("GARMIN_EMAIL") or input("Garmin email: ").strip()
password = os.getenv("GARMIN_PASSWORD") or getpass("Garmin password: ")

if not email or not password:
    print("Error: Garmin email and password are required.")
    sys.exit(1)

from garminconnect import Garmin

tokenstore = Path("~/.garminconnect").expanduser()
tokenstore.mkdir(parents=True, exist_ok=True)

garmin = Garmin(
    email, password, prompt_mfa=lambda: input("Garmin MFA code: ").strip()
)

print(f"Logging in as {email}...")
garmin.login(str(tokenstore))
print("Login successful!")

token_file = tokenstore / "garmin_tokens.json"
if token_file.exists():
    token_str = token_file.read_text().strip()
    print(f"\nTokens saved locally to {token_file}")
    print("\nIf GitHub Actions encounters 429 rate limiting on first run,")
    print("copy the following content into GitHub Secret 'GARMIN_TOKENS_JSON':")
    print("=" * 60)
    print(token_str)
    print("=" * 60)
