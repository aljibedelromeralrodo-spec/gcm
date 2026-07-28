"""Integración con migrup.cl (eCert Chile) — firma electrónica de documentos.

Usa la API interna ApiGatewayGrup. El login devuelve un JWT que se cachea.
Credenciales en .env (MIGRUP_RUT / MIGRUP_CLAVE). Firma en nombre del titular.
"""
import os
import time
import base64
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://www.migrup.cl/ApiGatewayGrup/api"
_CACHE = {"token": None, "uid": None, "user": None, "ts": 0}
_TTL = 20 * 60  # 20 min


def _headers(auth=True):
    h = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json",
         "Origin": "https://www.migrup.cl", "Referer": "https://www.migrup.cl/"}
    if auth and _CACHE["token"]:
        h["Authorization"] = f"Bearer {_CACHE['token']}"
    return h


def _split_rut(rut):
    r = (rut or "").replace(".", "").replace("-", "").strip()
    return r[:-1], r[-1:]


def configured():
    return bool(os.environ.get("MIGRUP_RUT") and os.environ.get("MIGRUP_CLAVE"))


def login(force=False):
    if not configured():
        return {"success": False, "error": "Credenciales migrup no configuradas"}
    if not force and _CACHE["token"] and (time.time() - _CACHE["ts"] < _TTL):
        return {"success": True, "cached": True, "user": _CACHE["user"], "uid": _CACHE["uid"]}
    num, dv = _split_rut(os.environ["MIGRUP_RUT"])
    try:
        r = requests.post(f"{BASE}/Usuarios/UsuariosPorRutyClave",
                          json={"RutUsuario": num, "DVUsuario": dv, "ClaveUsuario": os.environ["MIGRUP_CLAVE"]},
                          headers=_headers(auth=False), verify=False, timeout=25)
        d = r.json()
    except Exception as e:
        return {"success": False, "error": f"Conexión migrup: {str(e)[:120]}"}
    if not d.get("token"):
        return {"success": False, "error": d.get("mensaje") or "RUN o contraseña inválidos"}
    _CACHE.update({"token": d["token"], "uid": d.get("usuarioId"), "ts": time.time(),
                   "user": {"nombres": d.get("usuaNombres"), "apellido": d.get("usuaApPaterno"),
                            "email": d.get("usuaEmail"), "alias": d.get("usuaAlias")},
                   "forzar_renovacion": d.get("forzarRenovacionCertificado")})
    return {"success": True, "user": _CACHE["user"], "uid": _CACHE["uid"],
            "forzar_renovacion": d.get("forzarRenovacionCertificado")}


def _post(ep, payload, retry=True):
    lg = login()
    if not lg.get("success"):
        return {"_error": lg.get("error")}
    try:
        r = requests.post(f"{BASE}/{ep}", json=payload, headers=_headers(), verify=False, timeout=40)
    except Exception as e:
        return {"_error": f"Conexión migrup: {str(e)[:120]}"}
    if r.status_code == 401 and retry:
        login(force=True)
        return _post(ep, payload, retry=False)
    try:
        return r.json()
    except Exception:
        return {"_status": r.status_code, "_text": r.text[:300]}


def semaforo():
    lg = login()
    if not lg.get("success"):
        return {"_error": lg.get("error")}
    return _post("Dashboard/TraerSemaforo", {"idUsuario": _CACHE["uid"]})


def listar_documentos(nombre="", estado_id=0, pagina=1, cantidad=15):
    return _post("Dashboard/ListadoDocumentosConFiltros",
                 {"idUsuario": _CACHE["uid"], "nombreDocumento": nombre,
                  "estadoId": estado_id, "pagina": pagina, "cantidad": cantidad})


def listar_contactos(pagina=1, cantidad=1000):
    lg = login()
    if not lg.get("success"):
        return {"_error": lg.get("error")}
    return _post("Contacto/ListarContactos", {
        "pageNumber": pagina, "pageSize": cantidad, "idUsuario": _CACHE["uid"],
        "nombre": "", "apellidoPaterno": "", "apellidoMaterno": "",
        "rut": 0, "rutDv": "", "correo": ""})


