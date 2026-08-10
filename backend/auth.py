"""BÚNKER DE SEGURIDAD — autenticación JWT y lectura centralizada de secretos.

- Todos los secretos se leen EXCLUSIVAMENTE desde el entorno del sistema (os.environ).
- Todas las rutas /api/* exigen un token de administrador válido, salvo los
  portales públicos (captura de prospectos y firma), que usan su token temporal
  propio embebido en la URL (oid / token de firma).
"""
import os
import jwt
import logging
from datetime import datetime, timezone, timedelta

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

JWT_ALGORITHM = "HS256"
TOKEN_HORAS = 12


# ── SANEAMIENTO DE SECRETOS (SEC-003) ─────────────────────────────────────
def get_secret(name, default=""):
    """Punto ÚNICO de acceso a secretos: solo variables de entorno del sistema."""
    return os.environ.get(name, default)


def _jwt_secret():
    s = get_secret("JWT_SECRET")
    if not s:
        raise RuntimeError("JWT_SECRET no configurado en el entorno")
    return s


# ── EMISIÓN Y VERIFICACIÓN DE TOKENS ──────────────────────────────────────
def create_token(sub, rol="ejecutivo", scope="terminal", extra=None):
    payload = {
        "sub": str(sub), "rol": rol, "scope": scope,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_HORAS),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_token(token):
    return jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])


# ── CONTROL DE ACCESO GLOBAL (SEC-001 / SEC-002) ──────────────────────────
# Rutas públicas: NO exigen token de administrador. Los portales usan su token
# propio (oid del prospecto / token de firma) validado dentro del endpoint.
PUBLIC_EXACT = {
    "/api/", "/api", "/api/auth/login", "/api/inmobiliaria/auth/login",
    "/api/valor-uf",
}
PUBLIC_PREFIXES = (
    "/api/calificar",              # Portal de Captura Autónoma (token = oid)
    "/api/firma/",                 # Portal de Firma (token de firma en la URL)
    "/api/oportunidades/track",    # Pixeles/clics de correos comerciales
)
# El portal comercial de inmobiliarias tiene su propia sesión (scope inmobiliaria)
INMO_PREFIX = "/api/inmobiliaria"
TERMINAL_ROLES_OK = None  # cualquier usuario del terminal (staff interno)


def _es_publica(path):
    if path in PUBLIC_EXACT:
        return True
    return any(path.startswith(p) for p in PUBLIC_PREFIXES)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        method = request.method
        # Solo se protege el backend /api/*; el resto (frontend) pasa libre.
        if not path.startswith("/api") or method == "OPTIONS":
            return await call_next(request)
        if _es_publica(path):
            return await call_next(request)
        # Login de inmobiliarias ya está en PUBLIC_EXACT; el resto de /api/inmobiliaria
        # exige sesión (scope inmobiliaria o terminal).
        auth = request.headers.get("Authorization", "")
        token = auth[7:].strip() if auth.startswith("Bearer ") else ""
        if not token:
            # Descargas/vistas abiertas con window.open o <a href>: el navegador no
            # envía el header, pero sí la cookie de sesión (o el query param t).
            token = request.cookies.get("cm_token", "") or request.query_params.get("t", "")
        if not token:
            return JSONResponse({"detail": "No autenticado — token requerido"}, status_code=401)
        try:
            claims = decode_token(token)
        except jwt.ExpiredSignatureError:
            return JSONResponse({"detail": "Sesión expirada — vuelva a ingresar"}, status_code=401)
        except jwt.InvalidTokenError:
            return JSONResponse({"detail": "Token inválido"}, status_code=401)
        scope = claims.get("scope")
        if path.startswith(INMO_PREFIX):
            if scope not in ("inmobiliaria", "terminal"):
                return JSONResponse({"detail": "Acceso no autorizado a la inmobiliaria"}, status_code=403)
        else:
            # Rutas del Búnker (carpetas, auditoría, ventas, backups, datasets):
            # exclusivas del terminal interno.
            if scope != "terminal":
                return JSONResponse({"detail": "Acceso restringido al terminal de administración"}, status_code=403)
        request.state.user = claims
        return await call_next(request)
