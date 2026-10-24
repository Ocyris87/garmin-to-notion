"""Garmin and Notion client initialization."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

from garminconnect import (
    Garmin as GarminClient,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)
from notion_client import Client as NotionClient

from garmin_to_notion.config import Settings

logger = logging.getLogger(__name__)

TOKENSTORE_DIR = Path(os.getenv("GARMIN_TOKENSTORE", "~/.garminconnect")).expanduser()


@dataclass
class Clients:
    garmin: GarminClient
    notion: NotionClient


def _seed_tokens_from_env() -> None:
    """If GARMIN_TOKENS_JSON is provided via environment and not yet on disk, write it."""
    raw = (os.getenv("GARMIN_TOKENS_JSON") or os.getenv("GARMIN_TOKENS") or "").strip()
    if not raw:
        return
    token_file = TOKENSTORE_DIR / "garmin_tokens.json"
    if not token_file.exists():
        try:
            # Validate JSON if possible
            if raw.startswith("{") and raw.endswith("}"):
                json.loads(raw)  # verify syntax
                TOKENSTORE_DIR.mkdir(parents=True, exist_ok=True)
                token_file.write_text(raw)
                token_file.chmod(0o600)
                logger.info("Seeded tokens to %s from environment secret", token_file)
        except Exception as e:
            logger.warning("Could not seed tokens from environment: %s", e)


def get_garmin_client(
    email: str | None = None,
    password: str | None = None,
    tokenstore: str | Path | None = None,
) -> GarminClient:
    """Return an authenticated Garmin client with token persistence."""
    store = Path(tokenstore).expanduser() if tokenstore else TOKENSTORE_DIR
    store.mkdir(parents=True, exist_ok=True)

    client = GarminClient(email, password)
    client.login(str(store))
    return client


def init_clients(settings: Settings) -> Clients:
    """Initialize and authenticate both Garmin and Notion clients.

    Uses garminconnect >= 0.3.x DI OAuth2 Bearer token flow with token caching
    in ~/.garminconnect (or GARMIN_TOKENSTORE).
    """
    logger.info("Authenticating with Garmin Connect...")

    TOKENSTORE_DIR.mkdir(parents=True, exist_ok=True)
    _seed_tokens_from_env()

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            garmin = GarminClient(settings.garmin_email, settings.garmin_password)
            garmin.login(str(TOKENSTORE_DIR))
            display = getattr(garmin, "display_name", None) or "authenticated user"
            logger.info("Garmin auth successful (user: %s)", display)
            return Clients(garmin=garmin, notion=NotionClient(auth=settings.notion_token))
        except (GarminConnectTooManyRequestsError, Exception) as e:
            err_msg = str(e)
            if attempt < max_retries and ("429" in err_msg or "Too many" in err_msg):
                wait = 30 * attempt
                logger.warning("Rate limited (attempt %d/%d), waiting %ds...", attempt, max_retries, wait)
                time.sleep(wait)
            else:
                logger.error("Failed to authenticate (attempt %d/%d): %s", attempt, max_retries, e)
                if attempt == max_retries:
                    raise SystemExit(1) from e


def init_notion_only(settings: Settings) -> NotionClient:
    """Initialize only the Notion client (for tools that don't need Garmin)."""
    return NotionClient(auth=settings.notion_token)
