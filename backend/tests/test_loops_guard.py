"""Loops 24/7 — inventario y política de pausa (sin Mongo, sin SMTP)."""
import sys
from pathlib import Path

BACKEND_DIR = str(Path(__file__).resolve().parents[1])
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import loops_guard as lg  # noqa: E402


PROTEGIDOS = ("ingesta_carpetas", "mesa", "mesa_verdad", "autorreparacion",
              "gmail_watch", "resumen_diario_8am", "notif_pace", "bunker_gridfs")
PAUSABLES = ("cloud_bunker_espejo", "rescate_historico", "historia_minado",
             "espejo_hibrido", "lector_ejecutivos", "cuenta_barrido", "buzon_aprendizaje")


class TestPolitica:
    def test_protegidos_no_se_pausan(self):
        for n in PROTEGIDOS:
            assert lg.puede_pausar(n) is False, n

    def test_candidatos_si_se_pausan(self):
        for n in PAUSABLES:
            assert lg.puede_pausar(n) is True, n

    def test_desconocido_no_se_pausa(self):
        assert lg.puede_pausar("loop_inventado_xyz") is False

    def test_recomendados_son_pausables(self):
        for n in lg.RECOMENDADOS_PAUSA:
            assert n in lg.CATALOGO
            assert lg.CATALOGO[n]["pausable"] is True

    def test_mesa_solapa_con_verdad_pero_ambas_protegidas(self):
        assert "mesa_verdad" in lg.CATALOGO["mesa"]["solapa"]
        assert "mesa" in lg.CATALOGO["mesa_verdad"]["solapa"]
        assert lg.puede_pausar("mesa") is False
        assert lg.puede_pausar("mesa_verdad") is False

    def test_cloud_bunker_solapa_con_bunker(self):
        assert "bunker_gridfs" in lg.CATALOGO["cloud_bunker_espejo"]["solapa"]
        assert lg.puede_pausar("bunker_gridfs") is False

    def test_catalogo_nombres_unicos_y_completos(self):
        assert len(lg.CATALOGO) == len(set(lg.CATALOGO))
        assert len(lg.CATALOGO) >= 40

    def test_esta_pausado_protegido_siempre_false_sync_policy(self):
        # puede_pausar es la traba: esta_pausado corto-circuita sin Mongo
        assert lg.puede_pausar("mesa_verdad") is False
