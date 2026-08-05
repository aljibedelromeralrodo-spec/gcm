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
_CA_BUNDLE = os.path.join(os.path.dirname(__file__), "certs", "migrup_bundle.pem")
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
                          headers=_headers(auth=False), verify=_CA_BUNDLE, timeout=25)
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
        r = requests.post(f"{BASE}/{ep}", json=payload, headers=_headers(), verify=_CA_BUNDLE, timeout=40)
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
    lg = login()
    if not lg.get("success"):
        return {"_error": lg.get("error")}
    return _post("Dashboard/ListadoDocumentosConFiltros",
                 {"idUsuario": _CACHE["uid"], "nombreDocumento": nombre,
                  "estadoId": estado_id, "pagina": pagina, "cantidad": cantidad})


def get_file(id_documento):
    """Descarga un documento (incluido el firmado) desde eCert. Devuelve dict con base64."""
    lg = login()
    if not lg.get("success"):
        return {"_error": lg.get("error")}
    return _post("Dashboard/GetFile", {"idDocumento": id_documento})


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
    if isinstance(res, dict) and (res.get("_status", 200) >= 400 or res.get("status", 200) >= 400
                                  or res.get("errors")):
        detalle = res.get("errors") or res.get("_text") or res.get("title") or res
        return {"success": False, "error": str(detalle)[:200]}
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
                            pos=None, firmar_todas_paginas=False, posiciones=None):
    """Carga un PDF y lo envía a firmar por un tercero (el cliente) vía eCert.

    Flujo real de migrup: el firmante se referencia por contactoId, por lo que el
    contacto SIEMPRE se crea primero. texto = clave del certificado del titular.
    """
    lg = login()
    if not lg.get("success"):
        return {"success": False, "error": lg.get("error")}
    propio = _split_rut(os.environ.get("MIGRUP_RUT", ""))[0]
    es_propio = _split_rut(firmante.get("rut", ""))[0] == propio
    contacto = None
    if not es_propio:
        cont = asegurar_contacto(firmante)
        contacto = cont.get("contacto") or buscar_contacto_por_rut(firmante.get("rut", ""))
        if not contacto or not contacto.get("contId"):
            return {"success": False, "error": f"No se pudo crear el contacto en eCert: {cont.get('error') or ''}"}
    if len(pdf_bytes) > 10 * 1024 * 1024:
        return {"success": False, "error": "El PDF supera los 10MB permitidos por eCert"}
    n_pages, alto = 1, 792
    try:
        from pypdf import PdfReader
        import io as _io
        reader = PdfReader(_io.BytesIO(pdf_bytes))
        n_pages = len(reader.pages)
        alto = float(reader.pages[0].mediabox.height or 792)
    except Exception:
        pass
    pos = pos or {"x": 60, "y": 60}
    pos_y = max(8, int(alto - 53 - pos["y"]) - 8)
    if posiciones:
        # Una estampa por cada etiqueta 'Firma cliente/asegurado/...' detectada.
        # OJO: eCert cobra 1 firma de terceros POR ESTAMPA (firmaOrden distinto).
        firmantes = []
        for i, p in enumerate(posiciones, start=1):
            alto_pg = float(p.get("alto_pagina") or alto)
            fy = int(alto_pg - float(p["top"]))  # base de la estampa = borde superior de la etiqueta
            fy = max(8, min(fy, int(alto_pg) - 62))
            ancho_pg = float(p.get("ancho_pagina") or 612)
            fx = max(8, min(int(float(p["x"])), int(ancho_pg) - 132))
            firmantes.append({"usuarioId": _CACHE["uid"] if es_propio else None,
                              "contactoId": None if es_propio else contacto["contId"],
                              "firmaOrden": i, "firmaPagina": int(p["pagina"]),
                              "firmaPosX": fx, "firmaPosY": fy})
    else:
        paginas = list(range(1, n_pages + 1)) if firmar_todas_paginas else [1]
        firmantes = [{"usuarioId": _CACHE["uid"] if es_propio else None,
                      "contactoId": None if es_propio else contacto["contId"], "firmaOrden": 1,
                      "firmaPagina": pg, "firmaPosX": int(pos["x"]), "firmaPosY": pos_y}
                     for pg in paginas]
    payload = {
        "usuarioId": _CACHE["uid"],
        "comentario": comentario or "",
        "nroDocumentos": 1,
        "texto": os.environ.get("MIGRUP_CLAVE_CERT", "") if es_propio else "",
        "documentos": [{
            "doctoBase64": _b64(pdf_bytes),
            "doctoNombre": (nombre_documento or "documento")[:20],
            "modoFirma": 1,
            "firmantes": firmantes,
        }],
        "enviarCopiaAMi": False,
        "enviarCopiaAFirmantes": False,
        "listaCorreosEnvioCopia": "",
    }
    res = _post("ProcesoFirma/ProcesoFirmaDocumentos", payload)
    if isinstance(res, dict) and res.get("_error"):
        return {"success": False, "error": res["_error"]}
    codigo = (res or {}).get("codigo") or (res or {}).get("Codigo")
    if codigo != 200:
        msg = ((res or {}).get("descripcionError") or (res or {}).get("mensaje")
               or (res or {}).get("Mensaje") or str(res)[:200])
        if not posiciones and firmar_todas_paginas and len(firmantes) > 1:
            # Algunos planes no aceptan multi-página: reintentar con una sola firma en pág 1
            return enviar_a_firmar_tercero(pdf_bytes, nombre_documento, firmante,
                                           comentario, pos, firmar_todas_paginas=False)
        return {"success": False, "error": f"eCert: {msg}", "raw": res}
    _docs_res = (res or {}).get("documentos") or []
    _doc_id = None
    if isinstance(_docs_res, list) and _docs_res and isinstance(_docs_res[0], dict):
        d0 = _docs_res[0]
        _doc_id = (d0.get("idDocumento") or d0.get("documentoId")
                   or d0.get("doctoId") or d0.get("id"))
    return {"success": True, "ecert_doc_id": _doc_id,
            "raw": {k: v for k, v in (res or {}).items() if k != "documentos"},
            "paginas": n_pages, "contacto_id": (contacto or {}).get("contId")}

