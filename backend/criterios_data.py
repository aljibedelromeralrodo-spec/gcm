"""Default evaluation criteria & config ("Regla de Oro").
These are the credit-policy thresholds used by the evaluator.
"""
from datetime import datetime, timezone


def now_iso():
    return datetime.now(timezone.utc).isoformat()


DEFAULT_CRITERIOS = {
    "version": "1.0",
    "updated_at": now_iso(),
    "btg_pactual": {
        "con_subsidio": {
            "monto_credito_min_uf": 0,
            "nota_minimo": "SIN mínimo de crédito para viviendas con subsidio (Regla de Oro #71 / INV-3)",
            "monto_credito_max_uf": 8000,
            "ltv_max": 0.80,
            "div_renta_max": 0.35,
            "carga_financiera_max_sin_codeudor": 0.40,
            "carga_financiera_max_con_codeudor": 0.35,
            "edad_termino_max": 80,
            "antiguedad_laboral_min_meses": 12,
            "morosidad_permitida": "No",
        },
        "sin_subsidio": {
            "renta_min_uf": 30,
            "monto_credito_min_uf": 2000,
            "nota_minimo": "Mínimo UF 2.000 aplica ÚNICAMENTE a viviendas sin subsidio (Regla de Oro #71 / INV-3)",
            "monto_credito_max_uf": 25000,
            "valor_propiedad_min_uf": 1000,
            "valor_propiedad_max_uf": 40000,
            "plazo_min_anos": 5,
            "plazo_max_anos": 30,
            "edad_min": 24,
            "edad_max": 70,
            "edad_plazo_max": 80,
            "ltv_max": 0.90,
            "div_renta_max_sin_codeudor": 0.30,
            "div_renta_max_con_codeudor_conjunto": 0.35,
            "div_renta_max_titular_con_codeudor": 0.30,
            "carga_financiera_max": 0.40,
            "antiguedad_laboral_min_meses": 12,
        },
        "castigos_renta": {
            "renta_variable_castigo": 0.15,
            "honorarios_castigo": 0.20,
            "no_considera": [
                "Horas extras",
                "Asignaciones no imponibles",
                "Bonos esporadicos",
                "Movilizacion / colacion",
            ],
        },
    },
    "ameris": {
        "con_subsidio": {
            "monto_credito_min_uf": 500,
            "ltv_max_base": 0.90,
            "antiguedad_laboral_min_meses": 12,
            "politicas_edad_final": [
                {"edad_final_max": 70, "ltv_max": 0.90, "div_renta_max": 0.30, "carga_fin_max": 0.35},
                {"edad_final_max": 75, "ltv_max": 0.85, "div_renta_max": 0.28, "carga_fin_max": 0.33},
                {"edad_final_max": 80, "ltv_max": 0.80, "div_renta_max": 0.25, "carga_fin_max": 0.30},
            ],
            "div_renta_sin_codeudor": {"edad_max_40": 0.30, "edad_mayor_40": 0.28},
            "div_renta_con_codeudor_tipo_1_2": {"ltv_max_75": 0.35, "ltv_mayor_75": 0.30},
            "carga_sin_codeudor_max": 0.35,
            "carga_con_codeudor_tipo_1_2_max": 0.35,
            "carga_con_codeudor_tipo_3_max_conjunto": 0.30,
            "carga_con_codeudor_tipo_3_max_titular": 0.35,
        },
    },
    "concreces_mhe": {
        "fuente": "Resumen MHE Con/Sin Subsidio — planilla oficial cargada por el Administrador (27/08/2026)",
        "con_subsidio": {
            "tipo_vivienda": "Nuevas y usadas",
            "tipo_inmueble": "Casas y departamentos",
            "destino_vivienda": "Habitacional",
            "valor_propiedad_min_uf": 1000,
            "valor_propiedad_max_uf": 4000,
            "ltv_max": 0.80,
            "monto_credito_min_uf": 800,
            "monto_credito_max_uf": 3200,
            "pie_min": 0.20,
            "plazo_min_anos": 20,
            "plazo_max_anos": 40,
            "nota_plazo": "Plazos menores a 20 años se revisan en comité de excepción",
            "div_renta_max": 0.40,
            "carga_financiera_max": 0.55,
            "renta_min_uf_titular": 15,
            "renta_min_uf_conjunta": 25,
            "nacionalidad": "Chilena o extranjero con Permanencia Definitiva",
            "actividades": ["Dependiente", "Independiente",
                            "Jubilado / pensión renta vitalicia o fija definitiva"],
            "antiguedad_dependiente_indefinido_meses": 3,
            "antiguedad_dependiente_plazo_obra_meses": 6,
            "antiguedad_independiente_anos": 3,
            "continuidad_indefinido_meses": 6,
            "continuidad_obra_faena_meses": 12,
            "tipos_contrato": ["Indefinido", "Plazo fijo", "A contrata", "Por obra o faena"],
            "edad_min_ingreso": 21,
            "edad_max_ingreso": 65,
            "edad_max_termino": "79 años y 360 días",
            "haberes_no_imponibles_max_clp": 200000,
            "viaticos_asignaciones_max_pct": 0.50,
            "morosidad_permitida": "No",
            "excluyentes": ["Deuda directa morosa", "Deuda directa vencida", "Deuda directa castigada",
                            "Deuda indirecta (morosa, vencida o castigada)", "Mora comercial",
                            "Protestos vigentes", "Pagarés impagos", "Sujeto de alto riesgo (SAR)"],
            "codeudores_admitidos": ["Cónyuge o conviviente con hijo en común",
                                     "Codeudor directo: padres, hijos o hermanos",
                                     "Codeudor tercero: conviviente sin hijo en común, compañeros de trabajo o amigos"],
        },
        "sin_subsidio": {
            "tipo_vivienda": "Nuevas y usadas",
            "tipo_inmueble": "Casas y departamentos",
            "destino_vivienda": "Habitacional",
            "valor_propiedad_min_uf": 1250,
            "valor_propiedad_max_uf": 5000,
            "ltv_max": 0.80,
            "monto_credito_min_uf": 1000,
            "monto_credito_max_uf": 4000,
            "pie_min": 0.20,
            "plazo_min_anos": 20,
            "plazo_max_anos": 30,
            "div_renta_max": 0.35,
            "carga_financiera_max": 0.50,
            "renta_min_uf": 25,
            "nacionalidad": "Chilena o extranjero con Permanencia Definitiva",
            "antiguedad_dependiente_meses": 6,
            "antiguedad_independiente_anos": 3,
            "continuidad_indefinido_meses": 12,
            "continuidad_obra_faena_meses": 24,
            "edad_min_ingreso": 21,
            "edad_max_ingreso": 65,
            "edad_max_termino": "79 años y 360 días",
            "morosidad_permitida": "No",
            "complemento_renta": ("Padres y hermanos; cónyuge y pareja con hijos en común se evalúan con "
                                  "ratios familiares. Codeudor directo: el titular no debe exceder carga "
                                  "financiera de 70%. Codeudor tercero: el titular no debe exceder carga "
                                  "financiera de 60% y debe acreditar al menos el 50% del dividendo/renta"),
        },
    },
    "parametros_generales": {
        "con_subsidio": {
            "carga_fin_max": 0.40,
            "antiguedad_min_meses": 12,
            "edad_max_termino": 80,
            "ltv_max": 0.80,
            "morosidad": "No",
        },
        "sin_subsidio": {
            "carga_fin_max": 0.40,
            "antiguedad_min_meses": 12,
            "edad_max_termino": 80,
            "ltv_max": 0.90,
            "morosidad": "No",
        },
    },
}

DEFAULT_TASAS = {
    "tasa_subsidio_mayor_2000": 0.0635,
    "tasa_subsidio_menor_2000": 0.0650,
    "tasa_sin_subsidio": 0.0590,
}

DEFAULT_SEGUROS = {
    "seguro_desgravamen": 10245,
    "seguro_incendio": 23702,
}

DEFAULT_UF = 39842
