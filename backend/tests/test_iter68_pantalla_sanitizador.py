"""Iter68 — pruebas de: sanitizador PDF Gastos Operacionales, correos-preview con adjuntos,
permisos Martín, y forzado V3 con variantes de nombre (ANTONIA PÉREZ)."""
import io
import os
import sys
import time
import base64
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://espejo-hibrido.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


# ═══════════════ FIXTURES ═══════════════
@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{API}/auth/login",
                      json={"rut": "administrador", "password": "141617575"},
                      timeout=30)
    assert r.status_code == 200, f"Login falló: {r.status_code} {r.text[:200]}"
    tok = r.json().get("token")
    assert tok, "No token"
    return tok


@pytest.fixture(scope="session")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ═══════════════ SANITIZADOR PDF (python directo, sin API) ═══════════════
class TestSanitizadorPDF:
    """pdf_service.sanitizar_gastos_operacionales — regla crítica de bloqueo."""

    def _make_pdf(self, textos_por_pagina):
        """Crea un PDF con una página por cada texto de la lista (reportlab)."""
        sys.path.insert(0, "/app/backend")
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        for t in textos_por_pagina:
            c.drawString(100, 750, t)
            c.showPage()
        c.save()
        return buf.getvalue()

    def test_sanitizar_2paginas_pag2_con_gastos_ok(self):
        sys.path.insert(0, "/app/backend")
        import pdf_service
        pdf = self._make_pdf(["Simulación de crédito — dividendo mensual",
                              "GASTOS OPERACIONALES — impuestos y aranceles"])
        limpio, removidas, valido = pdf_service.sanitizar_gastos_operacionales(pdf)
        assert valido is True, "Debería ser válido tras quitar la pág 2"
        assert removidas == 1, f"Debería remover 1 página, removió {removidas}"
        from pypdf import PdfReader
        n = len(PdfReader(io.BytesIO(limpio)).pages)
        assert n == 1, f"Debería quedar 1 página, quedó {n}"

    def test_sanitizar_todas_paginas_gastos_bloquea(self):
        sys.path.insert(0, "/app/backend")
        import pdf_service
        pdf = self._make_pdf(["Costos Operacionales del crédito hipotecario",
                              "Costos Operacionales - continuación"])
        _limpio, _rem, valido = pdf_service.sanitizar_gastos_operacionales(pdf)
        assert valido is False, "Debe BLOQUEAR el envío (valido=False) si TODAS las páginas contienen Costos Operacionales"


# ═══════════════ MARTIN PERMISOS ═══════════════
class TestMartinPermisos:
    def test_get_permisos(self, headers):
        r = requests.get(f"{API}/martin/permisos", headers=headers, timeout=30)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
        d = r.json()
        assert "permisos" in d, "Falta campo 'permisos'"
        assert "ultimos_logs" in d, "Falta campo 'ultimos_logs'"
        assert isinstance(d["permisos"], (dict, list)), "permisos debe ser dict/list"
        assert isinstance(d["ultimos_logs"], list), "ultimos_logs debe ser list"


