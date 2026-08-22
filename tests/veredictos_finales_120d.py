from dotenv import load_dotenv
load_dotenv('/app/backend/.env')
import sys
sys.path.insert(0, '/app/backend')
import asyncio
import re


async def t():
    import gmail_pubsub as gp
    creds = await gp._creds()
    svc = gp._svc(creds)
    consultas = [
        ('EDUAR ARAYA (55a) hilo completo', '"Eduar" -from:ethangerardobarr@gmail.com newer_than:120d'),
        ('CATALINA AGUILERA (mixto)', '"Catalina Aguilera" -from:ethangerardobarr@gmail.com newer_than:120d'),
        ('MESA menciona plazo/edad/años', 'from:aprobaciones@centralmutuos.cl ("plazo" OR "edad" OR "años") newer_than:120d'),
    ]
    for tag, q in consultas:
        r = svc.users().messages().list(userId='me', q=q, maxResults=25).execute()
        msgs = r.get('messages', [])
        print(f'\n######## {tag} — {len(msgs)} msgs ########')
        for m in msgs[:14]:
            c = await asyncio.to_thread(gp._msg_a_correo, svc, m['id'])
            if 'ethangerardobarr' in (c['from'] or ''):
                continue
            cuerpo = ' '.join((c['body'] or '').split())
            cuerpo = re.split(r'El (?:lun|mar|mi[eé]|jue|vie|s[aá]b|dom)[,\s]', cuerpo)[0]
            cuerpo = re.split(r'Saludos, \*?CENTRALMUTUOS', cuerpo)[0]
            frm = re.sub(r'<.*?>', '', c['from']).strip()[:30]
            print(f"  >> {c['date'][:16]} | {frm} | {c['subject'][:52]}")
            print(f"     {cuerpo[:520]}")

asyncio.run(t())