def buscar_contacto_por_rut(rut):
    num, _dv = _split_rut(rut)
    if not num:
        return None
    res = listar_contactos()
    for c in (res or {}).get("items") or []:
        if str(c.get("contRut", "")).strip() == str(num):
            return c
    return None


def crear_contacto(nombres, paterno, materno, rut, email):
    lg = login()
    if not lg.get("success"):
        return {"success": False, "error": lg.get("error")}
    num, dv = _split_rut(rut)
    if not num or not dv:
        return {"success": False, "error": "RUN inválido"}
    res = _post("Contacto/CrearContacto", {
        "idUsuario": _CACHE["uid"], "nombres": nombres, "paterno": paterno,
        "materno": materno or "", "rut": num, "digitoVerificador": dv,
        "email": (email or "").lower()})
    if isinstance(res, dict) and res.get("_error"):
        return {"success": False, "error": res["_error"]}
    if isinstance(res, dict) and res.get("_status", 200) >= 400:
        return {"success": False, "error": res.get("_text") or f"HTTP {res.get('_status')}"}
    return {"success": True, "raw": res}


def asegurar_contacto(firmante):
    """Crea el contacto en eCert si no existe (requisito para firmas de terceros)."""
    existente = buscar_contacto_por_rut(firmante.get("rut", ""))
    if existente:
        return {"success": True, "existia": True, "contacto": existente}
    res = crear_contacto(firmante.get("nombres", ""), firmante.get("aPaterno", ""),
                         firmante.get("aMaterno", ""), firmante.get("rut", ""),
                         firmante.get("email", ""))
    res["existia"] = False
    return res



def _b64(raw):
    return base64.b64encode(raw).decode()


def enviar_a_firmar_tercero(pdf_bytes, nombre_documento, firmante, comentario="",
                            pos=None, firmar_todas_paginas=False):
    """Carga un PDF y lo envía a firmar por un tercero (el cliente).

    firmante: {nombres, aPaterno, aMaterno, rut, email}
    pos: posición de la firma {x,y,width,height} (por defecto abajo-izquierda).
    firmar_todas_paginas: si True, coloca un campo de firma en TODAS las páginas
        para que el cliente firme el set completo de una vez.
    """
    lg = login()
    if not lg.get("success"):
        return {"success": False, "error": lg.get("error")}
    asegurar_contacto(firmante)
    pos = pos or {"x": 60, "y": 60, "width": 130, "height": 60}
    n_pages = 1
    try:
        from pypdf import PdfReader
        import io as _io
        n_pages = len(PdfReader(_io.BytesIO(pdf_bytes)).pages)
    except Exception:
        pass
    paginas = list(range(1, n_pages + 1)) if firmar_todas_paginas else [1]
    rut_limpio = (firmante.get("rut", "") or "").replace(".", "")
    base_firmante = {
        "nombre": firmante.get("nombres", ""),
        "aPaterno": firmante.get("aPaterno", ""),
        "aMaterno": firmante.get("aMaterno", ""),
        "rut": rut_limpio,
        "correo": firmante.get("email", ""),
    }
    firmantes = [dict(base_firmante, posicionFirma=pos, pagina=pg) for pg in paginas]
    contacto = dict(base_firmante, item={"position": {"x": pos["x"], "y": pos["y"]}}, signMode=1)
    documento = {
        "nombreDocumento": nombre_documento,
        "documentoBase64": _b64(pdf_bytes),
        "base64": _b64(pdf_bytes),
        "extension": ".pdf",
        "signMode": 1,
        "paginas": n_pages,
        "firmarTodasLasPaginas": firmar_todas_paginas,
        "contacts": [contacto],
        "firmantes": firmantes,
    }
    payload = {
        "documentos": [documento],
        "idUsuario": _CACHE["uid"],
        "comentario": comentario,
        "enviarCopiaAMi": False,
        "enviarCopiaAFirmantes": False,
        "listaCorreosEnvioCopia": "",
    }
    res = _post("ProcesoFirma/ProcesoFirmaDocumentos", payload)
    if isinstance(res, dict) and res.get("_error"):
        return {"success": False, "error": res["_error"]}
    ok = not (isinstance(res, dict) and (res.get("_status", 200) >= 400))
    return {"success": ok, "raw": res, "paginas": n_pages}

