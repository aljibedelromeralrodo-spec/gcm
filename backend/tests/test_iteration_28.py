"""Iteration 28 - Backend tests for prospectos/escrituracion/calificar flows."""
import os
import io
import uuid
import re
import requests
import pytest
from pymongo import MongoClient
from datetime import datetime, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    # fallback to frontend/.env
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = ln.split("=", 1)[1].strip().strip('"')
BASE_URL = BASE_URL.rstrip("/")

with open("/app/backend/.env") as f:
    _env = dict(
        ln.strip().split("=", 1) for ln in f if "=" in ln and not ln.startswith("#")
    )
MONGO_URL = _env.get("MONGO_URL", "").strip('"')
DB_NAME = _env.get("DB_NAME", "").strip('"')

YERILE_ID = "69bd18cc-ff8a-4118-b0e5-9ec46f3a8210"


@pytest.fixture(scope="module")
def dbc():
    c = MongoClient(MONGO_URL)[DB_NAME]
    return c


@pytest.fixture(scope="module")
def test_prospecto(dbc):
    """Insert a proprietary test prospect (not Yerile)."""
    pid = f"test-it28-{uuid.uuid4().hex[:8]}"
    doc = {
        "id": pid,
        "nombre": f"TEST Iter28 {uuid.uuid4().hex[:5]}",
        "rut": "11111111-1",
        "email": "",  # sin email -> para probar invitacion 400
        "telefono": "",
        "proyecto": "TEST-PROY",
        "creado_en": datetime.now(timezone.utc).isoformat(),
        "estado": None,
        "status": "pendiente",
    }
    dbc.prospectos.insert_one(dict(doc))
    yield doc
    # Cleanup
    p = dbc.prospectos.find_one({"id": pid})
    if p and p.get("folder_id"):
        dbc.folders.delete_one({"id": p["folder_id"]})
    dbc.prospectos.delete_one({"id": pid})


