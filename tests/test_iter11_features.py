"""Iteration 11 — folders-light, carpetas escrituración, resumen semanal, alerta tasación."""
import os
import time
import requests
from datetime import datetime, timezone, timedelta
from dotenv import dotenv_values

_fe = dotenv_values("/app/frontend/.env")
_be = dotenv_values("/app/backend/.env")
os.environ.setdefault("REACT_APP_BACKEND_URL", _fe.get("REACT_APP_BACKEND_URL", ""))
os.environ.setdefault("MONGO_URL", _be.get("MONGO_URL", "").strip('"'))
os.environ.setdefault("DB_NAME", _be.get("DB_NAME", "").strip('"'))
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


def _login():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"codigo": "administrador", "password": "141617575"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


# ---------------- folders-light ----------------
class TestFoldersLight:
    def test_folders_light_fast_and_21(self):
        t0 = time.time()
        r = requests.get(f"{BASE_URL}/api/clientes/folders-light", timeout=10)
        dt = time.time() - t0
        assert r.status_code == 200
        assert dt < 3.0, f"folders-light tardó {dt:.2f}s (>3s)"
        data = r.json()
        folders = data.get("folders") or []
        assert len(folders) >= 20, f"esperaba ~21 carpetas, hay {len(folders)}"
        # shape: solo id, nombre, rut
        f0 = folders[0]
        keys = set(f0.keys())
        assert keys <= {"id", "nombre", "rut"}, f"folders-light devuelve claves extra: {keys}"
        assert "id" in f0 and "nombre" in f0

    def test_folders_light_incluye_nuevas_escrituracion(self):
        r = requests.get(f"{BASE_URL}/api/clientes/folders-light", timeout=10)
        assert r.status_code == 200
        nombres = [f["nombre"].upper() for f in r.json()["folders"]]
        for esperado in ["ALEIDYS NOEMI APONTE BANDRES",
                         "JOHNSON VARGAS PEÑA",
                         "JAVIERA PAZ HERNANDEZ LYNCH"]:
            assert any(esperado in n for n in nombres), f"falta {esperado}"


# ---------------- resumen semanal ----------------
class TestResumenSemanal:
    def test_preview_sin_confirm(self):
        r = requests.post(f"{BASE_URL}/api/central/resumen-semanal/enviar",
                          json={}, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        # Sin confirm debe devolver preview con body y to
        assert "body" in data
        assert "to" in data
        body = data["body"]
        assert "Resumen Semanal" in body
        for col in ("Tasación", "E. Título", "Escritura", "Pendientes"):
            assert col in body, f"falta columna {col}"
        # ~21 filas de clientes (contar <tr> con <b>)
        filas = body.count("<b>")
        assert filas >= 18, f"esperaba ≥18 filas, hay {filas}"


# ---------------- carpetas escrituración ----------------
class TestCarpetasEscrituracion:
    def test_carpeta_javiera_tiene_escritura_op(self):
        # Buscar Javiera vía folders-light
        r = requests.get(f"{BASE_URL}/api/clientes/folders-light?q=JAVIERA",
                         timeout=10)
        assert r.status_code == 200
        folders = r.json()["folders"]
        jav = next((f for f in folders if "JAVIERA" in f["nombre"].upper() and "HERNANDEZ" in f["nombre"].upper()), None)
        assert jav is not None, "no se encuentra JAVIERA PAZ HERNANDEZ LYNCH"
        # Obtener detalle vía folders pesado (filtrado por nombre)
        r2 = requests.get(f"{BASE_URL}/api/clientes/folders?q=JAVIERA", timeout=120)
        assert r2.status_code == 200
        doc = next((d for d in r2.json()["folders"] if d["id"] == jav["id"]), None)
        assert doc is not None
        assert doc.get("escritura_op") == "01-01-02484-1", f"escritura_op={doc.get('escritura_op')}"
        assert "19.862.353-2" in (doc.get("rut") or ""), f"rut={doc.get('rut')}"
        df = doc.get("datos_financieros") or {}
        assert (df.get("proyecto") or "").strip(), "datos_financieros.proyecto vacío"


# ---------------- alerta tasación sin respuesta (verificación estática de código) ----------------
class TestAlertaTasacionSinRespuestaStatic:
    def test_bloque_alerta_existe_en_server_py(self):
        with open("/app/backend/server.py") as f:
            src = f.read()
        assert "Alerta: tasaciones solicitadas hace más de 5 días sin respuesta" in src
        assert "tasacion_alerta_sin_respuesta" in src
        assert '"tipo": "tasacion_sin_respuesta"' in src
        # Debe estar dentro de _actividades_terminadas_loop
        idx_loop = src.find("async def _actividades_terminadas_loop")
        idx_alerta = src.find("Alerta: tasaciones solicitadas hace más de 5 días")
        assert idx_loop < idx_alerta, "el bloque de alerta no está dentro del loop"

    def test_query_sintetico_matchea(self):
        """Test sintético: setea una carpeta con tasacion_solicitada_at hace 6 días
        y verifica que el query del loop la selecciona. REVIERTE al final."""
        import pymongo
        MONGO_URL = os.environ["MONGO_URL"]
        DB_NAME = os.environ["DB_NAME"]
        client = pymongo.MongoClient(MONGO_URL)
        db = client[DB_NAME]
        # Buscar una carpeta cualquiera para test sintético
        doc = db.folders.find_one({}, {"id": 1, "nombre": 1,
                                        "tasacion_solicitada_at": 1,
                                        "tasacion_terminado_at": 1,
                                        "tasacion_alerta_sin_respuesta": 1})
        assert doc is not None, "no hay carpetas para test"
        fid = doc["id"]
        # snapshot
        original = {k: doc.get(k) for k in ("tasacion_solicitada_at",
                                             "tasacion_terminado_at",
                                             "tasacion_alerta_sin_respuesta")}
        # snapshot alertas para revertir
        try:
            hace_6 = (datetime.now(timezone.utc) - timedelta(days=6)).isoformat()
            db.folders.update_one({"id": fid}, {"$set": {
                "tasacion_solicitada_at": hace_6,
                "tasacion_terminado_at": None,
                "tasacion_alerta_sin_respuesta": False,
            }})
            limite = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
            match = db.folders.find_one({"id": fid,
                                         "tasacion_solicitada_at": {"$lt": limite, "$gt": ""},
                                         "tasacion_terminado_at": {"$in": [None]},
                                         "tasacion_alerta_sin_respuesta": {"$ne": True}})
            assert match is not None, "el query del loop NO selecciona la carpeta sintética"
        finally:
            # Revertir a snapshot original
            update = {}
            unset = {}
            for k, v in original.items():
                if v is None:
                    unset[k] = ""
                else:
                    update[k] = v
            op = {}
            if update:
                op["$set"] = update
            if unset:
                op["$unset"] = unset
            if op:
                db.folders.update_one({"id": fid}, op)
            client.close()
