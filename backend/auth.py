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
    "/api/", "/api", "/api/auth/login", "/api/auth/crear-clave",
    "/api/inmobiliaria/auth/login", "/api/valor-uf", "/api/paridad",
}

# ═══ Bloqueos backend por PERFIL (los módulos no asignados tampoco son accesibles por API) ═══
PERFIL_RUTAS_BLOQUEADAS = {
    "ventas": (
        "/api/admin/users",            # Gestión de usuarios: solo Admin
        "/api/dashai",                 # Cerebro DashAI / configuración del sistema
        "/api/auditoria-forense",
    ),
    "gerencia_comercial": (
        "/api/admin/users",
        "/api/dashai",
        "/api/auditoria-forense",
        "/api/clientes/folders",       # Carpeta de Clientes: sin acceso
        "/api/supercarpeta",           # Supercarpeta: sin acceso
        "/api/crece/credenciales",     # Gestor Crece: solo Admin y ejecutivos de venta
    ),
}
PUBLIC_PREFIXES = (
    "/api/publicidad/contacto",    # Formulario público "Quiero ser contactado" (campañas)
    "/api/publicidad/antecedentes",  # Portal público de envío de antecedentes (campañas WhatsApp)
    "/api/calificar",              # Portal de Captura Autónoma (token = oid)
    "/api/firma/",                 # Portal de Firma (token de firma en la URL)
    "/api/oportunidades/track",    # Pixeles/clics de correos comerciales
    "/api/descarga-segura/",       # Links seguros de descarga para clientes (token único)
    "/api/escrituracion/confirmar/",  # Confirmación de escrituración desde el correo de aprobación (token único)
    "/api/brain/",                 # Conexión Contralora (exige BRAIN_ACCESS_KEY dentro del módulo)
    "/api/energia",                # Monitor de energía (indicador de saldo del topbar)
    "/api/gmail/push",             # Webhook Pub/Sub de Gmail (valida cuenta monitoreada dentro)
    "/api/gmail/oauth/callback",   # Callback OAuth de Google (canje de código único)
)
# El portal comercial de inmobiliarias tiene su propia sesión (scope inmobiliaria)
INMO_PREFIX = "/api/inmobiliaria"
TERMINAL_ROLES_OK = None  # cualquier usuario del terminal (staff interno)


def _es_publica(path):
    if path in PUBLIC_EXACT:
        return True
    return any(path.startswith(p) for p in PUBLIC_PREFIXES)


# JERARQUÍA A/B (Regla de Oro #22): módulos vetados por perfil. Admin pasa libre.
PERFIL_BLOQUEOS = {
    "A": ("/api/contraloria", "/api/dashai", "/api/admin", "/api/gerencia", "/api/bodega",
          "/api/brain", "/api/constitucion", "/api/criterios", "/api/reporte-diario"),
    "B": ("/api/clientes", "/api/simulaciones", "/api/compromiso", "/api/setcredito",
          "/api/admin/users", "/api/escritura", "/api/tasacion"),
}

# PERFIL D (Brokers): lista blanca — SOLO su propio módulo (Regla de Oro #34)
PERFIL_PERMITIDOS = {
    "D": ("/api/broker", "/api/fuentes/broker", "/api/mi-correo", "/api/valor-uf", "/api/auth",
          "/api/storage"),
}

