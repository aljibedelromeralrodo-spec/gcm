"""Pro Flujo — una carpeta, una etapa."""
import os
import sys
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:27017")
os.environ.setdefault("DB_NAME", "test_database")
os.environ.setdefault("JWT_SECRET", "test-secret")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pro_flujo import etapa_operacion, accion_de


def test_faltantes_antes_que_mesa():
    e, acc = etapa_operacion({}, faltan=True, auth_pend=False,
                             gop_enviado=False, gop_pagado=False, carta=False)
    assert e == "clasificar"
    assert "clasificar" in acc.lower() or "documentos" in acc.lower()


def test_autorizar_mail():
    e, _ = etapa_operacion({}, faltan=True, auth_pend=True,
                           gop_enviado=False, gop_pagado=False, carta=False)
    assert e == "autorizar"


def test_completa_pide_gop_luego_mesa():
    e, acc = etapa_operacion({}, faltan=False, auth_pend=False,
                             gop_enviado=False, gop_pagado=False, carta=False)
    assert e == "gop"
    e2, _ = etapa_operacion({}, faltan=False, auth_pend=False,
                            gop_enviado=True, gop_pagado=False, carta=False)
    assert e2 == "listo_mesa"


def test_mesa_enviada_cobra_gop():
    fd = {"mesa_enviado_at": "2026-08-31"}
    e, _ = etapa_operacion(fd, faltan=False, auth_pend=False,
                           gop_enviado=True, gop_pagado=False, carta=False)
    assert e == "gop"


def test_aprobada_va_a_escrituracion():
    fd = {"mesa_respuesta": "aprobada"}
    e, acc = etapa_operacion(fd, faltan=False, auth_pend=False,
                             gop_enviado=True, gop_pagado=True, carta=True)
    assert e == "escrituracion"
    assert "tasación" in acc.lower()


def test_acciones_siguientes():
    assert accion_de("clasificar", {}) == "sincronizar"
    assert accion_de("autorizar", {}) == "autorizar_faltantes"
    assert accion_de("gop", {}, gop_enviado=False) == "enviar_gop"
    assert accion_de("gop", {"mesa_enviado_at": "x"}, gop_enviado=True) == "registrar_gop"
    assert accion_de("listo_mesa", {}) == "enviar_mesa"
    assert accion_de("escrituracion", {}) == "enviar_tasacion"
    assert accion_de("escrituracion", {"tasacion_solicitada_at": "x"}) == "enviar_estudio"


def test_firma_cierra():
    fd = {"escritura_confirmada_at": "2026-08-31"}
    e, _ = etapa_operacion(fd, faltan=False, auth_pend=False,
                           gop_enviado=True, gop_pagado=True, carta=True)
    assert e == "cerrado"
