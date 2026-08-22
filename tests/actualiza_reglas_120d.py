from dotenv import load_dotenv
load_dotenv('/app/backend/.env')
import os
import uuid
from datetime import datetime, timezone
from pymongo import MongoClient

db = MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
now = datetime.now(timezone.utc).isoformat()

db.proc_rules.update_one(
    {'name': 'Respuesta MESA — rechazo'},
    {'$set': {
        'pattern': r"no\s+cumple\s+parametros|pasad[oa]\s+en\s+carga\s+financiera|limitar\s+la\s+deuda|incorporar\s+(un\s+)?codeudor|ingresos?\s+.{0,30}no\s+son\s+suficientes|no\s+hay\s+posibilidad\s+de\s+aprobar|estaria\s+por\s+debajo\s+de\s+las?\s+uf|necesitamos\s+al\s+menos\s+\d+\s+meses|no\s+se\s+puede\s+aprobar\s+con\s+.{0,30}como\s+titular|favor\s+cancelar\s+email\s+de\s+aprobacion",
        'classify_as.motivos_conocidos': [
            'carga financiera', 'ingresos insuficientes', 'sociedad SPA',
            'antigüedad laboral <6 meses plazo fijo', 'tope UF por capacidad/edad',
            'titular no califica (sugerir cambio de titular)', 'anulación de aprobación previa',
        ],
        'actualizado': now, 'aprendido_de': 'analisis_gmail_120d',
    }},
)

db.proc_rules.update_one(
    {'name': 'Respuesta MESA — corrección/observación'},
    {'$set': {
        'pattern': r"favor\s+revisar|no\s+se\s+que\s+paso|revisar\s+monto|ficha\s+esta\s+por|favor\s+(pedir|solicitar|confirmar|enviar)\s|con\s+eso\s+podemos\s+evaluar",
        'classify_as.pedidos_conocidos': [
            'detalle deuda indirecta', 'confirmar con/sin subsidio',
            'informe resumen boletas de honorarios (SII) para evaluar independientes',
            'contratos de arriendo para bajar ratio del codeudor',
        ],
        'actualizado': now, 'aprendido_de': 'analisis_gmail_120d',
    }},
)

nuevas = [
    {
        'id': str(uuid.uuid4()),
        'name': 'Respuesta MESA — aprobación con tope',
        'pattern': r"por\s+maximo\s+posible(\s+de\s+uf\s*[\d\.]+)?|simulacion\s+por\s+maximo\s+posible|por\s+ambas\s+opciones\s+solicitadas",
        'kind': 'regex', 'priority': 4, 'active': True,
        'classify_as': {
            'categoria': 'respuesta_mesa_aprobacion_con_tope',
            'nota': 'Aprueba pero limita el monto ("máximo posible UF X"). Frecuente en independientes, renta mixta y clientes 55+ (plazo acortado por edad). Extraer tope_uf si aparece.',
            'extraer': ['tope_uf'],
        },
        'aprendido_de': 'analisis_gmail_120d', 'creado': now,
    },
    {
        'id': str(uuid.uuid4()),
        'name': 'Ficha con edad — alerta plazo 55+',
        'pattern': r"edad\s*:?\s*([5-9]\d)\s*(años|anos)?",
        'kind': 'regex', 'priority': 12, 'active': True,
        'classify_as': {
            'categoria': 'alerta_edad_plazo',
            'nota': 'Si edad>=55, el plazo máximo se acorta y baja el crédito posible (caso Eduar Araya, 55a: tope < UF 2000 y sugerencia de codeudor). Mesa NUNCA escribe "por edad": el efecto solo se ve en el tope UF o en el Simulador PDF. Marcar folder con edad_titular y alertar al ejecutivo que el monto puede bajar.',
            'extraer': ['edad'],
            'umbral_alerta': 55,
        },
        'aprendido_de': 'analisis_gmail_120d', 'creado': now,
    },
    {
        'id': str(uuid.uuid4()),
        'name': 'Renta mixta — dependiente + honorarios',
        'pattern': r"(liquidacion(es)?\s+de\s+sueldo|liquidaciones).{0,400}(boletas?\s+de\s+honorarios|certificados?\s+sii|carpeta\s+tributaria)|(boletas?\s+de\s+honorarios|certificados?\s+sii).{0,400}liquidacion",
        'kind': 'regex', 'priority': 14, 'active': True,
        'classify_as': {
            'categoria': 'renta_mixta',
            'nota': 'Titular o pareja con renta dependiente + independiente (Catalina Aguilera+Nelson Barraza, Javiera Espinoza). Mesa exige "informe resumen de boletas de honorarios" (resumen anual SII) para evaluar la parte independiente. Set: liquidaciones en 02, boletas/F22 en 03. Suele aprobarse CON TOPE.',
            'documento_requerido': 'informe_resumen_boletas_sii',
        },
        'aprendido_de': 'analisis_gmail_120d', 'creado': now,
    },
]
for r in nuevas:
    db.proc_rules.update_one({'name': r['name']}, {'$set': r}, upsert=True)

print('proc_rules actualizadas:', db.proc_rules.count_documents({}))
for r in db.proc_rules.find({'aprendido_de': 'analisis_gmail_120d'}, {'_id': 0, 'name': 1}):
    print(' -', r['name'])
