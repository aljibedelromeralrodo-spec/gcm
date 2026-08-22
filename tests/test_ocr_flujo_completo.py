"""TEST INTERNO COMPLETO — Flujo OCR + clasificación (orden del administrador).
Simula documentos reales (cédula, liquidación, AFP, CMF) en BAJA resolución tipo
WhatsApp (+ casos rotados), y los pasa por el flujo completo:
preprocesamiento → conversión a PDF → OCR → clasificación por contenido → reporte.
"""
import io
import sys
import json

sys.path.insert(0, "/app/backend")
from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/freefont/FreeSans.ttf"

DOCS = {
    "cedula": ["REPUBLICA DE CHILE", "SERVICIO DE REGISTRO CIVIL", "CEDULA DE IDENTIDAD",
               "RUN 16.212.567-2", "APELLIDOS: HERZBERG GADAN", "NOMBRES: ANDRES BENJAMIN"],
    "liquidacion": ["LIQUIDACION DE SUELDO", "EMPRESA CONSTRUCTORA LTDA", "RUT TRABAJADOR: 16.212.567-2",
                    "PERIODO: MAYO 2026", "SUELDO BASE: $1.250.000", "TOTAL HABERES: $1.480.000",
                    "LIQUIDO A PAGAR: $1.184.000"],
    "afp": ["CERTIFICADO DE COTIZACIONES", "AFP HABITAT", "AFILIADO RUT 16.212.567-2",
            "COTIZACIONES PREVISIONALES ULTIMOS 24 MESES", "EMPLEADOR: CONSTRUCTORA LTDA"],
    "cmf": ["COMISION PARA EL MERCADO FINANCIERO", "INFORME DE DEUDAS CMF",
            "RUT: 16.212.567-2", "DEUDA DIRECTA VIGENTE: $2.450.000", "MOROSIDAD: SIN MOROSIDAD"],
}


def gen_img(lineas, w=1300, h=950):
    im = Image.new("RGB", (w, h), "#f5f5f0")
    d = ImageDraw.Draw(im)
    f_big = ImageFont.truetype(FONT, 46)
    f = ImageFont.truetype(FONT, 36)
    y = 60
    for i, ln in enumerate(lineas):
        d.text((70, y), ln, fill="#111", font=f_big if i == 0 else f)
        y += 95 if i == 0 else 66
    return im


def whatsapp_lowres(im, lado=420, calidad=55):
    """Simula compresión de WhatsApp: reducción fuerte + JPEG de baja calidad."""
    f = lado / float(min(im.size))
    im = im.resize((int(im.width * f), int(im.height * f)))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=calidad)
    return Image.open(io.BytesIO(buf.getvalue()))


CASOS = [
    ("IMG-20260601-WA0001.jpg", whatsapp_lowres(gen_img(DOCS["cedula"])), "cedula"),
    ("IMG-20260601-WA0002.jpg", whatsapp_lowres(gen_img(DOCS["liquidacion"])), "liquidacion"),
    ("IMG-20260601-WA0003.jpg", whatsapp_lowres(gen_img(DOCS["afp"])), "afp"),
    ("IMG-20260601-WA0004.jpg", whatsapp_lowres(gen_img(DOCS["cmf"])), "cmf"),
    ("foto_rotada.jpg", whatsapp_lowres(gen_img(DOCS["liquidacion"]), lado=520).rotate(90, expand=True, fillcolor="#f5f5f0"), "liquidacion"),
    ("scan_rotado.png", gen_img(DOCS["cmf"]).rotate(270, expand=True, fillcolor="#f5f5f0"), "cmf"),
]


def run():
    import pdf_service as pdfs
    import ocr_service
    import folders_service as fsvc
    res, ok_total = [], 0
    for fn, im, esperado in CASOS:
        buf = io.BytesIO()
        im.convert("RGB").save(buf, format="JPEG" if fn.endswith(("jpg", "jpeg")) else "PNG", quality=88)
        raw = buf.getvalue()
        try:
            pdf, nuevo, _conv = pdfs.convertir_a_pdf(raw, fn)
            texto, metodo = ocr_service.extraer_texto(pdf, nuevo)
            clasif = fsvc.cat_de_texto(f"{nuevo} {texto[:800]}")
            rut_ok = "16212567" in texto.replace(".", "").replace("-", "").replace(" ", "")
            correcto = clasif == esperado and rut_ok
            ok_total += 1 if correcto else 0
            res.append({"nombre_original": fn, "esperado": esperado,
                        "renombrado_a": nuevo, "clasificacion_asignada": clasif,
                        "metodo_lectura": metodo, "caracteres_ocr": len(texto),
                        "rut_legible": rut_ok,
                        "texto_extraido": " ".join(texto.split())[:180],
                        "resultado": "✅ CORRECTO" if correcto else "❌ INCORRECTO"})
        except Exception as e:
            res.append({"nombre_original": fn, "esperado": esperado,
                        "resultado": f"❌ ERROR: {str(e)[:150]}"})
    print(json.dumps({"casos": res, "correctos": f"{ok_total}/{len(CASOS)}"},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    run()
