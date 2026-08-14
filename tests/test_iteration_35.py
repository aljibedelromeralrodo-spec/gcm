"""Iteration 35: gestion-ejecutivos, remitentes-detectados, supercarpeta regression."""
import os
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
# Fall back to reading frontend .env if REACT_APP_BACKEND_URL isn't in env
if not BASE:
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE = line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass

API = f"{BASE}/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
_mongo = MongoClient(MONGO_URL)
db = _mongo[DB_NAME]


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{API}/auth/login", json={"rut": "administrador", "password": "141617575"}, timeout=30)
    assert r.status_code == 200, f"login {r.status_code} {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def H(token):
    return {"Authorization": f"Bearer {token}"}


# ── GESTION EJECUTIVOS PANEL ──
def test_gestion_panel(H):
    r = requests.get(f"{API}/gestion-ejecutivos", headers=H, timeout=30)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert "modulos" in d and set(d["modulos"].keys()) >= {"daniela", "victoria", "postventa"}
    for k in ("daniela", "victoria", "postventa"):
        m = d["modulos"][k]
        for key in ("nombre", "hoy", "semana", "mes", "por_hora", "tipos", "clientes_hoy",
                    "cumplimiento_pct", "alerta_incompleto"):
            assert key in m, f"missing {key} in modulo {k}"
        assert isinstance(m["por_hora"], list) and len(m["por_hora"]) == 24
    assert "postventa" in d["modulos"]["postventa"]
    pv = d["modulos"]["postventa"]["postventa"]
    for key in ("casos_activos", "resueltos_hoy", "tiempo_promedio_dias"):
        assert key in pv
    c = d["consolidado"]
    assert "total_hoy" in c and "mas_activo" in c and "alertas_baja_actividad" in c
    assert isinstance(c["comparativa_semanal"], list) and len(c["comparativa_semanal"]) == 7
    assert "ultima_actualizacion" in d


# ── GESTION EJECUTIVOS FUENTES ──
def test_gestion_fuentes_agregar_quitar(H):
    r = requests.get(f"{API}/gestion-ejecutivos/fuentes", headers=H, timeout=30)
    assert r.status_code == 200
    correo = "victoria.vilche@centralmutuos.cl"
    r = requests.post(f"{API}/gestion-ejecutivos/fuentes", headers=H,
                      json={"ejecutivo": "victoria", "accion": "agregar", "correo": correo}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    assert correo in r.json()["fuentes"]
    # Bitácora
    log = db.gestion_fuentes_log.find_one({"correo": correo, "accion": "agregar"})
    assert log is not None
    # Quitar
    r = requests.post(f"{API}/gestion-ejecutivos/fuentes", headers=H,
                      json={"ejecutivo": "victoria", "accion": "quitar", "correo": correo}, timeout=30)
    assert r.status_code == 200
    assert correo not in r.json()["fuentes"]


# ── REMITENTES DETECTADOS ──
def test_remitentes_detectados_full_flow(H):
    r = requests.get(f"{API}/supercarpeta/remitentes-detectados", headers=H, timeout=30)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    for k in ("detectados", "bloqueados", "registro", "hitos_validos"):
        assert k in d
    assert "tasacion" in d["hitos_validos"]

    # find a real folder
    fd = db.folders.find_one({"oculto_supercarpeta": {"$exists": False}}, {"id": 1, "nombre": 1})
    assert fd, "No folders available"
    fid = fd["id"]
    correo_test = "test.remitente@qa.cl"
    detected = {
        "correo": correo_test, "nombre": "Test QA",
        "primera_vez": "2026-08-14T00:00:00", "estado": "pendiente_confirmacion",
        "etiqueta": "Detectado automáticamente el 2026-08-14",
    }

    # Insert & confirm
    db.folders.update_one({"id": fid}, {"$push": {"fuentes_detectadas.tasacion": detected}})
    r = requests.post(f"{API}/supercarpeta/remitentes-detectados/accion", headers=H,
                      json={"folder_id": fid, "hito": "tasacion", "correo": correo_test,
                            "accion": "confirmar"}, timeout=30)
    assert r.status_code == 200, r.text[:300]
    fd2 = db.folders.find_one({"id": fid})
    assert correo_test in (fd2.get("fuentes_doc") or {}).get("tasacion", []), "confirmar no persistió en fuentes_doc.tasacion"

    # Insert & bloquear
    db.folders.update_one({"id": fid}, {"$push": {"fuentes_detectadas.tasacion": detected}})
    r = requests.post(f"{API}/supercarpeta/remitentes-detectados/accion", headers=H,
                      json={"folder_id": fid, "hito": "tasacion", "correo": correo_test,
                            "accion": "bloquear"}, timeout=30)
    assert r.status_code == 200, r.text[:300]
    cfg = db.config.find_one({"_key": "remitentes_bloqueados"}) or {}
    assert correo_test in (cfg.get("correos") or []), "bloquear no persistió en remitentes_bloqueados"

    # CLEANUP
    db.folders.update_one({"id": fid}, {"$pull": {"fuentes_doc.tasacion": correo_test}})
    db.folders.update_one({"id": fid}, {"$pull": {"fuentes_detectadas.tasacion": {"correo": correo_test}}})
    db.config.update_one({"_key": "remitentes_bloqueados"}, {"$pull": {"correos": correo_test}})
    db.remitentes_registro.delete_many({"correo": correo_test})


# ── SUPERCARPETA REGRESION 17 clientes ──
def test_supercarpeta_agosto_17(H):
    r = requests.get(f"{API}/supercarpeta?mes=2026-08", headers=H, timeout=60)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    clientes = d.get("clientes") or d.get("items") or d.get("carpetas") or []
    assert len(clientes) == 17, f"Se esperaban 17, hay {len(clientes)}"
    # avance/proyeccion
    assert d.get("proyeccion") is not None
    sample = clientes[0]
    assert "avance" in sample, f"missing avance in cliente: {list(sample.keys())[:20]}"


# ── GERENCIA CARTERA ──
def test_gerencia_cartera_17(H):
    r = requests.get(f"{API}/gerencia/cartera", headers=H, timeout=60)
    assert r.status_code == 200
    d = r.json()
    filas = d.get("cartera") or d.get("filas") or d.get("clientes") or []
    assert len(filas) == 17, f"gerencia cartera filas={len(filas)}"
    assert "cumplimiento_broker" in d
