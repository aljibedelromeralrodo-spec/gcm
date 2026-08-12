# 🧠 EXPORTACIÓN DEL CEREBRO — Contralor + DashAI (Central Mutuos)

Guía técnica para integrar el **Módulo Contralor** y el **Cerebro DashAI** en otro
programa Emergent, SIN los datos privados de clientes del dueño original.

---

## 1. ¿Qué recibe usted?

| Pieza | Archivo / Ubicación | Contenido |
|---|---|---|
| Bóveda de Criterios | `exports/brain_config_export.json` → `boveda_criterios` | Reglas BTG/Ameris, políticas maestras, castigos de renta, fórmula de endeudamiento |
| Algoritmo Espejo MESA | `exports/brain_config_export.json` → `espejo_mesa_modelo` | Coeficientes de regresión entrenados (renta ↔ tope UF), multiplicadores por codeudor/edad/subsidio |
| Pesos del Contralor | `exports/brain_config_export.json` → `pesos_contralor` | Regla 2% mensual, proyección 48 meses, tope 40% de carga conjunta, regla RIESGO CRÍTICO |
| Casos de entrenamiento | `casos_entrenamiento_anonimizados` | Solo variables numéricas — **sin nombres, RUTs ni asuntos** |
| Motor de código | `backend/mesa_brain.py`, `backend/credit_engine.py`, `backend/criterios_data.py`, `backend/brain_export.py` | Auditoría 360° (`auditar_caso`), simulador, techo hipotecario, endpoints puente |

**Lo que NO recibe (Regla de Hierro):** carpetas de clientes, seguimiento de correos,
simulaciones nominadas, archivos PDF, credenciales de correo/eCert del dueño original.

## 2. ID de Bifurcación (Fork)

1. En Emergent, haga **Fork** del Job ID: `8f15b608-2c47-4131-9ef1-abcea57ac830`.
2. En su copia, edite `backend/.env` y defina SUS propios secretos:
   - `BRAIN_ACCESS_KEY="SU-LLAVE-PROPIA"`  ← **Llave de la Conexión Contralora (obligatoria)**
   - `ADMIN_PASSWORD_1` / `ADMIN_PASSWORD_2` (sus claves de login)
   - `JWT_SECRET` (uno nuevo, aleatorio)
   - Deje vacíos `MAIL_*`, `MIGRUP_*` si no usará correo/firma.
3. Active el **modo standalone** (borra los datos privados heredados y deja solo la inteligencia):

```bash
cd /app/backend
python brain_standalone_setup.py --activar
sudo supervisorctl restart backend
```

## 3. Conexión Contralora (API puente)

Todos los endpoints viven bajo `/api/brain/*` y exigen la cabecera
`X-Brain-Key: <BRAIN_ACCESS_KEY>` (o `?brain_key=`), excepto `/status`.

| Método | Ruta | Función |
|---|---|---|
| GET | `/api/brain/status` | Estado: llave activa, versión de criterios, espejo listo, modo standalone |
| GET | `/api/brain/export` | Genera y devuelve `brain_config_export.json` (también lo escribe en `exports/`) |
| GET | `/api/brain/export/descargar` | Descarga directa del JSON |
| POST | `/api/brain/import` | Carga un `brain_config_export.json` en la instancia (activa el Cerebro) |

Ejemplo de importación en su propio programa:

```bash
curl -X POST "https://SU-APP.emergent.host/api/brain/import" \
  -H "X-Brain-Key: SU-LLAVE-PROPIA" \
  -H "Content-Type: application/json" \
  --data @exports/brain_config_export.json
```

## 4. Uso del motor desde su código (Python)

```python
import mesa_brain, credit_engine as ce

# Auditoría 360° de una decisión (folder/sim son dicts con datos financieros)
cert = mesa_brain.auditar_caso(folder, sim, "aprobacion")

# Carga financiera conjunta (titular + codeudor) — regla 2% mensual
endeud = ce.endeudamiento_mensual(
    {"deuda_cmf_total": 8_000_000, "deuda_cmf_codeudor": 5_000_000}, uf_valor=40847.42)

# Techo hipotecario y simulador
sim = ce.simular_credito({"renta_titular": 1_500_000, "valor_uf": 40847.42})
```

- La Bóveda de Criterios se lee SIEMPRE de `db.config {_key: "criterios"}` (cero hardcode).
- Modificaciones de la Bóveda quedan reservadas al rol `maestro` (Mando Supremo).
- El Espejo MESA se re-entrena con `POST /api/dashai/espejo-mesa/minar` cuando usted
  acumule sus propias aprobaciones.

## 5. Correr DashAI localmente (su propio computador)

```bash
git clone <su fork>   # o "Descargar código" en Emergent
cd app/backend
pip install -r requirements.txt
# .env mínimo: MONGO_URL, DB_NAME, BRAIN_ACCESS_KEY, JWT_SECRET, ADMIN_PASSWORD_1
python brain_standalone_setup.py --activar
uvicorn server:app --port 8001
curl http://localhost:8001/api/brain/status
```

Opcional: `EMERGENT_LLM_KEY` propia si usará extracción OCR+IA (`ai_extract.py`).

## 6. Soporte

- Versión de criterios exportada: ver `criterios_version` dentro del JSON.
- El export es re-generable en cualquier momento: el JSON refleja la Bóveda vigente.
