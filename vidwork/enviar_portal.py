import base64, sys
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")
from email_service import send_mail

video = base64.b64encode(open("/app/frontend/public/demo-portal-cliente.mp4", "rb").read()).decode()
LINK = "https://espejo-hibrido.preview.emergentagent.com/demo-portal-cliente.mp4"
PORTAL = "https://espejo-hibrido.preview.emergentagent.com/portal-cliente.html"

body = f"""<!DOCTYPE html><html lang="es"><body style="margin:0;padding:0;background-color:#ededee;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#ededee;padding:28px 0;">
<tr><td align="center">
<table role="presentation" width="620" cellpadding="0" cellspacing="0" style="max-width:620px;width:100%;background-color:#ffffff;">
  <tr><td style="background-color:#0e0e10;padding:30px 40px;text-align:left;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      <td style="font-family:Georgia,'Times New Roman',serif;">
        <div style="font-size:22px;letter-spacing:5px;color:#d4af37;">CENTRAL MUTUOS</div>
        <div style="font-size:10px;letter-spacing:4px;color:#f5e7b8;margin-top:4px;">CON CRECES</div>
      </td>
      <td align="right" style="font-family:Georgia,serif;font-size:11px;color:#9a9a9a;vertical-align:bottom;">Mutuaria regulada por la CMF</td>
    </tr></table>
  </td></tr>
  <tr><td style="height:4px;background-color:#d4af37;font-size:0;line-height:0;">&nbsp;</td></tr>
  <tr><td style="padding:32px 40px 8px;font-family:Georgia,serif;color:#111111;">
    <p style="margin:0 0 16px;font-size:15px;">Estimado equipo,</p>
    <h1 style="margin:0 0 6px;font-family:Georgia,serif;font-size:21px;color:#111111;font-weight:normal;">Portal del Cliente — Video de presentación</h1>
    <div style="height:2px;background-color:#d4af37;width:70px;margin:0 0 18px;"></div>
    <p style="margin:0 0 14px;font-size:14px;line-height:1.7;color:#3a3a3a;">Compartimos el video comercial del nuevo <b>Portal del Cliente</b> de Central Mutuos con Creces: la plataforma donde cada cliente sigue su crédito hipotecario en línea, de principio a fin, sin llamadas ni incertidumbre.</p>
  </td></tr>
  <tr><td style="padding:0 40px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-left:3px solid #d4af37;background-color:#faf8f1;">
      <tr><td style="padding:16px 20px;font-family:Georgia,serif;">
        <div style="font-size:13.5px;color:#111111;line-height:2;">
          <b style="color:#8a6a0f;">Ventajas del Portal del Cliente</b><br>
          ✓ Seguimiento del crédito <b>en tiempo real</b>, etapa por etapa<br>
          ✓ Carga de documentos desde el celular, con validación automática<br>
          ✓ Firma electrónica de documentos con respaldo E-Ser Chile<br>
          ✓ Notificaciones inmediatas de avances y pendientes<br>
          ✓ Descarga de certificados y comprobantes en un clic<br>
          ✓ Atención más rápida y menos llamadas: todo queda registrado
        </div>
      </td></tr>
    </table>
  </td></tr>
  <tr><td style="padding:22px 40px 6px;font-family:Georgia,serif;">
    <p style="margin:0 0 18px;font-size:13.5px;line-height:1.7;color:#3a3a3a;">El video (2:03 min) va <b>adjunto</b> a este correo y también disponible para descarga directa:</p>
    <table role="presentation" cellpadding="0" cellspacing="0" align="center" style="margin:0 auto 8px;">
      <tr><td style="background-color:#0e0e10;">
        <a href="{LINK}" style="display:inline-block;padding:13px 46px;font-family:Georgia,serif;font-size:14px;letter-spacing:1px;color:#d4af37;text-decoration:none;border-bottom:2px solid #d4af37;">Descargar el video</a>
      </td></tr>
    </table>
    <p style="margin:12px 0 0;font-size:12.5px;text-align:center;font-family:Georgia,serif;"><a href="{PORTAL}" style="color:#8a6a0f;">Ver el prototipo navegable del Portal del Cliente</a></p>
  </td></tr>
  <tr><td style="padding:26px 40px 30px;">
    <p style="margin:0;font-size:10.5px;line-height:1.6;color:#999999;font-family:Georgia,serif;border-top:1px solid #eeeeee;padding-top:14px;">Material interno de presentación. Aprobación de créditos sujeta a revisión de antecedentes según la normativa vigente y las políticas internas de la compañía.</p>
    <p style="margin:10px 0 0;font-size:10.5px;color:#999999;font-family:Georgia,serif;">Central Mutuos · Con Creces — Av. La Dehesa 1822, Of. 511, Torre Sur, Lo Barnechea</p>
  </td></tr>
</table>
</td></tr></table></body></html>"""

r = send_mail(
    to="gerardo.ext@centralmutuos.cl",
    cc=["rodrigo@centralmutuos.cl", "rene@centralmutuos.cl"],
    subject="Portal del Cliente — Video de presentación oficial (Central Mutuos con Creces)",
    body_html=body,
    attachments=[{"filename": "portal-del-cliente-video.mp4", "content_b64": video}])
print(r)
