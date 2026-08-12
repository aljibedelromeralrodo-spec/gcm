"""CEREBRO EXPORTABLE — Contralor + DashAI como unidad independiente.

Agrupa la inteligencia (Bóveda de Criterios, Algoritmo Espejo MESA, pesos del
Contralor) detrás de la "Conexión Contralora": endpoints /api/brain/* protegidos
por BRAIN_ACCESS_KEY. REGLA DE HIERRO: cero datos privados de clientes en el export.
"""
import os
import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response
from database import db
import credit_engine as ce
import mesa_brain

brain = APIRouter(prefix="/brain")

EXPORT_DIR = Path(__file__).parent.parent / "exports"
EXPORT_FILE = EXPORT_DIR / "brain_config_export.json"

# ANONIMIZACIÓN: solo variables numéricas de entrenamiento; nombre/RUT/asunto EXCLUIDOS
_CAMPOS_LIMITE = ("renta_liquida_clp", "renta_codeudor_clp", "renta_disponible_clp",
                  "endeudamiento_mensual_clp", "tope_uf", "con_codeudor", "codeudor_tipo",
                  "con_subsidio", "edad_bucket", "edad_mayor_60", "mencion_tope", "fecha_mesa")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _verificar_llave(request: Request):
    llave = os.environ.get("BRAIN_ACCESS_KEY", "")
    if not llave:
        raise HTTPException(status_code=503,
                            detail="Conexión Contralora inactiva: defina BRAIN_ACCESS_KEY en backend/.env")
    entregada = request.headers.get("X-Brain-Key") or request.query_params.get("brain_key") or ""
    if entregada != llave:
        raise HTTPException(status_code=401, detail="Llave de Conexión Contralora inválida")


async def construir_export():
    criterios = await db.config.find_one({"_key": "criterios"}, {"_id": 0}) or {}
    espejo = await db.config.find_one({"_key": "espejo_mesa_modelo"}, {"_id": 0}) or {}
    limites = [{k: l.get(k) for k in _CAMPOS_LIMITE}
               for l in await db.limites_reales_mesa.find({}, {"_id": 0}).to_list(500)]
    version = await asyncio.to_thread(mesa_brain.criterios_version)
    return {
        "formato": "central-mutuos-brain",
        "version_export": 1,
        "generado_en": _now(),
        "job_id_origen": "8f15b608-2c47-4131-9ef1-abcea57ac830",
        "criterios_version": f"v1.{version}",
        "boveda_criterios": criterios,
        "espejo_mesa_modelo": espejo,
        "casos_entrenamiento_anonimizados": limites,
        "pesos_contralor": {
            "formula_endeudamiento_pct_mensual": ce.CF_PCT_MENSUAL,
            "proyeccion_amortizacion_meses": ce.CF_PROYECCION_MESES,
            "tope_carga_financiera_conjunta": ce.CF_TOPE_CARGA,
            "regla_riesgo_critico": "carga conjunta (titular + codeudor) > 40% => RIESGO CRÍTICO, mande lo que mande la MESA",
            "agregacion_deuda": "deuda_cmf_total (titular) + deuda_cmf_codeudor (cuota teórica 2% mensual)",
        },
        "modulos_motor": ["mesa_brain.py", "credit_engine.py", "criterios_data.py", "brain_export.py"],
        "privacidad": "SIN datos de clientes: carpetas, seguimiento, simulaciones, correos y archivos EXCLUIDOS",
    }


@brain.get("/status")
async def brain_status():
    espejo = await db.config.find_one({"_key": "espejo_mesa_modelo"}) or {}
    standalone = await db.config.find_one({"_key": "brain_standalone"}) or {}
    version = await asyncio.to_thread(mesa_brain.criterios_version)
    return {"conexion_contralora": "ACTIVA" if os.environ.get("BRAIN_ACCESS_KEY") else "INACTIVA — defina BRAIN_ACCESS_KEY",
            "criterios_version": f"v1.{version}",
            "espejo_listo": bool(espejo.get("listo")),
            "casos_espejo": espejo.get("n"),
            "modo_standalone": bool(standalone.get("activo")),
            "export_disponible": EXPORT_FILE.exists()}


@brain.get("/export")
async def brain_export(request: Request):
    _verificar_llave(request)
    data = await construir_export()
    EXPORT_DIR.mkdir(exist_ok=True)
    EXPORT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return data


@brain.get("/export/descargar")
async def brain_export_descargar(request: Request):
    _verificar_llave(request)
    data = await construir_export()
    EXPORT_DIR.mkdir(exist_ok=True)
    cuerpo = json.dumps(data, ensure_ascii=False, indent=2)
    EXPORT_FILE.write_text(cuerpo)
    return Response(content=cuerpo, media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="brain_config_export.json"'})


@brain.post("/import")
async def brain_import(request: Request):
    _verificar_llave(request)
    data = await request.json()
    if data.get("formato") != "central-mutuos-brain":
        raise HTTPException(status_code=400, detail="Archivo inválido: se espera formato central-mutuos-brain")
    crit = dict(data.get("boveda_criterios") or {})
    espj = dict(data.get("espejo_mesa_modelo") or {})
    crit["_key"] = "criterios"
    espj["_key"] = "espejo_mesa_modelo"
    await db.config.update_one({"_key": "criterios"}, {"$set": crit}, upsert=True)
    await db.config.update_one({"_key": "espejo_mesa_modelo"}, {"$set": espj}, upsert=True)
    casos = data.get("casos_entrenamiento_anonimizados") or []
    if casos:
        await db.limites_reales_mesa.delete_many({})
        await db.limites_reales_mesa.insert_many([dict(c) for c in casos])
    await db.config.update_one({"_key": "brain_standalone"}, {"$set": {
        "activo": True, "importado_en": _now(),
        "origen": data.get("job_id_origen"),
        "criterios_version": data.get("criterios_version")}}, upsert=True)
    return {"ok": True, "mensaje": "🧠 Cerebro DashAI + Contralor importado y ACTIVO",
            "criterios_version": data.get("criterios_version"), "casos": len(casos)}
