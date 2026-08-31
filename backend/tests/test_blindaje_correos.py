"""V15.9 — protocolos, detección y plantilla (sin SMTP)."""
import os
import sys
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:27017")
os.environ.setdefault("DB_NAME", "test_database")
os.environ.setdefault("JWT_SECRET", "test-secret")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import blindaje_correos as bl


def test_protocolos_semilla_ids():
    ids = {p["id"] for p in bl.PROTOCOLOS}
    assert ids >= {
        "independiente", "mixto", "con_codeudor",
        "con_licencia_medica", "dependiente_simple",
    }
    dep = bl.protocolo_por_id("dependiente_simple")
    assert "cedula" in dep["documentos_requeridos"]
    assert "cotizaciones_12" in dep["documentos_requeridos"]
    assert dep["valida_con"] == "fonasa"


def test_detectar_licencia_gana():
    fd = {
        "credit_request": {
            "client_type": "dependiente",
            "licencia_medica": True,
            "codeudor": {"has_codeudor": True},
        }
    }
    assert bl.detectar_protocolo(fd) == "con_licencia_medica"


def test_detectar_codeudor():
    fd = {"codeudor_nombre": "Ana Pérez", "credit_request": {"client_type": "dependiente"}}
    assert bl.detectar_protocolo(fd) == "con_codeudor"


def test_detectar_mixto_e_independiente():
    assert bl.detectar_protocolo({"credit_request": {"client_type": "mixto"}}) == "mixto"
    assert bl.detectar_protocolo(
        {"credit_request": {"client_type": "independiente"}}) == "independiente"
    assert bl.detectar_protocolo({}) == "dependiente_simple"


def test_doc_recibido_por_categoria():
    cats = {"cedula", "liquidacion", "afp"}
    assert bl.doc_recibido("cedula", cats)
    assert bl.doc_recibido("liquidacion_3_meses", cats)
    assert bl.doc_recibido("cotizaciones_12", cats)
    assert not bl.doc_recibido("carpeta_tributaria", cats)
    assert not bl.doc_recibido("cedula_codeudor", cats)
    assert bl.doc_recibido("cedula_codeudor", cats | {"codeudor"})


def test_inventario_faltantes(monkeypatch):
    monkeypatch.setattr(bl, "cats_presentes", lambda fd: {"cedula", "liquidacion"})
    fd = {"nombre": "Juan", "credit_request": {"client_type": "dependiente"}}
    inv = bl.inventario_protocolo(fd)
    assert inv["protocolo_id"] == "dependiente_simple"
    assert "cedula" in inv["documentos_tiene"]
    assert "cotizaciones_12" in inv["documentos_faltan"]
    assert inv["completo"] is False


def test_plantilla_sin_llm():
    asunto, html, texto = bl.plantilla_faltantes(
        "César Zamora", "1-9", "Dependiente Simple",
        ["cedula", "cotizaciones_12"])
    assert "César Zamora" in asunto
    assert "Cédula" in html
    assert "AFP" in html
    assert "emergent" not in html.lower()
    assert "1-9" in texto
