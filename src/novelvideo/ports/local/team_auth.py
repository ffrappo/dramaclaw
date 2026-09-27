"""Team passphrase auth port: shared-secret multi-user access for CE deploys.

CE ships as single-user (``FileAuthPort``: any visitor is the local owner).
That is fine on a loopback desktop and unacceptable on a team-facing HTTPS
deployment. This module provides the lightest secure alternative with no email
infrastructure and no frontend changes:

- ``ST_TEAM_PASSPHRASE`` env enables the port at registration time.
- The built-in login page (``POST /api/v1/auth/login``) asks for username and
  password. The password is the shared team passphrase.
- An unknown username plus the correct passphrase auto-provisions the account
  (requirement: new team members get an account on first use).
- Sessions are opaque random tokens; only their SHA-256 digest is stored, with
  a 7-day expiry, revocable via the stock logout endpoint.
- Failed logins are rate limited per username in process (fixed window).

Projects stay a shared workspace: the CE project registry keys on owner
``local`` for listing, so every team member sees every project and new
projects record the creating member's username for attribution.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from pathlib import Path

from novelvideo.ports.auth_contract import (
    DEFAULT_EXTERNAL_AGENT_SCOPES,
    AuthenticatedUser,
    AuthError,
    AuthFailureReason,
)

_TEAM_PASSPHRASE_ENV = "ST_TEAM_PASSPHRASE"
_TEAM_PROVISIONING_SECRET_ENV = "ST_TEAM_PROVISIONING_SECRET"
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60
_USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,31}$")
_LOGIN_WINDOW_SECONDS = 300
_LOGIN_MAX_FAILURES = 10


def team_passphrase() -> str:
    """Return the configured passphrase, or an empty string when disabled."""
    from novelvideo.shared.runtime_env import _load_env

    _load_env()
    return os.environ.get(_TEAM_PASSPHRASE_ENV, "").strip()


def team_auth_enabled() -> bool:
    return bool(team_passphrase())


def team_provisioning_secret() -> str:
    """Return the server-to-server installer secret, never the team passphrase."""
    from novelvideo.shared.runtime_env import _load_env

    _load_env()
    return os.environ.get(_TEAM_PROVISIONING_SECRET_ENV, "").strip()


def _db_path() -> Path:
    from novelvideo import config

    return Path(config.STATE_DIR) / "local" / "team_auth.db"


class _LoginRateLimiter:
    """Fixed-window per-username failure counter, in process."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._failures: dict[str, list[float]] = {}

    def _prune(self, username: str, now: float) -> list[float]:
        window = self._failures.get(username, [])
        return [ts for ts in window if now - ts < _LOGIN_WINDOW_SECONDS]

    async def check(self, username: str) -> None:
        async with self._lock:
            now = time.monotonic()
            if len(self._prune(username, now)) >= _LOGIN_MAX_FAILURES:
                raise AuthError(
                    AuthFailureReason.INVALID,
                    "too many failed logins for this username, retry later",
                )

    async def record_failure(self, username: str) -> None:
        async with self._lock:
            now = time.monotonic()
            window = self._prune(username, now)
            window.append(now)
            self._failures[username] = window


