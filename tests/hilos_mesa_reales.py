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
        ('Gonzalo Araos', 'from:aprobaciones@centralmutuos.cl subject:"Gonzalo Araos" newer_than:120d'),
        ('Ariel Araya', 'from:aprobaciones@centralmutuos.cl subject:"Ariel Araya" newer_than:120d'),
        ('Viviana Cardenas', 'from:aprobaciones@centralmutuos.cl subject:"Viviana" newer_than:120d'),
        ('Yan Carmona', 'from:aprobaciones@centralmutuos.cl subject:"Yan Carmona" newer_than:120d'),
        ('Marcela Escalona', 'from:aprobaciones@centralmutuos.cl subject:"Marcela Escalona" newer_than:120d'),
        ('Maria Encina', 'from:aprobaciones@centralmutuos.cl subject:"Encina" newer_than:120d'),
        ('EDAD explicita', '(from:aprobaciones@centralmutuos.cl OR to:aprobaciones@centralmutuos.cl) ("por la edad" OR "edad máxima" OR "edad maxima" OR "80 años" OR "75 años" OR "acorta") newer_than:120d'),
        ('HONORARIOS+LIQ', 'to:aprobaciones@centralmutuos.cl (honorarios AND liquidaciones) newer_than:120d'),
        ('SEGUNDO EMPLEO', '(from:aprobaciones@centralmutuos.cl OR to:aprobaciones@centralmutuos.cl) ("ambos trabajos" OR "dos empleadores" OR "segundo trabajo" OR "otro empleador" OR "suma de rentas" OR "ambas rentas") newer_than:120d'),
    ]
    vistos = set()
    for tag, q in consultas:
        r = svc.users().messages().list(userId='me', q=q, maxResults=25).execute()
        msgs = r.get('messages', [])
        tids = []
        for m in msgs:
            if m['threadId'] not in tids:
                tids.append(m['threadId'])
        print(f'\n######## {tag} — {len(tids)} hilos ########')
        for tid in tids[:6]:
            if tid in vistos:
                print(f'  (hilo {tid} ya mostrado)')
                continue
            vistos.add(tid)
            th = svc.users().threads().get(userId='me', id=tid, format='full').execute()
            print(f'--- hilo ({len(th["messages"])} msgs) ---')
            for mm in th['messages']:
                c = await asyncio.to_thread(gp._msg_a_correo, svc, mm['id'])
                if 'ethangerardobarr' in (c['from'] or ''):
                    continue
                cuerpo = ' '.join((c['body'] or '').split())
                cuerpo = re.split(r'El (?:lun|mar|mi[eé]|jue|vie|s[aá]b|dom)[,\s]', cuerpo)[0]
                cuerpo = re.split(r'Saludos, \*?CENTRALMUTUOS', cuerpo)[0]
                frm = re.sub(r'<.*?>', '', c['from']).strip()[:32]
                print(f"  >> {c['date'][:16]} | {frm} | {c['subject'][:48]}")
                print(f"     {cuerpo[:700]}")

asyncio.run(t())
