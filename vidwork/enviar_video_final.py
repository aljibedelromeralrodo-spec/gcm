import base64, sys
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")
from email_service import send_mail

video = base64.b64encode(open("/app/frontend/public/video-martin-suma-uc.mp4", "rb").read()).decode()
LINK = "https://espejo-hibrido.preview.emergentagent.com/video-martin-suma-uc.mp4"

body = f"""
<div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;color:#1B2559">
<div style="background:#16297C;border-radius:14px;padding:26px;text-align:center;color:#fff">
<h1 style="margin:0;font-size:26px">💛 Martín <span style="color:#FFC93C">Suma UC</span></h1>
<p style="color:#C9D4F5;font-size:13px;letter-spacing:2px;margin:6px 0 0">VIDEO DE PRESENTACIÓN — VERSIÓN FINAL</p>
</div>
<p style="font-size:14px;line-height:1.7;margin-top:18px">Estimado equipo:</p>
<p style="font-size:14px;line-height:1.7">Adjuntamos la <b>versión final</b> del video de presentación de Martín Suma UC, que <b>reemplaza a la anterior</b>. Esta versión muestra capturas reales de la app funcionando: el registro diario de gastos, las metas de ahorro, Martín animado conversando, los módulos navegables, la Conciencia, el Modo Crisis, los Desafíos de Ahorro y el Modo Familia — alternadas con imágenes de familias chilenas mientras suena la locución oficial.</p>
<p style="font-size:14px;line-height:1.7">🎬 <a href="{LINK}">Ver / descargar el video online</a> (también va adjunto).</p>
<p style="font-size:14px;line-height:1.7">Con cariño,<br><b>Central Mutuos Con Creces · Responsabilidad Social</b></p>
</div>"""

r = send_mail(
    to="gerardo.ext@centralmutuos.cl",
    subject="🎬 Martín Suma UC — Video de presentación VERSIÓN FINAL (reemplaza la anterior)",
    body_html=body,
    attachments=[{"filename": "video-martin-suma-uc-FINAL.mp4", "content_b64": video}])
print(r)
