"""Invite-only email OTP authentication and user-scoped Supabase REST access."""

from __future__ import annotations

from collections.abc import Mapping
import re
import time
from typing import Any

import requests
import streamlit as st


AUTH_SESSION_KEY = "market_brief_auth_session"
PENDING_EMAIL_KEY = "market_brief_pending_email"
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class UserAccessError(ValueError):
    """Safe-to-display authentication or database error."""


def supabase_config() -> dict[str, str] | None:
    try:
        settings = st.secrets.get("supabase", {})
    except Exception:
        return None
    if not isinstance(settings, Mapping):
        return None
    url = str(settings.get("url", "")).strip().rstrip("/")
    api_key = str(settings.get("anon_key", "")).strip()
    if not url.startswith("https://") or not api_key:
        return None
    return {"url": url, "api_key": api_key}


def _response_json(response: requests.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        data = {}
    return data if isinstance(data, dict) else {}


def _error_message(data: dict[str, Any], fallback: str) -> str:
    message = data.get("msg") or data.get("message") or data.get("error_description") or data.get("error")
    if isinstance(message, str) and message.strip():
        return message.strip()[:240]
    return fallback


def _auth_request(path: str, payload: dict[str, Any], *, params: dict[str, str] | None = None, access_token: str | None = None) -> dict[str, Any]:
    config = supabase_config()
    if config is None:
        raise UserAccessError("User sign-in is not configured yet.")
    headers = {"apikey": config["api_key"], "Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    try:
        response = requests.post(
            f"{config['url']}/auth/v1/{path.lstrip('/')}",
            params=params,
            json=payload,
            headers=headers,
            timeout=20,
        )
    except requests.RequestException as error:
        raise UserAccessError("The sign-in service is unavailable. Try again shortly.") from error
    data = _response_json(response)
    if not response.ok:
        raise UserAccessError(_error_message(data, "The sign-in request could not be completed."))
    return data


def send_login_code(email: str) -> None:
    normalized_email = email.strip().lower()
    if not EMAIL_PATTERN.fullmatch(normalized_email):
        raise UserAccessError("Enter a valid email address.")
    _auth_request("otp", {"email": normalized_email, "create_user": False})


def _session_from_response(data: dict[str, Any]) -> dict[str, Any]:
    user = data.get("user") or {}
    access_token = str(data.get("access_token") or "")
    refresh_token = str(data.get("refresh_token") or "")
    user_id = str(user.get("id") or "")
    email = str(user.get("email") or "")
    if not access_token or not refresh_token or not user_id or not email:
        raise UserAccessError("The sign-in response was incomplete. Request a new code and try again.")
    expires_in = int(data.get("expires_in") or 3600)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": int(time.time()) + max(60, expires_in),
        "user_id": user_id,
        "email": email,
    }


def verify_login_code(email: str, code: str) -> dict[str, Any]:
    normalized_email = email.strip().lower()
    normalized_code = code.strip()
    if not EMAIL_PATTERN.fullmatch(normalized_email) or not normalized_code:
        raise UserAccessError("Enter the email address and one-time code.")
    response = _auth_request("verify", {"email": normalized_email, "token": normalized_code, "type": "email"})
    return _session_from_response(response)


def _refresh_session(session: dict[str, Any]) -> dict[str, Any]:
    response = _auth_request(
        "token",
        {"refresh_token": session["refresh_token"]},
        params={"grant_type": "refresh_token"},
    )
    return _session_from_response(response)


def current_user_session() -> dict[str, Any] | None:
    session = st.session_state.get(AUTH_SESSION_KEY)
    if not isinstance(session, dict):
        return None
    if int(session.get("expires_at", 0)) <= int(time.time()) + 60:
        try:
            session = _refresh_session(session)
        except (UserAccessError, KeyError, TypeError, ValueError):
            st.session_state.clear()
            return None
        st.session_state[AUTH_SESSION_KEY] = session
    return session


def logout_user() -> None:
    session = st.session_state.get(AUTH_SESSION_KEY)
    if isinstance(session, dict) and session.get("access_token"):
        try:
            _auth_request("logout", {}, access_token=str(session["access_token"]))
        except UserAccessError:
            pass
    # Clear widgets as well as the token so a later user on this browser session
    # cannot inherit another person's selections or unsaved form values.
    st.session_state.clear()


def _complete_login() -> None:
    email = str(st.session_state.get(PENDING_EMAIL_KEY, ""))
    code = str(st.session_state.get("login_otp_code", ""))
    try:
        session = verify_login_code(email, code)
    except UserAccessError as error:
        st.session_state["login_error"] = str(error)
        return
    # This runs as a form callback, before Streamlit instantiates widgets again.
    # Clearing here removes the OTP and any stale state from a previous user.
    st.session_state.clear()
    st.session_state[AUTH_SESSION_KEY] = session


def render_access_gate() -> dict[str, Any] | None:
    """Render an invite-only email-code sign-in and return the current session."""
    if supabase_config() is None:
        st.markdown('<div class="eyebrow">Private workspace</div>', unsafe_allow_html=True)
        st.title("Account setup required")
        st.info("This dashboard is locked until Supabase Auth and the per-user database are configured. Follow USER_SETUP.md, then add the project URL and publishable key to Streamlit secrets.")
        return None

    session = current_user_session()
    if session:
        return session

    st.markdown('<div class="eyebrow">Private workspace</div>', unsafe_allow_html=True)
    st.title("Sign in to Market Brief")
    st.caption("Access is by invitation. Request a one-time code using the email address added by the workspace owner.")

    pending_email = str(st.session_state.get(PENDING_EMAIL_KEY, ""))
    if not pending_email:
        with st.form("request_login_code"):
            email = st.text_input("Email address", autocomplete="email")
            request_code = st.form_submit_button("Send sign-in code", type="primary", use_container_width=True)
        if request_code:
            try:
                send_login_code(email)
                st.session_state[PENDING_EMAIL_KEY] = email.strip().lower()
                st.success("If this email belongs to an invited account, a sign-in code will arrive shortly.")
                st.rerun()
            except UserAccessError as error:
                st.error(str(error))
        return None

    if error_message := st.session_state.pop("login_error", None):
        st.error(str(error_message))
    st.info(f"Enter the one-time code sent to **{pending_email}**.")
    with st.form("verify_login_code"):
        st.text_input("One-time code", max_chars=12, autocomplete="one-time-code", key="login_otp_code")
        st.form_submit_button("Verify and sign in", type="primary", use_container_width=True, on_click=_complete_login)

    action_cols = st.columns(2)
    with action_cols[0]:
        if st.button("Send a new code", use_container_width=True):
            try:
                send_login_code(pending_email)
                st.success("If this email belongs to an invited account, a new code will arrive shortly.")
            except UserAccessError as error:
                st.error(str(error))
    with action_cols[1]:
        if st.button("Use a different email", use_container_width=True):
            st.session_state.pop(PENDING_EMAIL_KEY, None)
            st.rerun()
    return None


def supabase_data_request(
    method: str,
    path: str,
    access_token: str,
    *,
    params: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
) -> Any:
    """Make a user-token-scoped PostgREST request; RLS is enforced by Supabase."""
    config = supabase_config()
    if config is None:
        raise UserAccessError("User storage is not configured yet.")
    headers = {
        "apikey": config["api_key"],
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        response = requests.request(
            method.upper(),
            f"{config['url']}/rest/v1/{path.lstrip('/')}",
            params=params,
            json=payload,
            headers=headers,
            timeout=25,
        )
    except requests.RequestException as error:
        raise UserAccessError("The private data store is unavailable. Try again shortly.") from error
    if not response.ok:
        data = _response_json(response)
        raise UserAccessError(_error_message(data, "The private data request could not be completed."))
    if response.status_code == 204 or not response.content:
        return None
    try:
        return response.json()
    except ValueError:
        return None
