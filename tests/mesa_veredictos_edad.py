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
    casos = ['Gonzalo Araos', 'Ariel Araya', 'Yan Carmona', 'Javiera Espinoza',
             'Ehestefany Mora', 'Carlos Rodríguez', 'Mariannys Giron', 'Viviana Cardenas',
             'Joaquín Orellana', 'MARIA JOSE ARGANDOÑA']
    for nombre in casos:
        q = f'from:aprobaciones@centralmutuos.cl "{nombre}" newer_than:120d'
        r = svc.users().messages().list(userId='me', q=q, maxResults=2).execute()
        for m in r.get('messages', [])[:1]:
            c = await asyncio.to_thread(gp._msg_a_correo, svc, m['id'])
            cuerpo = ' '.join((c['body'] or '').split())
            cuerpo = re.split(r'El (?:lun|mar|mi[eé]|jue|vie|s[aá]b|dom)', cuerpo)[0]
            print(f"== {nombre} | {c['subject'][:55]} ==")
            print('  ', cuerpo[:340])

asyncio.run(t())
