import io, sys, json
sys.path.insert(0, "/app/backend")
from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

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
    "boletas": ["BOLETA DE HONORARIOS ELECTRONICA N 145", "RUT EMISOR 16.212.567-2",
                "POR SERVICIOS PROFESIONALES", "TOTAL HONORARIOS: $850.000", "RETENCION 13,75%"],
}

def gen_img(lineas, w=1200, h=900, rotar=0, lowres=False):
    im = Image.new("RGB", (w, h), "#f5f5f0")
    d = ImageDraw.Draw(im)
    try:
        f_big = ImageFont.truetype(FONT, 44)
        f = ImageFont.truetype(FONT, 34)
    except Exception:
        f_big = f = ImageFont.load_default()
    y = 60
    for i, ln in enumerate(lineas):
        d.text((70, y), ln, fill="#111", font=f_big if i == 0 else f)
        y += 90 if i == 0 else 64
    if lowres:
        im = im.resize((w // 3, h // 3))
    if rotar:
        im = im.rotate(rotar, expand=True, fillcolor="#f5f5f0")
    return im

def caso(nombre_archivo, im, fmt):
    buf = io.BytesIO()
    im.save(buf, format=fmt, quality=88 if fmt == "JPEG" else None)
    return nombre_archivo, buf.getvalue()

CASOS = [
    ("IMG_20260601_1032.jpg",) + (gen_img(DOCS["liquidacion"]), "JPEG"),
    ("foto_carnet.png",) + (gen_img(DOCS["cedula"]), "PNG"),
    ("certificado afp habitat.jpg",) + (gen_img(DOCS["afp"]), "JPEG"),
    ("WhatsApp Image 2026-06-01.jpeg",) + (gen_img(DOCS["cmf"]), "JPEG"),
    ("scan0001.png",) + (gen_img(DOCS["boletas"], rotar=90), "PNG"),
    ("IMG_5566.jpg",) + (gen_img(DOCS["cedula"], lowres=True), "JPEG"),
]
ESPERADOS = ["liquidacion", "cedula", "afp/cotizacion", "cmf/deuda", "boletas/honorario", "cedula"]

def clasificar_folders(fn, texto):
    import folders_service as fsvc
    return fsvc.cat_de_texto(f"{fn} {texto[:800]}")

def run():
    import pdf_service as pdfs
    import ocr_service
    from victoria_independiente import _clasificar_tipo
    res = []
    for i, (fn, im, fmt) in enumerate(CASOS):
        nombre, raw = caso(fn, im, fmt)
        try:
            pdf, nuevo, conv = pdfs.convertir_a_pdf(raw, nombre)
            texto, metodo = ocr_service.extraer_texto(pdf, nuevo)
            rut_ok = "16.212.567-2" in texto or "16212567" in texto.replace(".", "").replace("-", "")
            cls_daniela = _clasificar_tipo(nuevo, texto)
            cls_folders = clasificar_folders(nuevo, texto)
            res.append({"caso": nombre, "esperado": ESPERADOS[i], "convertido_a": nuevo,
                        "metodo": metodo, "chars_ocr": len(texto), "rut_legible": rut_ok,
                        "clasif_daniela": cls_daniela, "clasif_carpetas": cls_folders})
        except Exception as e:
            res.append({"caso": nombre, "esperado": ESPERADOS[i], "error": str(e)[:120]})
    print(json.dumps(res, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    run()
