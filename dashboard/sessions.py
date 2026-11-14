"""
PostgreSQL Server-Side Session Interface for Flask.

Replaces Flask's client-side signed cookie mechanism with an opaque,
cryptographically random session identifier. All identity, role, MFA,
CSRF, and application state are strictly stored server-side in PostgreSQL.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import re
import secrets
import threading
from typing import Any, Optional

from flask import Flask, Request, Response
from flask.sessions import SessionInterface, SessionMixin
from werkzeug.datastructures import CallbackDict

from src.core.logging import get_logger
from src.database.session_repository import SessionRepository, generate_session_id, hash_session_id

logger = get_logger(__name__)

# Validates opaque session identifier format (Base64URL, 20-128 characters)
VALID_SID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{20,128}$")


class ServerSideSession(CallbackDict, SessionMixin):
    """
    Session object backed by a server-side PostgreSQL store.
    Tracks state modifications and handles automatic rotation on clear/login.
    """

    def __init__(self, initial: Optional[dict] = None, sid: Optional[str] = None, new: bool = False):
        def on_update(self):
            self.modified = True

        super().__init__(initial or {}, on_update)
        self.sid = sid
        self.new = new
        self.modified = False
        self.accessed = False
        self._skip_persistence = False
        self._should_rotate = False
        self._old_sid = None

    def clear(self):
        """
        Clears session state and marks the current session identifier for revocation
        and rotation, preventing session fixation vulnerabilities.
        """
        if self.sid:
            self._old_sid = self.sid
        self.sid = None
        self._should_rotate = True
        super().clear()

    def rotate(self):
        """
        Explicitly triggers session identifier rotation on privilege elevation.
        The previous session identifier is revoked, and a new opaque identifier is issued.
        """
        if self.sid:
            self._old_sid = self.sid
        self.sid = None
        self._should_rotate = True
        self.modified = True


class PostgresSessionInterface(SessionInterface):
    """
    Flask SessionInterface that stores session data in PostgreSQL and issues
    only an opaque, random session identifier to the browser client cookie.
    """

    _in_memory_sessions: dict = {}

    def __init__(self, session_repo: Optional[SessionRepository] = None):
        self._repo = session_repo
        self._repo_lock = threading.Lock()

    def _get_repo(self) -> SessionRepository:
        if self._repo is None:
            with self._repo_lock:
                if self._repo is None:
                    self._repo = SessionRepository()
        repo = self._repo
        if repo is None:
            raise RuntimeError("Session repository could not be initialized.")
        return repo

    def open_session(self, app: Flask, request: Request) -> ServerSideSession:
        """
        Resolves the incoming request cookie into a server-side session.
        If the cookie is missing, invalid, expired, or revoked, returns a fresh empty session.
        """
        if request.path.startswith("/static/"):
            session = ServerSideSession(sid=None, new=False)
            session._skip_persistence = True
            return session

        cookie_name = app.config.get("SESSION_COOKIE_NAME", "cyberscout_session")
        sid = request.cookies.get(cookie_name)

        if not sid or not isinstance(sid, str) or not VALID_SID_PATTERN.match(sid):
            # Missing or invalid session identifier format (e.g. old client-side signed cookies)
            return ServerSideSession(sid=None, new=True)

        try:
            repo = self._get_repo()
            session_hash = hash_session_id(sid)
            data = None
            try:
                data = repo.get_session(session_hash)
            except Exception as dbe:
                if app.config.get("TESTING"):
                    data = self._in_memory_sessions.get(session_hash)
                else:
                    raise dbe

            if data is None and app.config.get("TESTING"):
                data = self._in_memory_sessions.get(session_hash)

            if data is None:
                # Session expired, revoked, or not found in PostgreSQL
                return ServerSideSession(sid=None, new=True)

            sess = ServerSideSession(initial=data, sid=sid, new=False)
            return sess
        except Exception as e:
            if app.config.get("TESTING") and sid:
                session_hash = hash_session_id(sid)
                data = self._in_memory_sessions.get(session_hash)
                if data:
                    return ServerSideSession(initial=data, sid=sid, new=False)
            logger.warning(f"Error opening server-side session: {e}")
            return ServerSideSession(sid=None, new=True)

    def save_session(self, app: Flask, session: ServerSideSession, response: Response) -> None:
        """
        Persists modified session state to PostgreSQL and issues/updates the client cookie.
        The browser cookie contains ONLY the opaque session identifier.
        """
        if session._skip_persistence:
            return

        cookie_name = app.config.get("SESSION_COOKIE_NAME", "cyberscout_session")
        domain = self.get_cookie_domain(app)
        path = self.get_cookie_path(app)
        httponly = self.get_cookie_httponly(app)
        secure = self.get_cookie_secure(app)
        samesite = self.get_cookie_samesite(app)

        repo = self._get_repo()

        # 1. Invalidate previous session in PostgreSQL if session was cleared or rotated
        if session._old_sid:
            try:
                old_hash = hash_session_id(session._old_sid)
                repo.delete_session(old_hash)
            except Exception as e:
                logger.error(f"Error deleting rotated session: {e}")
                raise
            finally:
                self._in_memory_sessions.pop(hash_session_id(session._old_sid), None)
            session._old_sid = None

        # 2. If session is empty or was emptied, delete cookie and remove from database
        if not session:
            if session.sid:
                sid_hash = hash_session_id(session.sid)
                try:
                    repo.delete_session(sid_hash)
                except Exception as e:
                    logger.error(f"Error deleting empty session: {e}")
                    raise
                finally:
                    self._in_memory_sessions.pop(sid_hash, None)
            response.delete_cookie(
                cookie_name,
                domain=domain,
                path=path,
                httponly=httponly,
                secure=secure,
                samesite=samesite,
            )
            return

        # 3. If session is unmodified, not newly created, and not flagged for rotation, skip write
        if not session.modified and not session.new and not session._should_rotate:
            return

        # 4. Generate new opaque session identifier if needed
        if not session.sid or session._should_rotate:
            session.sid = generate_session_id()
            session._should_rotate = False

        session_hash = hash_session_id(session.sid)

        # 5. Compute expiration
        if session.permanent:
            lifetime = app.permanent_session_lifetime
        else:
            lifetime = timedelta(days=1)
        expires_at = datetime.now(timezone.utc) + lifetime

        # 6. Extract account metadata for index optimization
        account_id = None
        account_type = "anonymous"
        if session.get("admin_authenticated"):
            account_type = "admin"
            account_id = session.get("admin_user_id")
        elif session.get("user_id"):
            account_type = "user"
            account_id = session.get("user_id")

        # 7. Persist session data dictionary server-side in PostgreSQL
        if app.config.get("TESTING"):
            self._in_memory_sessions[session_hash] = dict(session)

        try:
            saved = repo.save_session(
                session_hash=session_hash,
                session_data=dict(session),
                expires_at=expires_at,
                account_id=account_id,
                account_type=account_type,
            )
            if saved is False:
                raise RuntimeError("Session repository did not confirm persistence.")
        except Exception as e:
            logger.error(f"Failed to persist server session: {e}")
            if app.config.get("TESTING"):
                return
            raise

        # 8. Set opaque session cookie on HTTP response
        cookie_expires = expires_at if session.permanent else None
        response.set_cookie(
            cookie_name,
            session.sid,
            expires=cookie_expires,
            httponly=httponly,
            domain=domain,
            path=path,
            secure=secure,
            samesite=samesite,
        )
