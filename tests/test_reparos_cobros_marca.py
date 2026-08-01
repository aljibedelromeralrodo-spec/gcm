"""
Iteration 6 backend tests:
- Reparos Estudio Título (GET/PATCH/scan)
- Cobros Tasación (listado/historial/manual preview)
- Marca formal 'CON CRECES' en previews de correos operativos
- Regla inviolable: gastos operacionales sin CC
- Resumen semanal preview
- Upload/delete de vouchers (voucher_tasacion, voucher_gasto_operacional)

CRITICO: NUNCA usar confirm:true (evita envío real de correos).
"""
import os
import io
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or
            open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0]).strip().rstrip("/")

FID = "a996aa5d-1543-491f-a247-41d8da449138"  # ERNESTO LEONARDO DÍAZ SILVA


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _body(d):
    return (d.get("body") or d.get("preview") or d.get("html") or "").lower()


# ---------- Reparos Estudio Título ----------

class TestReparos:
    def test_get_reparos(self, sess):
        r = sess.get(f"{BASE_URL}/api/estudio-titulo/reparos/{FID}", timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        items = (d.get("reparos") or {}).get("items") or []
        assert len(items) >= 2, f"Expected >=2 reparos, got {items}"
        assert items[0].get("satisfecho") is True, f"item1 debería estar satisfecho: {items[0]}"
        assert items[1].get("satisfecho") is False, f"item2 debería estar pendiente: {items[1]}"
        vendedor = d.get("vendedor") or {}
        assert "Prueba" in (vendedor.get("nombre") or ""), f"vendedor: {vendedor}"

    def test_toggle_item2_and_restore(self, sess):
        # Toggle item 2 -> True
        r = sess.patch(f"{BASE_URL}/api/estudio-titulo/reparos/{FID}/item/2",
                       json={"satisfecho": True}, timeout=20)
        assert r.status_code == 200, r.text

        g = sess.get(f"{BASE_URL}/api/estudio-titulo/reparos/{FID}", timeout=20).json()
        items = (g.get("reparos") or {}).get("items") or []
        assert items[1].get("satisfecho") is True, f"toggle no aplicó: {items}"

        # Restaurar item 2 -> False
        r2 = sess.patch(f"{BASE_URL}/api/estudio-titulo/reparos/{FID}/item/2",
                        json={"satisfecho": False}, timeout=20)
        assert r2.status_code == 200, r2.text
        g2 = sess.get(f"{BASE_URL}/api/estudio-titulo/reparos/{FID}", timeout=20).json()
        items2 = (g2.get("reparos") or {}).get("items") or []
        assert items2[1].get("satisfecho") is False, f"no se restauró: {items2}"
        assert items2[0].get("satisfecho") is True, f"item1 alterado: {items2}"

    def test_scan_no_error(self, sess):
        r = sess.post(f"{BASE_URL}/api/estudio-titulo/reparos/{FID}/scan",
                      json={}, timeout=120)
        assert r.status_code in (200, 202), r.text
        d = r.json()
        assert "error" not in d or d.get("ok") is True, f"scan error: {d}"


# ---------- Cobros Tasación ----------

class TestCobrosTasacion:
    def test_listado(self, sess):
        r = sess.get(f"{BASE_URL}/api/gastos-operacionales/cobros-tasacion", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("monto_uf") == 4.5, f"monto_uf={d.get('monto_uf')}"
        assert "valor_uf" in d and isinstance(d["valor_uf"], (int, float))
        assert "monto_clp" in d
        res = d.get("resumen") or {}
        for k in ("enviadas", "pagadas", "pendientes"):
            assert k in res, f"resumen missing {k}: {res}"

    def test_historial(self, sess):
        r = sess.get(f"{BASE_URL}/api/gastos-operacionales/cobros-tasacion/historial", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "historial" in d, d

    def test_manual_preview(self, sess):
        r = sess.post(f"{BASE_URL}/api/gastos-operacionales/cobros-tasacion/manual",
                      json={"email": "test@example.com", "cliente": "Cliente Prueba"},
                      timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        body = _body(d)
        assert "cuenta recaudadora" in body, f"Falta 'Cuenta Recaudadora' en preview"
        assert "mercado pago" in body, "Falta 'Mercado Pago'"
        assert "1030937838" in body, "Falta cuenta 1030937838"
        assert ("4,5" in body or "4.5" in body), "Falta monto 4,5 UF"
        assert "con creces" in body, "Falta marca 'CON CRECES'"
        # Debe traer sender secundaria (no enviar)
        assert d.get("to") == "test@example.com"


# ---------- Marca 'CON CRECES' en previews ----------

class TestMarcaCorreos:
    def test_gastos_operacionales_enviar_no_cc(self, sess):
        r = sess.post(f"{BASE_URL}/api/gastos-operacionales/enviar",
                      json={"email_cliente": "dest@example.com", "nombre": "Cliente Test",
                            "items": [{"concepto": "Notaría", "valor": 50000}]},
                      timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        # Regla inviolable: sin cc
        assert not d.get("cc"), f"NO debe haber cc: {d.get('cc')}"
        body = _body(d)
        assert "con creces" in body, "Falta marca CON CRECES"

    def test_tasacion_enviar_marca(self, sess):
        r = sess.post(f"{BASE_URL}/api/tasacion/enviar",
                      json={"nombre": "Cliente Prueba", "rut": "11.111.111-1",
                            "direccion": "Calle Falsa 123", "tipo": "casa",
                            "modalidad": "particular", "folder_id": FID},
                      timeout=30)
        assert r.status_code == 200, r.text
        assert "con creces" in _body(r.json()), "Falta marca CON CRECES en tasacion/enviar"

    def test_estudio_titulo_enviar_marca(self, sess):
        r = sess.post(f"{BASE_URL}/api/estudio-titulo/enviar",
                      json={"nombre": "Cliente Prueba", "rut": "11.111.111-1",
                            "tipo_vivienda": "usada",
                            "vendedor_nombre": "Vendedor X",
                            "vendedor_email": "v@x.cl"},
                      timeout=30)
        assert r.status_code == 200, r.text
        assert "con creces" in _body(r.json()), "Falta marca CON CRECES en estudio-titulo/enviar"

    def test_escritura_enviar_marca(self, sess):
        r = sess.post(f"{BASE_URL}/api/escritura/enviar",
                      json={"nombre": "Cliente Prueba", "rut": "11.111.111-1",
                            "email_cliente": "dest@example.com",
                            "fecha": "2026-12-31", "hora": "10:00"},
                      timeout=30)
        assert r.status_code == 200, r.text
        assert "con creces" in _body(r.json()), "Falta marca CON CRECES en escritura/enviar"

    def test_pedir_faltantes_marca(self, sess):
        r = sess.post(f"{BASE_URL}/api/clientes/folders/{FID}/pedir-faltantes",
                      json={"destinatario": "dest@example.com"},
                      timeout=30)
        assert r.status_code == 200, r.text
        assert "con creces" in _body(r.json()), "Falta marca CON CRECES en pedir-faltantes"


# ---------- Resumen semanal preview ----------

class TestResumenSemanal:
    def test_resumen_preview(self, sess):
        r = sess.post(f"{BASE_URL}/api/central/resumen-semanal/enviar",
                      json={}, timeout=180)
        assert r.status_code == 200, r.text
        d = r.json()
        low = _body(d)
        assert "resumen semanal de mart" in low, f"Falta título 'Resumen Semanal de Mart...': {low[:300]}"
        assert "cobros de tasaci" in low, "Falta sección 'Cobros de Tasación'"
        assert "carpetas que necesitan acci" in low, "Falta 'Carpetas que necesitan acción'"


# ---------- Voucher upload/delete ----------

class TestVoucherUpload:
    @staticmethod
    def _pdf():
        return (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
                b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
                b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 100 100]>>endobj\n"
                b"xref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n"
                b"0000000053 00000 n \n0000000098 00000 n \n"
                b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n150\n%%EOF\n")

    def _upload_and_delete(self, sess, categoria, prefijo, fname):
        files = {"file": (fname, io.BytesIO(self._pdf()), "application/pdf")}
        data = {"categoria": categoria}
        r = requests.post(f"{BASE_URL}/api/clientes/folders/{FID}/upload-file",
                          files=files, data=data, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        saved = d.get("saved") or ""
        assert "99_otros" in saved, f"subfolder wrong: {saved}"
        assert prefijo in saved, f"prefijo {prefijo} missing in {saved}"
        # Delete
        rd = sess.post(f"{BASE_URL}/api/clientes/folders/{FID}/delete-file",
                       json={"file_path": saved}, timeout=15)
        assert rd.status_code == 200, rd.text

    def test_voucher_tasacion(self, sess):
        self._upload_and_delete(sess, "voucher_tasacion",
                                "VOUCHER_TASACION_", "test_agent_vt.pdf")

    def test_voucher_gasto_op(self, sess):
        self._upload_and_delete(sess, "voucher_gasto_operacional",
                                "VOUCHER_GASTO_OP_", "test_agent_vgo.pdf")