class TeamPassphraseAuthPort:
    """Browser-session auth backed by STATE_DIR/local/team_auth.db."""

    def __init__(self) -> None:
        self._limiter = _LoginRateLimiter()
        self._init_lock = asyncio.Lock()
        self._schema_ready = False

    # -- schema ---------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        path = _db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), timeout=10, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    async def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        async with self._init_lock:
            if self._schema_ready:
                return
            conn = self._connect()
            try:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS team_users (
                        username TEXT PRIMARY KEY,
                        created_at TEXT NOT NULL,
                        last_login_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS team_sessions (
                        token_hash TEXT PRIMARY KEY,
                        username TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        expires_at INTEGER NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_team_sessions_username
                        ON team_sessions(username);
                    CREATE TABLE IF NOT EXISTS team_agent_tokens (
                        token_hash TEXT PRIMARY KEY,
                        username TEXT NOT NULL UNIQUE,
                        created_at TEXT NOT NULL,
                        last_used_at TEXT NOT NULL
                    );
                    """
                )
                conn.commit()
                self._schema_ready = True
            finally:
                conn.close()

    # -- login ----------------------------------------------------------
    async def login(self, username: str, password: str) -> tuple[AuthenticatedUser, str]:
        """Verify the shared passphrase, auto-provisioning unknown usernames.

        Returns the user and the raw session token (caller sets the cookie).
        """
        from datetime import datetime, timezone

        if not _USERNAME_RE.match(username or ""):
            raise AuthError(AuthFailureReason.INVALID, "invalid username")
        await self._limiter.check(username)
        if not password or not hmac.compare_digest(password, team_passphrase()):
            await self._limiter.record_failure(username)
            raise AuthError(AuthFailureReason.INVALID, "wrong username or passphrase")

        now_iso = datetime.now(timezone.utc).isoformat()
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        await self._ensure_schema()
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO team_users(username, created_at, last_login_at)
                VALUES (?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET last_login_at = excluded.last_login_at
                """,
                (username, now_iso, now_iso),
            )
            conn.execute(
                """
                INSERT INTO team_sessions(token_hash, username, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (token_hash, username, now_iso, int(time.time()) + SESSION_TTL_SECONDS),
            )
            conn.execute(
                "DELETE FROM team_sessions WHERE expires_at < ?",
                (int(time.time()),),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return AuthenticatedUser(id=username, username=username, role="owner"), token

    async def provision_agent_token(
        self, username: str, existing_token: str | None = None
    ) -> str:
        """Create or reconcile one hashed installer credential for a team user.

        The caller is the trusted Fornace identity bridge. An update sends its
        locally stored token so a valid credential remains stable. A missing or
        invalid local credential rotates the server row and returns a new value.
        """
        from datetime import datetime, timezone

        if not _USERNAME_RE.match(username or ""):
            raise AuthError(AuthFailureReason.INVALID, "invalid username")
        await self._ensure_schema()
        now_iso = datetime.now(timezone.utc).isoformat()
        existing_hash = (
            hashlib.sha256(existing_token.encode("utf-8")).hexdigest()
            if existing_token
            else ""
        )
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            if existing_hash:
                row = conn.execute(
                    """
                    SELECT username FROM team_agent_tokens
                    WHERE token_hash = ?
                    """,
                    (existing_hash,),
                ).fetchone()
                if row is not None and hmac.compare_digest(str(row[0]), username):
                    conn.execute(
                        "UPDATE team_agent_tokens SET last_used_at = ? WHERE token_hash = ?",
                        (now_iso, existing_hash),
                    )
                    conn.execute(
                        """
                        INSERT INTO team_users(username, created_at, last_login_at)
                        VALUES (?, ?, ?)
                        ON CONFLICT(username) DO UPDATE SET last_login_at = excluded.last_login_at
                        """,
                        (username, now_iso, now_iso),
                    )
                    conn.commit()
                    return existing_token

            token = f"dfa_{secrets.token_urlsafe(32)}"
            token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
            conn.execute(
                """
                INSERT INTO team_users(username, created_at, last_login_at)
                VALUES (?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET last_login_at = excluded.last_login_at
                """,
                (username, now_iso, now_iso),
            )
            conn.execute("DELETE FROM team_agent_tokens WHERE username = ?", (username,))
            conn.execute(
                """
                INSERT INTO team_agent_tokens(
                    token_hash, username, created_at, last_used_at
                ) VALUES (?, ?, ?, ?)
                """,
                (token_hash, username, now_iso, now_iso),
            )
            conn.commit()
            return token
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def verify_agent_token(self, token: str) -> dict:
        """Verify a persistent team credential issued by the installer bridge."""
        if not token.startswith("dfa_"):
            raise AuthError(AuthFailureReason.INVALID, "team agent token not found")
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        await self._ensure_schema()
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT username FROM team_agent_tokens WHERE token_hash = ?",
                (token_hash,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise AuthError(AuthFailureReason.INVALID, "team agent token not found")
        username = str(row[0])
        return {
            **AuthenticatedUser(
                id=username, username=username, role="owner"
            ).to_legacy_dict(),
            "credential_kind": "team_agent",
            "scopes": list(DEFAULT_EXTERNAL_AGENT_SCOPES),
            "current_scope_kind": "team",
            "current_project_id": None,
        }

    # -- port interface ---------------------------------------------------
    async def verify_session(self, raw_cookie: str | None) -> dict:
        if not raw_cookie:
            raise AuthError(AuthFailureReason.MISSING, "missing session cookie")
        token_hash = hashlib.sha256(raw_cookie.encode("utf-8")).hexdigest()
        await self._ensure_schema()
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT username, expires_at FROM team_sessions WHERE token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise AuthError(AuthFailureReason.INVALID, "unknown session")
        username, expires_at = row
        if int(expires_at) < int(time.time()):
            await self._delete_session(token_hash)
            raise AuthError(AuthFailureReason.EXPIRED, "session expired")
        user = AuthenticatedUser(id=username, username=username, role="owner")
        return user.to_legacy_dict()

    async def revoke_session(self, raw_cookie: str) -> None:
        if not raw_cookie:
            return
        await self._delete_session(
            hashlib.sha256(raw_cookie.encode("utf-8")).hexdigest()
        )

    async def _delete_session(self, token_hash: str) -> None:
        await self._ensure_schema()
        conn = self._connect()
        try:
            conn.execute("DELETE FROM team_sessions WHERE token_hash = ?", (token_hash,))
            conn.commit()
        finally:
            conn.close()
