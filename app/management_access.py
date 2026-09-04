from __future__ import annotations

from datetime import datetime

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .database import SessionLocal
from .management_models import ManagementSession, StaffUser
from .security import hash_token


ALL_OPERATORS = {"Administrator", "Manager", "Underwriter", "Claims", "Finance", "Agent"}
RULES = [
    ("/api/v1/management/core/quotes", {"Administrator", "Manager", "Underwriter"}),
    ("/api/v1/management/core/policies", {"Administrator", "Manager", "Underwriter"}),
    ("/api/v1/management/core/claims", {"Administrator", "Manager", "Claims"}),
    ("/api/v1/management/core/customers", {"Administrator", "Manager", "Underwriter"}),
    ("/api/v1/management/core/intermediaries", {"Administrator", "Manager"}),
    ("/api/v1/management/core/approvals", ALL_OPERATORS),
    ("/api/v1/management/core/documents", ALL_OPERATORS),
    ("/api/v1/management/customers", {"Administrator", "Manager", "Underwriter", "Agent"}),
    ("/api/v1/management/policies", {"Administrator", "Manager", "Underwriter"}),
    ("/api/v1/management/products", {"Administrator", "Manager", "Underwriter"}),
    ("/api/v1/management/payments", {"Administrator", "Manager", "Finance"}),
    ("/api/v1/management/leads", {"Administrator", "Manager", "Underwriter", "Agent"}),
    ("/api/v1/management/claims", {"Administrator", "Manager", "Claims"}),
    ("/api/v1/management/tickets", {"Administrator", "Manager", "Claims", "Agent"}),
    ("/api/v1/management/tasks", ALL_OPERATORS),
    ("/api/v1/management/notes", ALL_OPERATORS),
    ("/api/v1/management/documents", ALL_OPERATORS),
    ("/api/v1/management/staff", {"Administrator"}),
    ("/api/v1/management/branches", {"Administrator"}),
    ("/api/v1/management/settings", {"Administrator"}),
]


class ManagementAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        method = request.method.upper()
        if not path.startswith("/api/v1/management/") or method in {"GET", "HEAD", "OPTIONS"}:
            return await call_next(request)
        if path == "/api/v1/management/auth/login":
            return await call_next(request)

        auth = request.headers.get("authorization", "")
        token = request.headers.get("x-management-token") or (auth[7:].strip() if auth.lower().startswith("bearer ") else "")
        if not token:
            return JSONResponse({"detail": "Management authentication required"}, status_code=401)

        with SessionLocal() as db:
            session = db.query(ManagementSession).filter(ManagementSession.token_hash == hash_token(token)).first()
            if not session or session.expires_at <= datetime.utcnow():
                return JSONResponse({"detail": "Management session has expired"}, status_code=401)
            user = db.query(StaffUser).filter(StaffUser.id == session.user_id, StaffUser.active.is_(True)).first()
            if not user:
                return JSONResponse({"detail": "Management account is inactive"}, status_code=401)

            if path.startswith("/api/v1/management/auth/"):
                return await call_next(request)

            allowed = {"Administrator", "Manager"}
            for prefix, roles in RULES:
                if path.startswith(prefix):
                    allowed = roles
                    break
            if user.role not in allowed:
                return JSONResponse({"detail": "Your role does not have permission for this action"}, status_code=403)

        return await call_next(request)
