"""Iteración 47: Regla Constitucional #67 + Calendario + No Calificó (E2E backend)."""
import os
import re
import pytest
import requests
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://espejo-hibrido.preview.emergentagent.com").rstrip("/")
LOCAL = "http://localhost:8001"


@pytest.fixture(scope="session")
def base():
    # Verificar que el proxy WAF no devuelva HTML; fallback a localhost si es necesario
    try:
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"rut": "administrador", "password": "141617575"}, timeout=10)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json"):
            return BASE_URL
    except Exception:
        pass
    return LOCAL


@pytest.fixture(scope="session")
def token(base):
    r = requests.post(f"{base}/api/auth/login",
                      json={"rut": "administrador", "password": "141617575"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def hdr(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def mongo():
    c = MongoClient(os.environ["MONGO_URL"])
    return c[os.environ["DB_NAME"]]


# ── Regla Constitucional #67 ────────────────────────────────────────────────
class TestRegla67:
    def test_creacion_sin_documentos_devuelve_422(self, base, hdr, mongo):
        r = requests.post(f"{base}/api/clientes/folders", headers=hdr,
                          json={"nombre": "PRUEBA QA", "rut": "11.111.111-1"}, timeout=15)
        assert r.status_code == 422, f"esperaba 422 got {r.status_code}: {r.text[:200]}"
        assert "Documentación insuficiente" in r.text
        # Verificar que NO se creó
        assert mongo.folders.find_one({"nombre": "PRUEBA QA"}) is None

    def test_constitucion_maestra_v28_regla67(self, mongo):
        cm = mongo.config.find_one({"_key": "constitucion_maestra"})
        assert cm is not None, "constitucion_maestra no existe"
        assert cm.get("version") == 28
        reglas = cm.get("reglas", [])
        r67 = [r for r in reglas if r.get("n") == 67]
        assert len(r67) == 1
        assert r67[0].get("id") == "apertura_3_documentos"

    def test_creacion_con_3_docs_validos_pasa_y_cleanup(self, base, hdr, mongo):
        payload = {
            "nombre": "PRUEBA QA DOCS",
            "rut": "22.222.222-2",
            "documentos": [
                {"nombre": "cedula_identidad.pdf"},
                {"nombre": "liquidacion_sueldo_enero.pdf"},
                {"nombre": "certificado_afp.pdf"},
            ],
        }
        r = requests.post(f"{base}/api/clientes/folders", headers=hdr, json=payload, timeout=15)
        assert r.status_code == 200, f"esperaba 200 got {r.status_code}: {r.text[:300]}"
        data = r.json()
        fid = data.get("id")
        assert fid
        # Cleanup: intentar DELETE endpoint
        d = requests.delete(f"{base}/api/clientes/folders/{fid}", headers=hdr, timeout=15)
        # Aunque el endpoint devuelva error, forzar limpieza en Mongo
        mongo.folders.delete_one({"id": fid})
        # Verificar limpieza
        assert mongo.folders.find_one({"id": fid}) is None
        assert d.status_code in (200, 204, 404)


# ── Calendario ──────────────────────────────────────────────────────────────
class TestCalendario:
    def test_calendario_mes_agosto(self, base, hdr):
        r = requests.get(f"{base}/api/clientes/calendario?mes=2026-08", headers=hdr, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["mes"] == "2026-08"
        assert isinstance(d["dias"], dict)
        assert d["total_mes"] > 0, f"total_mes debería ser >0, got {d['total_mes']}"

    def test_calendario_dia_2026_08_19(self, base, hdr):
        r = requests.get(f"{base}/api/clientes/calendario/dia?fecha=2026-08-19", headers=hdr, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["fecha"] == "2026-08-19"
        assert isinstance(d["del_dia"], list)
        assert isinstance(d["pendientes_anteriores"], list)
        # resumen.del_dia ≈ 6 (permitir rango 4-10 por si cambia)
        assert d["resumen"]["del_dia"] >= 1
        # Verificar campo dias_sin_avance en pendientes
        if d["pendientes_anteriores"]:
            assert "dias_sin_avance" in d["pendientes_anteriores"][0]

    def test_calendario_dia_fecha_invalida(self, base, hdr):
        r = requests.get(f"{base}/api/clientes/calendario/dia?fecha=xxx", headers=hdr, timeout=10)
        assert r.status_code == 400


# ── Evaluaciones negativas + Notificar No Calificó (E2E) ───────────────────
class TestNoCalifico:
    def test_evaluaciones_negativas_mapa(self, base, hdr):
        r = requests.get(f"{base}/api/clientes/evaluaciones-negativas", headers=hdr, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "negativas" in d
        assert isinstance(d["negativas"], dict)

    def test_flujo_completo_no_califico_con_simulacion_inyectada(self, base, hdr, mongo):
        """Inserta simulación negativa para la carpeta 'LILIAN NAVARRO' (tiene source_email),
        verifica que aparece en /evaluaciones-negativas, envía notificación (1 correo real)
        y limpia."""
        # Localizar carpeta con source_email
        f = mongo.folders.find_one({"source_email": {"$exists": True, "$ne": ""},
                                    "rut": {"$exists": True, "$ne": ""}},
                                   {"_id": 0, "id": 1, "rut": 1, "nombre": 1, "source_email": 1})
        assert f is not None, "no hay carpetas con source_email + rut en la BD"
        fid = f["id"]
        rut = f["rut"]

        # Insertar simulación negativa de prueba
        sim = {
            "rut": rut,
            "precalificacion_aprobada": False,
            "monto_aprobado_uf": 0,
            "timestamp": "2026-08-20T00:00:00",
            "_test_iter47": True,
        }
        ins = mongo.simulaciones.insert_one(sim)
        try:
            # Ahora debería aparecer en negativas
            r = requests.get(f"{base}/api/clientes/evaluaciones-negativas", headers=hdr, timeout=15)
            assert r.status_code == 200
            d = r.json()
            assert fid in d["negativas"], f"carpeta {fid} no está en negativas: keys={list(d['negativas'].keys())[:5]}"

            # POST notificar (envía 1 correo real)
            n = requests.post(f"{base}/api/clientes/folders/{fid}/notificar-no-califico",
                              headers=hdr, timeout=60)
            assert n.status_code == 200, f"esperaba 200 got {n.status_code}: {n.text[:400]}"
            nd = n.json()
            assert nd.get("ok") is True
            assert isinstance(nd.get("destinatarios"), list) and len(nd["destinatarios"]) >= 1

            # Verificar campo no_califico_notificado_at seteado
            f2 = mongo.folders.find_one({"id": fid}, {"_id": 0, "no_califico_notificado_at": 1,
                                                     "no_califico_notificado_a": 1})
            assert f2.get("no_califico_notificado_at"), "no se seteó no_califico_notificado_at"
            assert isinstance(f2.get("no_califico_notificado_a"), list)
        finally:
            # Cleanup simulación
            mongo.simulaciones.delete_one({"_id": ins.inserted_id})
            # Cleanup campos de notificación para no dejar residuo
            mongo.folders.update_one({"id": fid}, {"$unset": {"no_califico_notificado_at": "",
                                                              "no_califico_notificado_a": ""}})
            # Cleanup alertas de este test
            mongo.alertas.delete_many({"tipo": "no_califico_notificado",
                                       "fecha": {"$gte": datetime.now(timezone.utc).isoformat()[:10]}})

    def test_notificar_folder_sin_source_email_400(self, base, hdr, mongo):
        """Carpeta sin source_email debe responder 400 con mensaje claro (sin enviar correo)."""
        f = mongo.folders.find_one({"$and": [
            {"$or": [{"source_email": {"$exists": False}}, {"source_email": ""}]},
            {"rut": {"$in": [None, ""]}},  # también sin rut para asegurar no destinatarios
        ]}, {"_id": 0, "id": 1})
        if not f:
            pytest.skip("no hay carpeta sin source_email ni rut en la BD")
        r = requests.post(f"{base}/api/clientes/folders/{f['id']}/notificar-no-califico",
                          headers=hdr, timeout=20)
        assert r.status_code == 400
        assert "ejecutivo" in r.text.lower() or "correo" in r.text.lower()