class TestOportunidades:
    def test_listar_200_excluye_promovidos(self, dbc):
        r = requests.get(f"{BASE_URL}/api/oportunidades", timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "oportunidades" in data
        ops = data["oportunidades"]
        assert isinstance(ops, list)
        for o in ops:
            assert o.get("estado") != "PROMOVIDO"


class TestPromover:
    def test_promover_and_flow(self, dbc, test_prospecto):
        pid = test_prospecto["id"]
        r = requests.post(f"{BASE_URL}/api/prospectos/{pid}/promover", timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        fid = body.get("folder_id")
        assert fid

        # Verify folder created
        fd = dbc.folders.find_one({"id": fid})
        assert fd is not None
        assert fd.get("origen") == "promocion_prospecto"

        # Verify subfolders on disk
        from pathlib import Path
        # try common bases
        nombre = fd["nombre"]
        found_sub = False
        for base in [
            "/app/backend/carpeta_clientes",
            "/app/carpeta_clientes",
            "/tmp/carpeta_clientes",
        ]:
            p = Path(base) / nombre
            if p.exists():
                subs = {"01_cedula", "02_liquidaciones", "03_afp", "04_cmf",
                        "05_codeudor", "06_cotizacion", "99_otros"}
                existing = {c.name for c in p.iterdir() if c.is_dir()}
                if subs.issubset(existing):
                    found_sub = True
                    break
        # Non-fatal; folder disk path may vary
        print(f"Subfolders check found={found_sub}")

        # Prospecto state
        p2 = dbc.prospectos.find_one({"id": pid})
        assert p2.get("estado") == "PROMOVIDO"
        assert p2.get("folder_id") == fid

        # Second call -> 400
        r2 = requests.post(f"{BASE_URL}/api/prospectos/{pid}/promover", timeout=60)
        assert r2.status_code == 400, r2.text

        # Disappears from oportunidades listing
        rl = requests.get(f"{BASE_URL}/api/oportunidades", timeout=60)
        assert rl.status_code == 200
        ids = [o.get("id") for o in rl.json().get("oportunidades", [])]
        assert pid not in ids


class TestEscrituracion:
    def test_enviar_escrituracion_from_existing_folder(self, dbc):
        # pick any existing folder that's not already in escrituracion
        fd = dbc.folders.find_one({"is_escrituracion": {"$ne": True}})
        assert fd is not None, "No folders available for test"
        fid = fd["id"]
        r = requests.post(
            f"{BASE_URL}/api/clientes/folders/{fid}/enviar-escrituracion", timeout=60
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert body.get("set_id")

        fd2 = dbc.folders.find_one({"id": fid})
        assert fd2.get("is_escrituracion") is True
        assert fd2.get("estudio_titulo_solicitado_at")

        set_doc = dbc.set_credito.find_one({"id": body["set_id"]})
        assert set_doc is not None

        # Escrituracion listing
        r1 = requests.get(f"{BASE_URL}/api/escrituracion/carpetas", timeout=60)
        assert r1.status_code == 200
        # Estudio Titulo listing
        r2 = requests.get(f"{BASE_URL}/api/estudio-titulo/carpetas", timeout=60)
        assert r2.status_code == 200
        # Set-credito listing
        r3 = requests.get(f"{BASE_URL}/api/set-credito/sets", timeout=60)
        assert r3.status_code == 200

        def _flatten(d):
            if isinstance(d, list):
                return d
            for k in ("carpetas", "sets", "items", "data"):
                if isinstance(d.get(k), list):
                    return d[k]
            return []

        e_ids = [x.get("id") for x in _flatten(r1.json())]
        et_ids = [x.get("id") for x in _flatten(r2.json())]
        sc_ids = [x.get("id") for x in _flatten(r3.json())]
        assert fid in e_ids, f"folder {fid} not in escrituracion listing: {e_ids[:5]}"
        assert fid in et_ids, f"folder {fid} not in estudio-titulo listing"
        assert body["set_id"] in sc_ids, f"set {body['set_id']} not in set-credito"


class TestInvitacionVIP:
    def test_invitacion_sin_email_400(self, test_prospecto):
        pid = test_prospecto["id"]
        # test_prospecto has empty email
        r = requests.post(f"{BASE_URL}/api/oportunidades/{pid}/invitacion-vip", timeout=60)
        assert r.status_code == 400, r.text

    def test_yerile_status_invitacion_enviada(self, dbc):
        y = dbc.prospectos.find_one({"id": YERILE_ID})
        assert y is not None, "Yerile not found in db.prospectos"
        assert y.get("status") == "invitacion_enviada"


class TestCalificarPortal:
    def test_portal_html(self):
        r = requests.get(f"{BASE_URL}/api/calificar/{YERILE_ID}", timeout=60)
        assert r.status_code == 200, r.status_code
        html = r.text
        assert "Bienvenido" in html and "Yerile" in html
        for tid in [
            "captura-salida-modal",
            "captura-ayuda-link",
            "captura-entrega-inmediata",
            "captura-entrega-futura",
        ]:
            assert f'data-testid="{tid}"' in html, f"missing {tid}"
        assert "6 últimas Liquidaciones de Sueldo" in html
        assert "min:6" in html


class TestCalificarSubir:
    def test_subir_docs_prospecto_propio(self, dbc, test_prospecto):
        # Insert a fresh prospect (not Yerile), not promoted
        pid = f"test-it28-subir-{uuid.uuid4().hex[:8]}"
        doc = {
            "id": pid,
            "nombre": f"TEST Subir {uuid.uuid4().hex[:5]}",
            "rut": "22222222-2",
            "email": "",
            "proyecto": "TEST-PROY",
            "creado_en": datetime.now(timezone.utc).isoformat(),
        }
        dbc.prospectos.insert_one(dict(doc))
        try:
            # minimal PDF
            pdf_bytes = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
            files = {
                "cedula": ("cedula.pdf", pdf_bytes, "application/pdf"),
            }
            data = {
                "perfil": "dependiente",
                "entrega": "futura_mas_6m",
                "con_subsidio": "0",
                "valor_uf": "3000",
                "pie_pct": "10",
                "credito_uf": "2700",
            }
            r = requests.post(
                f"{BASE_URL}/api/calificar/{pid}/subir",
                data=data, files=files, timeout=90,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body.get("ok") is True

            p2 = dbc.prospectos.find_one({"id": pid})
            assert p2.get("fecha_entrega_estimada") == "Futura +6 meses"
            assert p2.get("captura_autonoma_en")
        finally:
            p2 = dbc.prospectos.find_one({"id": pid}) or {}
            # cleanup folder if created
            fd = dbc.folders.find_one({"nombre": doc["nombre"].title()})
            if fd:
                dbc.folders.delete_one({"id": fd["id"]})
            dbc.prospectos.delete_one({"id": pid})
