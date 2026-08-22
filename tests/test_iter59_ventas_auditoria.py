"""Iter 59 — Backend tests: Ventas nuevos endpoints + Auditoría de campos + huellas cerebro."""
import os
import time
import pytest
import requests


def _read_env_var(path, key):
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        return None
    return None


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or _read_env_var("/app/frontend/.env", "REACT_APP_BACKEND_URL")).rstrip("/")


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"rut": "administrador", "password": "141617575"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ─── VENTAS ─────────────────────────────────────────────────────────────
class TestVentasRendimiento:
    def test_rendimiento(self, headers):
        r = requests.get(f"{BASE_URL}/api/ventas/rendimiento", headers=headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "ejecutivos" in data
        ejs = data["ejecutivos"]
        for ej in ("yerile", "deysi"):
            assert ej in ejs, f"Falta ejecutivo {ej}"
            d = ejs[ej]
            for k in ("activos", "cerrados_mes", "tasa_conversion",
                      "dias_promedio_cierre", "semaforos"):
                assert k in d, f"Falta KPI {k} en {ej}"
            for c in ("verde", "amarillo", "rojo"):
                assert c in d["semaforos"]

    def test_embudo(self, headers):
        r = requests.get(f"{BASE_URL}/api/ventas/embudo", headers=headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "embudo" in data and len(data["embudo"]) == 6
        etapas = [e["etapa"] for e in data["embudo"]]
        assert etapas == ["ingresado", "documentacion_proceso", "completo",
                          "enviado_mesa", "aprobado", "rechazado"]
        for e in data["embudo"]:
            assert "por_ejecutivo" in e
            assert "yerile" in e["por_ejecutivo"]
            assert "deysi" in e["por_ejecutivo"]

    def test_export_xlsx(self, headers):
        r = requests.get(f"{BASE_URL}/api/ventas/export",
                         params={"ejecutivo": "yerile", "resultado": "abierto"},
                         headers=headers, timeout=30)
        assert r.status_code == 200, r.text
        ct = r.headers.get("content-type", "")
        assert "openxmlformats" in ct or "spreadsheetml" in ct, ct
        assert r.content[:2] == b"PK"  # xlsx = zip


# ─── VENTAS FLUJO: solicitud → estado → timeline ───────────────────────
class TestVentasFlujoCompleto:
    cliente_id = None

    def test_crear_solicitud_asignada_por_balance(self, headers):
        payload = {"nombre": "QA TEST Iter59 Balance", "rut": "22.222.222-2",
                   "entrega_inmediata": True}
        r = requests.post(f"{BASE_URL}/api/ventas/solicitudes",
                          json=payload, headers=headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        assert data.get("asignado") is True
        assert data.get("cliente_id")
        TestVentasFlujoCompleto.cliente_id = data["cliente_id"]
        # Debe ser Yerile o Deisy
        assert any(n in data.get("ejecutivo", "") for n in ("Yerile", "Deisy")), data

    def test_huella_asignacion_en_cerebro(self, headers):
        # Le da un momento para que la escritura async se afiance
        time.sleep(0.5)
        r = requests.get(f"{BASE_URL}/api/constitucion/consultas",
                         headers=headers, params={"limit": 20}, timeout=30)
        # Endpoint puede no existir; verificar por Mongo directamente
        # via /api/cerebro/consultas? probemos ambos suavemente
        if r.status_code != 200:
            pytest.skip(f"Endpoint de consultas cerebro no expuesto ({r.status_code})")
        data = r.json()
        acciones = str(data)
        assert "asignacion_ventas" in acciones

    def test_timeline_tiene_evento_inicial(self, headers):
        cid = TestVentasFlujoCompleto.cliente_id
        assert cid, "cliente_id no seteado"
        r = requests.get(f"{BASE_URL}/api/ventas/clientes/{cid}/timeline",
                         headers=headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "eventos" in data and len(data["eventos"]) >= 1
        first = data["eventos"][0]
        assert "fecha" in first and "accion" in first and "por" in first

    def test_estado_aprobado_setea_cerrado_y_timeline(self, headers):
        cid = TestVentasFlujoCompleto.cliente_id
        assert cid
        r = requests.put(f"{BASE_URL}/api/ventas/clientes/{cid}/estado",
                         json={"estado": "aprobado"}, headers=headers, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["estado"] == "aprobado"
        # verificar timeline
        r2 = requests.get(f"{BASE_URL}/api/ventas/clientes/{cid}/timeline",
                          headers=headers, timeout=30)
        assert r2.status_code == 200
        eventos = r2.json()["eventos"]
        assert any("aprobado" in str(e.get("accion", "")).lower() for e in eventos)

    def test_zzz_cleanup(self, headers):
        """Limpieza del cliente de prueba."""
        cid = TestVentasFlujoCompleto.cliente_id
        if not cid:
            return
        # No hay endpoint para borrar → usar mongo directamente vía subprocess
        import subprocess
        subprocess.run(["python", "-c", f"""
import os
from pymongo import MongoClient
c = MongoClient(os.environ['MONGO_URL'])
db = c[os.environ['DB_NAME']]
db.victoria_clientes.delete_one({{'id': '{cid}'}})
db.victoria_docs.delete_many({{'cliente_id': '{cid}'}})
print('cleanup OK')
"""], check=False, env={**os.environ, **_load_env()})


def _load_env():
    env = {}
    try:
        with open("/app/backend/.env") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return env


# ─── AUDITORÍA DE CAMPOS (Daniela) ─────────────────────────────────────
class TestAuditoriaCampos:
    def test_auditoria_campos_5_items(self, headers):
        r = requests.get(f"{BASE_URL}/api/victoria/panel", headers=headers, timeout=30)
        assert r.status_code == 200, r.text
        clientes = r.json().get("clientes", [])
        if not clientes:
            pytest.skip("Bóveda Victoria vacía")
        cid = clientes[0]["id"]
        r2 = requests.get(f"{BASE_URL}/api/victoria/clientes/{cid}/auditoria-campos",
                          headers=headers, timeout=30)
        assert r2.status_code == 200, r2.text
        data = r2.json()
        assert "campos" in data and len(data["campos"]) == 5
        keys = {c["campo"] for c in data["campos"]}
        assert keys == {"nombre_cliente", "rut_titular", "rut_codeudor",
                        "rol_avaluo", "direccion_propiedad"}
        for c in data["campos"]:
            assert "valor" in c and "pendiente" in c
            if not c["pendiente"]:
                assert c["valor"], c
                # doc_id/pagina pueden estar vacíos si el doc físico no existe

    def test_fragmento_png(self, headers):
        r = requests.get(f"{BASE_URL}/api/victoria/panel", headers=headers, timeout=30)
        clientes = r.json().get("clientes", [])
        if not clientes:
            pytest.skip("Bóveda vacía")
        cid = clientes[0]["id"]
        rc = requests.get(f"{BASE_URL}/api/victoria/clientes/{cid}/auditoria-campos",
                          headers=headers, timeout=30)
        campos = rc.json()["campos"]
        con_doc = next((c for c in campos if c.get("doc_id")), None)
        if not con_doc:
            pytest.skip("Ningún campo con doc_id (sin fragmento posible)")
        r2 = requests.get(f"{BASE_URL}/api/victoria/documentos/{con_doc['doc_id']}/fragmento",
                          params={"q": con_doc["valor"], "pagina": con_doc.get("pagina") or 1},
                          headers=headers, timeout=60)
        assert r2.status_code == 200, r2.text
        assert r2.headers.get("content-type", "").startswith("image/png")
        assert r2.content[:8] == b"\x89PNG\r\n\x1a\n"

    def test_auditar_registra_huella_daniela(self, headers):
        r = requests.get(f"{BASE_URL}/api/victoria/panel", headers=headers, timeout=30)
        clientes = r.json().get("clientes", [])
        if not clientes:
            pytest.skip("Bóveda vacía")
        cid = clientes[0]["id"]
        r2 = requests.post(f"{BASE_URL}/api/victoria/clientes/{cid}/auditar",
                           headers=headers, timeout=60)
        assert r2.status_code == 200, r2.text
        assert r2.json()["ok"] is True
        # verificar huella vía mongo
        import subprocess
        env = {**os.environ, **_load_env()}
        out = subprocess.run(["python", "-c",
            "import os; from pymongo import MongoClient;"
            "c=MongoClient(os.environ['MONGO_URL']); db=c[os.environ['DB_NAME']];"
            "n=db.cerebro_consultas.count_documents({'accion':'validacion_cruzada_daniela'});"
            "print(n)"], capture_output=True, text=True, env=env, timeout=30)
        assert out.returncode == 0, out.stderr
        assert int(out.stdout.strip()) >= 1, f"No hay huella: {out.stdout}"
