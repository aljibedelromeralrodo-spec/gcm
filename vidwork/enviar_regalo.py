import base64, sys
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")
from email_service import send_mail

video = base64.b64encode(open("/app/frontend/public/video-martin-suma-uc.mp4", "rb").read()).decode()
zipb = base64.b64encode(open("/app/frontend/public/martin-suma-uc-paquete.zip", "rb").read()).decode()

body = """
<div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;color:#1B2559">
<div style="background:#16297C;border-radius:14px;padding:26px;text-align:center;color:#fff">
<h1 style="margin:0;font-size:26px">💛 Martín <span style="color:#FFC93C">Suma UC</span></h1>
<p style="color:#C9D4F5;font-size:13px;letter-spacing:2px;margin:6px 0 0">UNA APP · UNA RED · UN CEREBRO · UN REGALO</p>
</div>
<p style="font-size:14px;line-height:1.7;margin-top:18px">Estimado equipo:</p>
<p style="font-size:14px;line-height:1.7">Adjuntamos el <b>video de presentación oficial</b> de Martín Suma UC (2:05 min) y el <b>paquete exportable completo</b>, pensado como regalo de responsabilidad social para instituciones de educación financiera: incluye la app móvil, la personalidad de Martín, la Conciencia (memoria privada de cada usuario), El Cerebro (red central de aprendizaje colectivo) y un panel de administración propio para personalizarlo con la identidad de la institución.</p>
<table style="width:100%;font-size:13.5px;line-height:1.6">
<tr><td>🎬 Video online:</td><td><a href="https://espejo-hibrido.preview.emergentagent.com/video-martin-suma-uc.mp4">Ver video</a></td></tr>
<tr><td>📱 App navegable:</td><td><a href="https://espejo-hibrido.preview.emergentagent.com/martin-app.html">Abrir Martín Suma UC</a></td></tr>
<tr><td>🧠 Panel El Cerebro:</td><td><a href="https://espejo-hibrido.preview.emergentagent.com/martin-admin.html">Panel de administración</a></td></tr>
<tr><td>🎁 Paquete:</td><td><a href="https://espejo-hibrido.preview.emergentagent.com/martin-suma-uc-paquete.zip">Descargar ZIP</a> (también adjunto)</td></tr>
</table>
<p style="font-size:14px;line-height:1.7">El archivo <b>LEEME.md</b> dentro del paquete explica la instalación (10 minutos) y cómo personalizar módulos, comunicación e identidad.</p>
<p style="font-size:14px;line-height:1.7">Con cariño,<br><b>Central Mutuos Con Creces · Responsabilidad Social</b></p>
</div>"""

r = send_mail(
    to="gerardo.ext@centralmutuos.cl",
    subject="🎁 Martín Suma UC — Video de presentación + Paquete de regalo institucional",
    body_html=body,
    attachments=[
        {"filename": "video-martin-suma-uc.mp4", "content_b64": video},
        {"filename": "martin-suma-uc-paquete.zip", "content_b64": zipb},
    ])
print(r)
