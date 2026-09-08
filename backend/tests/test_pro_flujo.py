"""Pro Flujo — una carpeta, una etapa."""
import os
import sys
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:27017")
os.environ.setdefault("DB_NAME", "test_database")
os.environ.setdefault("JWT_SECRET", "test-secret")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pro_flujo import etapa_operacion, accion_de, faltan_para_tablero


def test_tablero_usa_protocolo_sin_disco():
    assert faltan_para_tablero({"protocolo_completo": True, "protocolo_faltan": ["CI"]}) == []
    assert faltan_para_tablero({"protocolo_faltan": ["CI", "Renta"]}) == ["CI", "Renta"]
    assert faltan_para_tablero({}) == ["Documentación por revisar"]


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
    assert accion_de("clasificar", {}) == "abrir_carpeta"
    src = Path(__file__).resolve().parents[1] / "pro_flujo.py"
    assert 'accion in ("armar_borrador", "sincronizar")' in src.read_text()
    assert accion_de("autorizar", {}) == "autorizar_faltantes"
    assert accion_de("gop", {}, gop_enviado=False) == "enviar_gop"
    assert accion_de("gop", {"mesa_enviado_at": "x"}, gop_enviado=True) == "registrar_gop"
    assert accion_de("listo_mesa", {}) == "enviar_mesa"
    assert accion_de("escrituracion", {}) == "enviar_tasacion"
    assert accion_de("escrituracion", {"tasacion_solicitada_at": "x"}) == "enviar_estudio"
    assert accion_de("escrituracion", {
        "tasacion_solicitada_at": "x",
        "estudio_titulo_solicitado_at": "y",
    }) == "mover_escrituracion"
    assert accion_de("escrituracion", {
        "tasacion_solicitada_at": "x",
        "estudio_titulo_solicitado_at": "y",
        "escritura_solicitada_at": "z",
    }) == "abrir_escritura"


def test_inventario_ignora_99_y_codeudor():
    import tempfile
    from pathlib import Path
    import folders_service as fsvc
    import pro_flujo as pf
    prev = fsvc.CLIENTES_DIR
    td = Path(tempfile.mkdtemp())
    try:
        fsvc.CLIENTES_DIR = td
        nombre = "JUAN PRUEBA"
        dest = td / fsvc.safe_name(nombre)
        (dest / "01_cedula").mkdir(parents=True)
        (dest / "01_cedula" / "01_Cedula_x.pdf").write_bytes(b"%PDF-1.4 extra")
        (dest / "99_otros").mkdir()
        (dest / "99_otros" / "scan.pdf").write_bytes(b"%PDF-1.4 extra")
        (dest / "05_codeudor").mkdir()
        (dest / "05_codeudor" / "CODEUDOR_cmf.pdf").write_bytes(b"%PDF-1.4 extra")
        fd = {"nombre": nombre, "credit_request": {"client_type": "dependiente"}}
        faltan = pf.inventario_faltantes(fd)
        joined = " ".join(faltan).lower()
        assert "cmf" in joined or "informe" in joined
        assert "liquidaci" in joined
    finally:
        fsvc.CLIENTES_DIR = prev


def test_firma_cierra():
    fd = {"escritura_confirmada_at": "2026-08-31"}
    e, _ = etapa_operacion(fd, faltan=False, auth_pend=False,
                           gop_enviado=True, gop_pagado=True, carta=True)
    assert e == "cerrado"
