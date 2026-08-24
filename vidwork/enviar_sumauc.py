import base64, sys
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")
from email_service import send_mail

body = open("/app/frontend/public/correo-sumauc-c.html", encoding="utf-8").read()
video = base64.b64encode(open("/app/frontend/public/video-martin-suma-uc.mp4", "rb").read()).decode()
zipb = base64.b64encode(open("/app/frontend/public/martin-suma-uc-paquete.zip", "rb").read()).decode()

r = send_mail(
    to="jibanezj@estudiante.uc.cl",
    subject="💛 Martín Suma UC — Un regalo de Central Mutuos para Suma UC",
    body_html=body,
    attachments=[
        {"filename": "video-martin-suma-uc.mp4", "content_b64": video},
        {"filename": "martin-suma-uc-paquete.zip", "content_b64": zipb},
    ])
print(r)