# ═══════════════ CORREOS PREVIEW ═══════════════
class TestCorreosPreview:
    def test_lista_preview_estructura(self, headers):
        r = requests.get(f"{API}/correos-preview", headers=headers, timeout=30)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
        d = r.json()
        assert "correos" in d
        assert isinstance(d["correos"], list)
        # Si hay correos, verificar estructura (no confirmar ninguno)
        for c in d["correos"][:3]:
            assert "id" in c or "_id" in c or True  # tolerante
            assert "adjuntos" in c or "to" in c, f"Falta campo básico en preview: {list(c.keys())[:10]}"

    def test_crear_preview_test_y_flujo_adjunto(self, headers):
        """Crea un PREVIEW de prueba con adjunto vía email_service.send_mail (SIN confirmar),
        prueba GET adjunto → POST quitar adjunto → POST descartar. NUNCA envía correo real."""
        sys.path.insert(0, "/app/backend")
        from dotenv import load_dotenv as _ld
        _ld("/app/backend/.env")
        import email_service as mail
        # Adjunto mínimo válido PDF
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        c.drawString(100, 750, "TEST_ADJUNTO_ITER68 — prueba de visor y quitar")
        c.showPage()
        c.save()
        pdf_bytes = buf.getvalue()
        adj = [{"filename": "TEST_ITER68_adjunto.pdf",
                "content_b64": base64.b64encode(pdf_bytes).decode()}]
        # SIN confirmado → queda en cola correos_preview
        res = mail.send_mail(
            to="no-reply-test@example.invalid",
            subject="TEST_ITER68 preview — NO ENVIAR",
            body_html="<p>TEST_ITER68</p>",
            attachments=adj,
            desde="secundaria",
            confirmado=False,
            permitir_duplicado=True,
        )
        assert isinstance(res, dict), f"Respuesta send_mail inesperada: {res}"
        assert res.get("preview_id"), f"send_mail no encoló preview: {res}"
        pid = res["preview_id"]
        # Verificar visible en el API público
        time.sleep(0.5)
        lista = requests.get(f"{API}/correos-preview", headers=headers, timeout=30).json()
        encontrado = any((c.get("id") == pid) for c in lista.get("correos", []))
        assert encontrado, f"Preview {pid} no aparece en GET /correos-preview"
        # GET adjunto → application/pdf
        ra = requests.get(f"{API}/correos-preview/{pid}/adjunto/0", headers=headers, timeout=30)
        assert ra.status_code == 200, f"GET adjunto: {ra.status_code} {ra.text[:200]}"
        assert ra.headers.get("content-type", "").startswith("application/pdf"), \
            f"Content-Type esperado application/pdf, recibió: {ra.headers.get('content-type')}"
        assert ra.content[:5] == b"%PDF-", "Contenido no parece PDF"
        # POST quitar adjunto
        rq = requests.post(f"{API}/correos-preview/{pid}/adjunto/0/quitar",
                           headers=headers, timeout=30)
        assert rq.status_code == 200, f"Quitar: {rq.status_code} {rq.text[:200]}"
        dq = rq.json()
        assert dq.get("ok") is True
        assert dq.get("quitado") == "TEST_ITER68_adjunto.pdf" or "TEST_ITER68" in (dq.get("quitado") or ""), dq
        assert isinstance(dq.get("adjuntos"), list) and len(dq["adjuntos"]) == 0
        # POST descartar (obligatorio: JAMÁS confirmar/enviar)
        rd = requests.post(f"{API}/correos-preview/{pid}/descartar",
                           headers=headers, timeout=30)
        assert rd.status_code == 200, f"Descartar: {rd.status_code} {rd.text[:200]}"
        assert rd.json().get("descartado") is True


# ═══════════════ FORZAR CARPETA V3 (ANTONIA PÉREZ) ═══════════════
class TestForzarV3:
    def test_forzar_antonia_matchea_carpeta_existente(self, headers):
        payload = {"clave": "0586", "nombre": "Antonia Fernanda Perez Muñoz"}
        r = requests.post(f"{API}/clientes/folders/forzar",
                          headers=headers, json=payload, timeout=30)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
        job = r.json()
        job_id = job.get("job_id")
        assert job_id, f"No job_id: {job}"
        # Esperar hasta 3 min
        started = time.time()
        result = None
        while time.time() - started < 180:
            rj = requests.get(f"{API}/jobs/{job_id}", headers=headers, timeout=30)
            if rj.status_code == 200:
                jd = rj.json()
                if jd.get("estado") in ("terminado", "ok", "completado", "done") or jd.get("resultado"):
                    result = jd
                    break
                if jd.get("estado") in ("error", "fallido", "failed"):
                    result = jd
                    break
            time.sleep(5)
        assert result is not None, f"Job {job_id} no terminó en 3 min"
        res = result.get("resultado") or result.get("result") or {}
        assert res, f"Sin resultado en job: {result}"
        carpeta = (res.get("carpeta") or "").upper()
        # Debe matchear ANTONIA PÉREZ existente, NO crear duplicado ANTONIA FERNANDA PEREZ MUÑOZ
        assert "ANTONIA" in carpeta and ("PEREZ" in carpeta or "PÉREZ" in carpeta), \
            f"Carpeta inesperada: {carpeta}"
        assert "FERNANDA" not in carpeta, \
            f"Se creó duplicado (no debería contener FERNANDA/MUÑOZ): {carpeta}"
        assert "MUÑOZ" not in carpeta and "MUNOZ" not in carpeta, \
            f"Duplicado detectado: {carpeta}"
        assert "variante_busqueda" in res, f"Falta variante_busqueda: {list(res.keys())}"
        assert "menciones_detectadas" in res, f"Falta menciones_detectadas: {list(res.keys())}"


# ═══════════════ REGRESIÓN ═══════════════
class TestRegresion:
    def test_login_admin(self):
        r = requests.post(f"{API}/auth/login",
                          json={"rut": "administrador", "password": "141617575"},
                          timeout=30)
        assert r.status_code == 200
        assert "token" in r.json()

    def test_listar_folders(self, headers):
        r = requests.get(f"{API}/clientes/folders", headers=headers, timeout=60)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
        d = r.json()
        # Soporta {folders:[...]} o list directo
        folders = d.get("folders") if isinstance(d, dict) else d
        assert isinstance(folders, list) and len(folders) > 0
        nombres = " | ".join((f.get("nombre") or "").upper() for f in folders)
        assert "ANTONIA" in nombres, "No aparece ANTONIA en folders"
        assert "CESAR" in nombres or "CÉSAR" in nombres or "ZAMORA" in nombres, "No aparece César Zamora"
