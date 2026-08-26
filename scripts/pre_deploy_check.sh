#!/bin/bash
# 🧪 CHEQUEO PRE-DESPLIEGUE — Central Mutuos
# Ejecuta las pruebas críticas. Si alguna falla: NO DESPLEGAR.
cd /app/backend || exit 1
echo "══════════════════════════════════════════════════════════"
echo "🧪 PRUEBAS CRÍTICAS PRE-DESPLIEGUE — CENTRAL MUTUOS"
echo "   (correos salientes · carpetas · Mesa · rechazos · gastos)"
echo "══════════════════════════════════════════════════════════"
python3 -m pytest tests/test_criticos.py -v --tb=short
CODE=$?
echo ""
if [ $CODE -eq 0 ]; then
  echo "✅✅✅ TODAS LAS PRUEBAS PASARON — APTO PARA DESPLEGAR ✅✅✅"
else
  echo "🚨🚨🚨 ALERTA: HAY PRUEBAS FALLANDO — ¡NO SUBIR A PRODUCCIÓN! 🚨🚨🚨"
  echo "   Revise el detalle arriba y corrija antes de redesplegar."
fi
exit $CODE
