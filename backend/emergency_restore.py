#!/usr/bin/env python3
"""PROTOCOLO DE RECUPERACIÓN DE EMERGENCIA — Central Mutuos.

Script INACTIVO: solo se ejecuta a mano en caso de pérdida total del equipo.
Baja TODO el Búnker de Respaldo Cloud (Emergent Object Store) al disco local.

Uso:
    cd /app/backend && python3 emergency_restore.py            # simulación (dry-run)
    cd /app/backend && python3 emergency_restore.py --ejecutar # restauración real
"""
import sys
import json
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

import cloud_bunker as cb


def main():
    ejecutar = "--ejecutar" in sys.argv
    print("🛡️  PROTOCOLO DE RECUPERACIÓN — Búnker Cloud Central Mutuos")
    print(f"    Modo: {'RESTAURACIÓN REAL' if ejecutar else 'SIMULACIÓN (use --ejecutar para restaurar)'}\n")
    print("Descargando manifiesto desde la nube…")
    mani = json.loads(cb.get_object(cb.MANIFIESTO_PATH))
    archivos = mani.get("archivos") or []
    print(f"Manifiesto del {mani.get('generado_en', 's/f')} — {len(archivos)} archivos respaldados.\n")
    ok, err = 0, 0
    for a in archivos:
        rel = a["rel"]
        dest = cb.ROOT / rel
        if not ejecutar:
            print(f"  [dry-run] {rel} ({a.get('size', '?')} bytes)")
            continue
        try:
            data = cb.get_object(a["cloud_path"])
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            ok += 1
            print(f"  ✓ {rel}")
        except Exception as e:
            err += 1
            print(f"  ✗ {rel}: {e}")
    if ejecutar:
        try:
            snap = cb.get_object(f"{cb.APP_NAME}/dashai/registros_dashai.json")
            out = cb.ROOT / "boveda_dashai" / "registros_dashai_restaurado.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(snap)
            print(f"  ✓ Registro DashAI → {out}")
        except Exception as e:
            print(f"  ✗ Registro DashAI: {e}")
        print(f"\nRESULTADO: {ok} restaurados, {err} errores.")
        print("Recuerde reiniciar el backend para que el Búnker GridFS re-sincronice.")
    else:
        print(f"\nSimulación completa: {len(archivos)} archivos listos para restaurar con --ejecutar")


if __name__ == "__main__":
    main()
