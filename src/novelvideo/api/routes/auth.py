"""认证端点：登录 / 登出 / 当前用户信息。"""

import logging

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from novelvideo.api.auth import (
    AUTH_COOKIE_NAME,
    get_api_user,
    resolve_auth_cookie_from_request,
)
from novelvideo.ports import get_auth_port
from novelvideo.ports.auth_contract import AuthError
from novelvideo.ports.local.team_auth import TeamPassphraseAuthPort
from novelvideo.shared.runtime_env import cookie_secure as runtime_cookie_secure

router = APIRouter()
logger = logging.getLogger("novelvideo.api.auth")

_COOKIE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60


def _cookie_secure() -> bool:
    return runtime_cookie_secure()


def _set_auth_cookie(response: Response, cookie_value: str) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=cookie_value,
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(),
        max_age=_COOKIE_MAX_AGE_SECONDS,
        path="/",
    )


def _clear_auth_cookie(response: Response) -> None:
    # Mirror the cookie attributes used on set so CDN edges and Safari ITP
    # match it reliably. secure is echoed for the same reason.
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        path="/",
        samesite="lax",
        secure=_cookie_secure(),
    )


@router.post("/auth/login")
async def login(request: Request):
    """Team passphrase login; auto-provisions unknown usernames.

    Returns 404 unless ``ST_TEAM_PASSPHRASE`` activated the team auth port;
    stock CE local mode keeps no login endpoint.
    """
    auth_port = get_auth_port()
    if not isinstance(auth_port, TeamPassphraseAuthPort):
        return JSONResponse({"ok": False, "error": "login disabled"}, status_code=404)
    try:
        body = await request.json()
    except Exception:
        body = {}
    username = str((body or {}).get("username", "")).strip()
    password = str((body or {}).get("password", ""))
    try:
        user, token = await auth_port.login(username, password)
    except AuthError as exc:
        status = 429 if "retry later" in exc.detail else 401
        return JSONResponse(
            {"ok": False, "error": exc.detail or "login failed"}, status_code=status
        )
    response = JSONResponse(
        {
            "ok": True,
            "data": {
                "username": user.username,
                "role": user.role,
                "credit_balance": 0,
                "credential_kind": "browser_session",
            },
        }
    )
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(),
        max_age=_COOKIE_MAX_AGE_SECONDS,
        path="/",
    )
    return response


@router.post("/auth/logout")
async def logout(request: Request):
    """Best-effort revoke the session and always clear the browser cookie."""
    cookie_value = resolve_auth_cookie_from_request(request)
    if cookie_value:
        try:
            await get_auth_port().revoke_session(cookie_value)
        except Exception:
            # Logout is a recovery endpoint. An expired/invalid cookie or a
            # temporarily unavailable auth backend must not prevent the
            # browser from deleting its local credential.
            logger.warning("Failed to revoke session during logout", exc_info=True)

    response = JSONResponse({"ok": True})
    _clear_auth_cookie(response)
    return response


@router.get("/auth/me")
async def me(user: dict = Depends(get_api_user)):
    credit_balance = 0
    user_id = str(user.get("user_id") or user.get("id") or "").strip()
    if user_id:
        from novelvideo.ports.registry import get_port

        balance = await get_port("usage_meter").get_user_credit_balance(user_id)
        credit_balance = balance if balance is not None else 0

    return JSONResponse(
        {
            "ok": True,
            "data": {
                "username": user["username"],
                "role": user["role"],
                "credit_balance": credit_balance,
                "credential_kind": user.get("credential_kind") or "user",
                "current_scope_kind": user.get("current_scope_kind"),
                "current_project_id": user.get("current_project_id"),
                "scopes": user.get("scopes"),
            },
        }
    )
