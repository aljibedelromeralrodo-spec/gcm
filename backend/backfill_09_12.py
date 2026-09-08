#!/usr/bin/env python3
"""Backfill temporal: inyecta 09_tasacion, 10_escritura, 11_resoluciones y 12_gop
en carpetas de clientes ya existentes (disco + Mongo si está disponible).

Uso, desde backend/:
    python backfill_09_12.py
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import folders_service as fsvc  # noqa: E402

SUBS_NUEVAS = ("09_tasacion", "10_escritura", "11_resoluciones", "12_gop")


def get_all_folders():
    """Nombres de carpetas históricas: directorios en disco ∪ Mongo."""
    nombres = set()
    base = fsvc.CLIENTES_DIR
    if base.exists():
        for p in base.iterdir():
            if p.is_dir() and not p.name.startswith("."):
                nombres.add(p.name)
    try:
        from bunker import _db
        for d in _db().folders.find({}, {"nombre": 1}):
            nom = (d.get("nombre") or "").strip()
            if nom:
                nombres.add(fsvc.safe_name(nom))
    except Exception as e:
        print(f"(Mongo omitido: {e})")
    return sorted(nombres)


def main():
    nombres = get_all_folders()
    print(f"Carpetas a revisar: {len(nombres)}")
    ok = 0
    for nom in nombres:
        base = fsvc.asegurar_estructura(nom)
        faltan = [s for s in SUBS_NUEVAS if not (base / s).is_dir()]
        if faltan:
            print(f"  FALLO {nom}: no quedaron {faltan}")
            continue
        print(f"  ok {nom}")
        ok += 1
    print(f"Listo: {ok}/{len(nombres)} con {', '.join(SUBS_NUEVAS)}")


if __name__ == "__main__":
    main()