# ── SISTEMA DE ROLES: reglas de escritura por rol (lectura pasa libre) ──
# contralor: SOLO LECTURA absoluta (lista blanca: su propio módulo espejo)
# postventa/broker: escriben solo en sus módulos propios (lista blanca)
# gerencia: módulos de administración en MODO LECTURA (lista negra de escritura)
# administracion: sin escritura en módulos de gerencia/broker/contralor
ROL_BLOQUEO_ESCRITURA = {
    "contralor": {"lista_blanca": True, "permitidos": ("/api/contralor/",),
                  "mensaje": "Rol Contralor: solo lectura y auditoría absoluta — no puede ejercer cambios"},
    "postventa": {"lista_blanca": True, "permitidos": ("/api/postventa", "/api/mi-correo"),
                  "mensaje": "No está autorizado el ingreso a este módulo"},
    "broker": {"lista_blanca": True, "permitidos": ("/api/broker", "/api/fuentes/broker", "/api/mi-correo"),
               "mensaje": "No está autorizado el ingreso a este módulo"},
    "gerencia": {"lista_blanca": False, "permitidos": (),
                 "bloqueados": ("/api/admin", "/api/criterios", "/api/config/ejecutivos",
                                "/api/autocorreo", "/api/whatsapp", "/api/contralor/"),
                 "mensaje": "Su rol accede a este módulo en modo lectura — cambios no autorizados"},
    "administracion": {"lista_blanca": False, "permitidos": (),
                       "bloqueados": ("/api/supercarpeta", "/api/gerencia", "/api/gestion",
                                      "/api/broker", "/api/contralor/", "/api/oportunidades"),
                       "mensaje": "No está autorizado el ingreso a este módulo"},
}


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
        # PRIMER INGRESO OBLIGATORIO: sin acceso al sistema hasta completar la configuración
        if claims.get("first_login") and not path.startswith("/api/auth"):
            return JSONResponse({"detail": ("Configuración inicial pendiente: debe cambiar su "
                                            "contraseña y configurar su correo antes de acceder")},
                                status_code=428)
        scope = claims.get("scope")
        if path.startswith(INMO_PREFIX):
            if scope not in ("inmobiliaria", "terminal"):
                return JSONResponse({"detail": "Acceso no autorizado a la inmobiliaria"}, status_code=403)
        else:
            # Rutas del Búnker (carpetas, auditoría, ventas, backups, datasets):
            # exclusivas del terminal interno.
            if scope != "terminal":
                return JSONResponse({"detail": "Acceso restringido al terminal de administración"}, status_code=403)
        # HERMETICIDAD A/B: nadie entra ni ve lo que no le corresponde (Regla #22)
        perfil = claims.get("perfil", "")
        permitidos = PERFIL_PERMITIDOS.get(perfil)
        if permitidos and claims.get("rol") not in ("admin", "maestro"):
            if not any(path.startswith(p) for p in permitidos):
                return JSONResponse(
                    {"detail": "Perfil Broker (D): acceso limitado a su propio módulo (Regla de Oro #34)"},
                    status_code=403)
        if perfil in PERFIL_BLOQUEOS and claims.get("rol") not in ("admin", "maestro"):
            if any(path.startswith(p) for p in PERFIL_BLOQUEOS[perfil]):
                return JSONResponse(
                    {"detail": f"Módulo restringido para su perfil {perfil} (Regla de Oro #22 — DashAI monitorea este acceso)"},
                    status_code=403)
        # ── SISTEMA DE ROLES (norma fija) ─────────────────────────────────
        rol = claims.get("rol", "")
        es_escritura = method in ("POST", "PUT", "PATCH", "DELETE")
        # MÓDULO CONTROL (Contraloría): solo lectura SIN EXCEPCIÓN, para todos los roles
        if path.startswith("/api/contraloria") and es_escritura:
            return JSONResponse({"detail": "El Módulo Control es de solo lectura sin excepción"},
                                status_code=403)
        if es_escritura and rol in ROL_BLOQUEO_ESCRITURA and not path.startswith("/api/auth"):
            regla = ROL_BLOQUEO_ESCRITURA[rol]
            permitido = any(path.startswith(p) for p in regla["permitidos"])
            if regla.get("lista_blanca"):
                if not permitido:
                    return JSONResponse({"detail": regla["mensaje"]}, status_code=403)
            elif any(path.startswith(p) for p in regla.get("bloqueados", ())) and not permitido:
                return JSONResponse({"detail": regla["mensaje"]}, status_code=403)
        # 👁 VISTA PREVIA POR ROL: auditoría de acciones del Admin en simulación
        rol_simulado = request.headers.get("x-simula-rol", "").strip()
        if es_escritura and rol_simulado and rol in ("admin", "maestro"):
            try:
                import uuid as _uuid
                import asyncio as _asyncio
                from database import db as _db
                _asyncio.create_task(_db.simulacion_auditoria.insert_one({
                    "id": str(_uuid.uuid4()),
                    "fecha": datetime.now(timezone.utc).isoformat(),
                    "usuario": claims.get("sub", ""),
                    "rol_simulado": rol_simulado,
                    "metodo": method, "ruta": path,
                    "detalle": f"Acción realizada por Admin en simulación de rol {rol_simulado}",
                }))
            except Exception:
                logging.warning("auditoría de simulación: no fue posible registrar")
        request.state.user = claims
        # ═══ PERFILES ESTRICTOS (Regla del menú por rol): bloqueo backend de rutas sensibles ═══
        perfil = claims.get("perfil") or ""
        if perfil in PERFIL_RUTAS_BLOQUEADAS and claims.get("rol") not in ("admin", "maestro"):
            for pref in PERFIL_RUTAS_BLOQUEADAS[perfil]:
                if path.startswith(pref):
                    return JSONResponse({"detail": f"Acceso denegado: su perfil ({perfil}) no tiene "
                                                   "permiso sobre este módulo."}, status_code=403)
            if path.startswith("/api/inmobiliaria/config/criterios") and method in ("POST", "PUT", "DELETE"):
                return JSONResponse({"detail": "Solo el Administrador puede modificar la Bóveda de Criterios."},
                                    status_code=403)
        return await call_next(request)
