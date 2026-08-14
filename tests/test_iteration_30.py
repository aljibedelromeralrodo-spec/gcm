"""
Iteration 30: Tests for prompts (1)-(9) session — brokers, fuentes IMAP, hitos,
control auditor, flujos usada/inmobiliaria, mi correo, GRID-DASHAI, radar de
escrituración, gerencia.
"""
import io
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://risk-assess-17.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

ADMIN = ("administrador", "141617575")
BROKER1 = ("broker1", "broker123")
MUTUARIA = ("mutuaria", "mutuaria2026")
CLAVE_FIRMA = "141617575"


def _login(rut, password):
    r = requests.post(f"{API}/auth/login", json={"rut": rut, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {rut} failed: {r.status_code} {r.text}"
    return r.json()["token"]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def admin_token():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def broker_token():
    return _login(*BROKER1)


@pytest.fixture(scope="module")
def mutuaria_token():
    return _login(*MUTUARIA)


# ---------------- 1. Constitución v15 ----------------
class TestConstitucion:
    def test_version_y_reglas(self, admin_token):
        r = requests.get(f"{API}/constitucion", headers=_h(admin_token), timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert data.get("version") == 15, f"Expected v15, got {data.get('version')}"
        # reglas may be under 'reglas' as list of {n:..} or dict
        reglas_raw = data.get("reglas") or data.get("REGLAS_ORO") or []
        # normalize to a set of ints
        ids = set()
        if isinstance(reglas_raw, list):
            for r_item in reglas_raw:
                if isinstance(r_item, dict):
                    n = r_item.get("n") or r_item.get("id") or r_item.get("numero")
                    if n is not None:
                        try:
                            ids.add(int(n))
                        except Exception:
                            pass
        elif isinstance(reglas_raw, dict):
            for k in reglas_raw.keys():
                try:
                    ids.add(int(k))
                except Exception:
                    pass
        for expected in [34, 35, 36, 37, 38, 41, 43]:
            assert expected in ids, f"Regla #{expected} missing. Got ids={sorted(ids)}"


# ---------------- 2. Brokers ----------------
class TestBrokers:
    def test_broker_solo_ve_sus_carpetas(self, broker_token):
        r = requests.get(f"{API}/broker/carpetas", headers=_h(broker_token), timeout=20)
        assert r.status_code == 200
        data = r.json()
        carpetas = data if isinstance(data, list) else data.get("carpetas", [])
        assert len(carpetas) == 1, f"Broker1 should see exactly 1 carpeta, got {len(carpetas)}"
        # nombre debe contener CLIENTE PRUEBA
        nombres = " ".join(str(c) for c in carpetas).upper()
        assert "PRUEBA" in nombres or "BROKER" in nombres

    def test_broker_no_acceso_clientes_folders(self, broker_token):
        r = requests.get(f"{API}/clientes/folders", headers=_h(broker_token), timeout=20)
        assert r.status_code == 403, f"Expected 403, got {r.status_code}"

    def test_mutuaria_ve_10_clientes_estado(self, mutuaria_token):
        r = requests.get(f"{API}/broker/estado-situacion", headers=_h(mutuaria_token), timeout=30)
        assert r.status_code == 200
        data = r.json()
        rows = data.get("situacion", data.get("clientes", data.get("rows", []))) if isinstance(data, dict) else data
        assert len(rows) == 10, f"Expected 10 clients, got {len(rows)}"


# ---------------- 3. Fuentes IMAP + auditoría ----------------
class TestFuentesIMAP:
    def test_clave_incorrecta_403(self, admin_token):
        r = requests.post(
            f"{API}/fuentes/victoria",
            headers=_h(admin_token),
            json={"aliados": [{"nombre": "test", "email": "x@y.cl", "etiqueta": "TEST"}], "clave": "WRONG"},
            timeout=20,
        )
        assert r.status_code == 403, f"Expected 403 wrong clave, got {r.status_code}: {r.text[:200]}"

    def test_sin_etiqueta_400(self, admin_token):
        r = requests.post(
            f"{API}/fuentes/victoria",
            headers=_h(admin_token),
            json={"aliados": [{"nombre": "test", "email": "x@y.cl"}], "clave": CLAVE_FIRMA},
            timeout=20,
        )
        assert r.status_code == 400, f"Expected 400 no etiqueta, got {r.status_code}: {r.text[:200]}"

    def test_clave_correcta_ok_y_auditoria(self, admin_token):
        cur = requests.get(f"{API}/fuentes/victoria", headers=_h(admin_token), timeout=20)
        assert cur.status_code == 200
        current = cur.json()
        aliados = current.get("aliados") or []
        correo = current.get("correo_principal") or ""
        if not aliados:
            aliados = [{"nombre": "TEST_alias", "email": "test@test.cl", "etiqueta": "TEST"}]
        for a in aliados:
            a.setdefault("etiqueta", "TEST")
        r = requests.post(
            f"{API}/fuentes/victoria",
            headers=_h(admin_token),
            json={"correo_principal": correo, "aliados": aliados, "clave": CLAVE_FIRMA},
            timeout=20,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"

        aud = requests.get(f"{API}/fuentes/auditoria", headers=_h(admin_token), timeout=20)
        assert aud.status_code == 200
        events = aud.json().get("auditoria", [])
        assert isinstance(events, list), "auditoria no es lista"


# ---------------- 4. Control auditor ----------------
class TestControlAuditor:
    def test_discrepancias_shape(self, admin_token):
        r = requests.get(f"{API}/control/discrepancias", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "destinatario_maestro" in data, f"Missing destinatario_maestro. Keys={list(data.keys())}"
        assert data.get("no_interferencia") is True, f"no_interferencia should be True"

    def test_control_config_guarda_email(self, admin_token):
        r = requests.post(
            f"{API}/control/config",
            headers=_h(admin_token),
            json={"destinatario_maestro": "test-audit@centralmutuos.cl"},
            timeout=20,
        )
        assert r.status_code == 200, f"POST config failed: {r.status_code} {r.text[:200]}"

    def test_alerta_sin_discrepancias_400(self, admin_token):
        rr = requests.get(f"{API}/control/discrepancias", headers=_h(admin_token), timeout=30)
        data = rr.json()
        discreps = data.get("discrepancias", []) or data.get("items", [])
        discrep_ids = {d.get("carpeta_id") or d.get("fid") or d.get("folder_id") for d in discreps if isinstance(d, dict)}
        cf = requests.get(f"{API}/clientes/folders", headers=_h(admin_token), timeout=30)
        if cf.status_code != 200:
            pytest.skip("cannot list folders")
        payload = cf.json()
        folders = payload if isinstance(payload, list) else payload.get("folders", payload.get("carpetas", []))
        candidate = None
        for f in folders:
            fid = f.get("id") or f.get("_id") or f.get("carpeta_id")
            if fid and fid not in discrep_ids:
                candidate = fid
                break
        if not candidate:
            pytest.skip("no clean folder available")
        r = requests.post(f"{API}/control/alerta/{candidate}", headers=_h(admin_token),
                          json={"confirm": False}, timeout=20)
        assert r.status_code == 400, f"Expected 400 sin discrepancias, got {r.status_code}: {r.text[:200]}"


# ---------------- 5. Hitos feed, flujos, radar ----------------
class TestHitosFlujos:
    def test_feed_hitos(self, admin_token):
        r = requests.get(f"{API}/hitos/feed", headers=_h(admin_token), timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert "hitos" in data or "descartados" in data, f"Keys={list(data.keys())}"

    def test_inmobiliarias_seed(self, admin_token):
        r = requests.get(f"{API}/flujos/inmobiliarias", headers=_h(admin_token), timeout=20)
        assert r.status_code == 200
        data = r.json()
        items = data if isinstance(data, list) else data.get("inmobiliarias", data.get("contactos", []))
        names = " ".join([(x.get("inmobiliaria", "") or x.get("nombre", "")) if isinstance(x, dict) else str(x) for x in items]).upper()
        for n in ["MAESTRA", "COMAC", "BESTAL"]:
            assert n in names, f"{n} missing in {names[:200]}"

    def test_contactos_visita(self, admin_token):
        r = requests.get(f"{API}/flujos/contactos-visita", headers=_h(admin_token), timeout=20)
        assert r.status_code == 200


# ---------------- 6. Radar de Escrituración ----------------
class TestRadar:
    def test_radar_shape(self, admin_token):
        r = requests.get(f"{API}/flujos/radar", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200
        data = r.json()
        rows = data if isinstance(data, list) else data.get("radar", data.get("carpetas", []))
        assert len(rows) > 0, "Radar vacío"
        sample = rows[0]
        assert "doc20" in sample, f"doc20 missing. Keys={list(sample.keys())}"
        assert "firmas" in sample
        assert "hito_firmas" in sample

    def test_firma_parcial_no_es_ok(self, admin_token):
        # find CLIENTE PRUEBA BROKER
        r = requests.get(f"{API}/flujos/radar", headers=_h(admin_token), timeout=30)
        rows = r.json() if isinstance(r.json(), list) else r.json().get("radar", r.json().get("carpetas", []))
        target = None
        for row in rows:
            nom = str(row.get("cliente", row.get("nombre", ""))).upper()
            if "PRUEBA" in nom and "BROKER" in nom:
                target = row
                break
        if not target:
            # fallback: any row that has codeudor
            for row in rows:
                fs = row.get("firmas", {}) or {}
                if fs.get("codeudor") is not None:
                    target = row
                    break
        if not target:
            pytest.skip("no test folder found for firma parcial")
        fid = target.get("carpeta_id") or target.get("fid") or target.get("id")
        # POST firma titular=firmado
        p = requests.post(
            f"{API}/flujos/firmas/{fid}",
            headers=_h(admin_token),
            json={"rol": "titular", "estado": "firmado"},
            timeout=20,
        )
        assert p.status_code == 200, f"POST firma failed: {p.status_code} {p.text[:200]}"
        # verify hito_firmas != ok
        r2 = requests.get(f"{API}/flujos/radar", headers=_h(admin_token), timeout=30)
        rows2 = r2.json() if isinstance(r2.json(), list) else r2.json().get("radar", r2.json().get("carpetas", []))
        updated = next((x for x in rows2 if (x.get("carpeta_id") or x.get("fid") or x.get("id")) == fid), None)
        assert updated is not None
        hf = updated.get("hito_firmas")
        assert hf != "ok", f"hito_firmas should NOT be 'ok' with partial signatures, got {hf}"

        # revertir
        rev = requests.post(
            f"{API}/flujos/firmas/{fid}",
            headers=_h(admin_token),
            json={"rol": "titular", "estado": "pendiente"},
            timeout=20,
        )
        assert rev.status_code == 200

    def test_fecha_firma(self, admin_token):
        r = requests.get(f"{API}/flujos/radar", headers=_h(admin_token), timeout=30)
        rows = r.json() if isinstance(r.json(), list) else r.json().get("radar", r.json().get("carpetas", []))
        target = None
        for row in rows:
            nom = str(row.get("cliente", row.get("nombre", ""))).upper()
            if "PRUEBA" in nom and "BROKER" in nom:
                target = row
                break
        if not target:
            pytest.skip("no PRUEBA BROKER folder")
        fid = target.get("carpeta_id") or target.get("fid") or target.get("id")
        p = requests.post(
            f"{API}/flujos/fecha-firma/{fid}",
            headers=_h(admin_token),
            json={"fecha": "2026-06-25"},
            timeout=20,
        )
        assert p.status_code == 200, f"fecha-firma failed: {p.status_code} {p.text[:200]}"


# ---------------- 7. GRID-DASHAI ----------------
class TestGrid:
    def test_grid_estado(self, admin_token):
        r = requests.get(f"{API}/grid/estado", headers=_h(admin_token), timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert data.get("bloqueo_desactivacion") is True, f"bloqueo_desactivacion should be True, got {data}"
        assert data.get("permanente") is True
        assert (data.get("archivos_espejo") or 0) > 0

    def test_grid_eventos(self, admin_token):
        r = requests.get(f"{API}/grid/eventos?desde_seq=0", headers=_h(admin_token), timeout=20)
        assert r.status_code == 200

    def test_grid_resync(self, admin_token):
        r = requests.post(f"{API}/grid/resync", headers=_h(admin_token), timeout=60)
        assert r.status_code == 200, f"resync failed: {r.status_code} {r.text[:200]}"


# ---------------- 8. Broker RUT audit ----------------
def _pdf_with_text(text):
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
    except ImportError:
        pytest.skip("reportlab not installed")
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.drawString(100, 700, text)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()


class TestBrokerUploadRUT:
    def _find_broker_folder(self, broker_token):
        r = requests.get(f"{API}/broker/carpetas", headers=_h(broker_token), timeout=20)
        assert r.status_code == 200
        data = r.json()
        carpetas = data if isinstance(data, list) else data.get("carpetas", [])
        assert len(carpetas) > 0
        c = carpetas[0]
        return c.get("id") or c.get("_id") or c.get("carpeta_id") or c.get("fid")

    def test_rut_mismatch_rechazado_y_match_aceptado(self, broker_token):
        fid = self._find_broker_folder(broker_token)
        assert fid, "no broker folder id"

        # WRONG RUT
        wrong_pdf = _pdf_with_text("RUT 99.999.999-9 - carta test")
        r_wrong = requests.post(
            f"{API}/broker/carpetas/{fid}/upload",
            headers=_h(broker_token),
            data={"categoria": "carta_enmienda"},
            files={"archivo": ("wrong.pdf", wrong_pdf, "application/pdf")},
            timeout=60,
        )
        assert r_wrong.status_code == 422, f"Expected 422 wrong RUT, got {r_wrong.status_code}: {r_wrong.text[:300]}"

        # CORRECT RUT
        good_pdf = _pdf_with_text("RUT 11.111.111-1 - carta enmienda test")
        r_good = requests.post(
            f"{API}/broker/carpetas/{fid}/upload",
            headers=_h(broker_token),
            data={"categoria": "carta_enmienda"},
            files={"archivo": ("TEST_good.pdf", good_pdf, "application/pdf")},
            timeout=60,
        )
        assert r_good.status_code == 200, f"Expected 200 good RUT, got {r_good.status_code}: {r_good.text[:300]}"

        # actividad registra huella
        act = requests.get(f"{API}/broker/actividad", headers=_h(broker_token), timeout=20)
        assert act.status_code == 200
        acts_str = str(act.json()).lower()
        assert "rechaz" in acts_str, "actividad no registra archivo_rechazado"
        assert "sub" in acts_str, "actividad no registra archivo_subido"

        # cleanup: try to delete the uploaded test file
        requests.post(
            f"{API}/broker/carpetas/{fid}/delete",
            headers=_h(broker_token),
            json={"archivo": "TEST_good.pdf"},
            timeout=20,
        )


# ---------------- 9. Gerencia cartera ----------------
class TestGerencia:
    def test_cartera_cols(self, admin_token):
        r = requests.get(f"{API}/gerencia/cartera", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200
        data = r.json()
        rows = data if isinstance(data, list) else data.get("cartera", data.get("rows", []))
        assert len(rows) > 0, "cartera vacía"
        s = rows[0]
        expected = ["broker_origen", "tipo_operacion", "tasacion_estado", "estudio_estado",
                    "doc20", "firmas", "hito_firmas", "fecha_firma"]
        missing = [k for k in expected if k not in s]
        assert not missing, f"Missing keys: {missing}. Available: {list(s.keys())}"

    def test_export_xlsx(self, admin_token):
        r = requests.get(f"{API}/gerencia/export-xlsx", headers=_h(admin_token), timeout=60)
        assert r.status_code == 200, f"export-xlsx failed: {r.status_code}"
        ct = r.headers.get("content-type", "")
        assert "sheet" in ct or "xlsx" in ct or "octet" in ct, f"Unexpected content-type: {ct}"
