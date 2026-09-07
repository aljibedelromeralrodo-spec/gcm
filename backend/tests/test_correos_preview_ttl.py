"""Buzón preview: clasifica preaprobación vs otros y calcula caducidad (7d / 60d)."""
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

BACKEND_DIR = str(Path(__file__).resolve().parents[1])
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import email_service as mail  # noqa: E402


def test_preaprobacion_por_asunto_ds19():
    assert mail.clasificar_preview("Re: Ricardo Cárcamo (DS19 - INMEDIATA - NICOLAS)") == "preaprobacion"


def test_preaprobacion_por_carta():
    assert mail.clasificar_preview(
        "Aprobación cliente", "",
        [{"filename": "Carta_Aprobacion_RICARDO.pdf"}]) == "preaprobacion"


def test_preaprobacion_por_simulador():
    assert mail.clasificar_preview(
        "Resultado", "",
        [{"filename": "Simulador_RICARDO_ESTEBAN_CM.pdf"}]) == "preaprobacion"


def test_otro_resumen_diario():
    assert mail.clasificar_preview("Resumen Diario Central Mutuos — 09/07/2026 8:00 a.m.") == "otro"


def test_otro_resumen_martin():
    assert mail.clasificar_preview("Resumen Semanal de Martín — 09/07/2026") == "otro"


def test_caduca_otro_7_dias():
    creado = datetime(2026, 9, 1, tzinfo=timezone.utc).isoformat()
    cad = mail._parse_iso_preview(mail.caduca_preview(creado, "otro"))
    assert cad - datetime(2026, 9, 1, tzinfo=timezone.utc) == timedelta(days=7)


def test_caduca_preaprobacion_60_dias():
    creado = datetime(2026, 9, 1, tzinfo=timezone.utc).isoformat()
    cad = mail._parse_iso_preview(mail.caduca_preview(creado, "preaprobacion"))
    assert cad - datetime(2026, 9, 1, tzinfo=timezone.utc) == timedelta(days=60)
