"""🧪 PRUEBAS CRÍTICAS PRE-DESPLIEGUE — Central Mutuos.
Cubre: correos salientes, creación de carpetas, aprobaciones de Mesa, rechazos y
Gasto Operacional. NO envía correos reales (SMTP simulado) ni escribe datos de negocio.
Ejecutar: bash /app/scripts/pre_deploy_check.sh
"""
import io
import sys
import zipfile

import pytest

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

import email_service as mail  # noqa: E402


@pytest.fixture
def smtp_simulado():
    """Captura los envíos sin tocar la red; restaura al terminar."""
    capturados = []
    orig_envio, orig_pausa = mail._intentar_envio, mail.PAUSA_ENTRE_CORREOS
    orig_accounts = list(mail.ACCOUNTS)

    def fake(acc, msg):
        capturados.append({"cuenta": acc["user"], "from": msg["From"], "to": msg["To"]})
        return {"success": True, "desde": acc["user"], "smtp_code": 250, "smtp_response": "SIM"}

    mail._intentar_envio, mail.PAUSA_ENTRE_CORREOS = fake, 0
    yield capturados
    mail._intentar_envio, mail.PAUSA_ENTRE_CORREOS = orig_envio, orig_pausa
    mail.ACCOUNTS[:] = orig_accounts


# ── 1. CORREOS SALIENTES — Cuenta Única ─────────────────────────────────
def test_correo_cuenta_unica(smtp_simulado):
    r = mail.send_mail("cliente@externo.cl", "T", "<p>x</p>", [], "principal", permitir_duplicado=True)
    assert r["success"] and smtp_simulado[-1]["cuenta"] == "gerardo.ext@centralmutuos.cl"
    assert "Central Mutuos" in smtp_simulado[-1]["from"]


def test_correo_destino_propio_mantiene_corporativa(smtp_simulado):
    mail.send_mail("gerardo.ext@centralmutuos.cl", "T2", "<p>x</p>", [], "secundaria", permitir_duplicado=True)
    assert smtp_simulado[-1]["cuenta"] == "gerardo.ext@centralmutuos.cl"


def test_correo_sin_mail2_bloquea(smtp_simulado):
    mail.ACCOUNTS[:] = [a for a in mail.ACCOUNTS if a["rol"] != "secundaria"]
    r = mail.send_mail("cliente@externo.cl", "T3", "<p>x</p>", [], "secundaria", permitir_duplicado=True)
    assert not r["success"] and "CUENTA ÚNICA" in r["error"]


# ── 2. GASTO OPERACIONAL — cuenta fija ──────────────────────────────────
def test_gasto_operacional_cuenta_fija(smtp_simulado):
    r = mail.send_mail("cliente@externo.cl", "Gastos Operacionales — TEST", "<p>x</p>", [],
                       "secundaria", cuenta_fija=True, permitir_duplicado=True)
    assert r["success"] and smtp_simulado[-1]["cuenta"] == "gerardo.ext@centralmutuos.cl"


# ── 3. CREACIÓN DE CARPETAS — Regla 3 documentos (sin frases exactas) ───
def _item(docs, subject="fotos varias sin palabras clave"):
    return {"subject": subject, "body_full": "", "classification": {"documentos": docs}}


def test_carpeta_3_docs_sin_frase():
    import server
    ok, _ = server._regla_solicitud_ok(_item([
        {"tipo": "cedula", "filename": "cedula.pdf"},
        {"tipo": "liquidacion", "filename": "liq1.pdf"},
        {"tipo": "certificado_smf", "filename": "cmf.pdf"}]))
    assert ok, "3 docs obligatorios deben bastar sin frase exacta"


def test_carpeta_insuficiente_rechaza():
    import server
    ok, motivo = server._regla_solicitud_ok(_item(
        [{"tipo": "cedula", "filename": "cedula.pdf"}],
        subject="Solicitud de crédito formal"))
    assert not ok and "mínimo 3" in motivo


def test_zip_y_rar():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("cedula.pdf", b"%PDF-1.4")
        z.writestr("nota.txt", b"no")
    r = mail.expandir_zip("docs.zip", buf.getvalue())
    assert [x[0] for x in r] == ["cedula.pdf"]
    assert mail.expandir_zip("malo.rar", b"corrupto") == []


# ── 4. APROBACIONES DE MESA ─────────────────────────────────────────────
def test_clasificacion_mesa():
    import mesa_verdad as mv
    assert mv._clasificar("Estimados: aprobado, adjuntamos carta de aprobación") == "aprobacion"
    assert mv._clasificar("El crédito no cumple parámetros objetivos mínimos de aprobación") == "rechazo"
    assert mv._clasificar("se anula la aprobación enviada") == "anulacion"


def test_aprobacion_sin_gastos():
    import server
    assert server._tipo_pdf_aprobacion("gastos_operacionales_cliente.pdf") == "otro"
    assert server._tipo_pdf_aprobacion("simulacion_gastos_operacional.pdf") == "otro"
    assert server._tipo_pdf_aprobacion("Carta_Aprobacion_Juan.pdf") == "carta_aprobacion"


# ── 5. RECHAZOS — texto exacto y enmascaramiento ────────────────────────
def test_rechazo_texto_exacto():
    import rechazo_notificacion as rn
    texto = "Estimada: no cumple parámetro objetivo de aprobación. Saludos."
    motivo, reco = rn.motivo_y_recomendacion(texto)
    assert motivo == texto and "codeudor" in reco.lower()
    assert rn.RX_ORIGEN_PROHIBIDO.search("reenviado de la mesa")
    assert rn.RX_ORIGEN_PROHIBIDO.search("contacto@banco.cl")
    assert not rn.RX_ORIGEN_PROHIBIDO.search(texto)
    html = rn.PLANTILLAS["c"]("Anita Álvarez", motivo, reco)
    assert "Anita Álvarez" in html and "mesa" not in html.lower()


# ── 6. API SMOKE (backend vivo) ─────────────────────────────────────────
def test_api_smoke():
    import requests
    try:
        r = requests.post("http://localhost:8001/api/auth/login",
                          json={"rut": "administrador", "password": "141617575"}, timeout=15)
    except requests.ConnectionError:
        pytest.skip("backend no está corriendo en 8001")
    assert r.status_code == 200
    tok = {"Authorization": f"Bearer {r.json()['token']}"}
    for ep in ("/api/central/dashboard-batch", "/api/carpetas/faltantes",
               "/api/almacenamiento/estado", "/api/modo-prueba/retenidos"):
        assert requests.get(f"http://localhost:8001{ep}", headers=tok, timeout=30).status_code == 200
