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
        ('Gonzalo Araos', 'subject:"Gonzalo Araos" newer_than:120d'),
        ('Francisca Hernandez', 'subject:"Francisca Hernandez" newer_than:120d'),
        ('Yan Carmona', '"Yan Carmona" newer_than:120d'),
        ('Javiera Espinoza', 'subject:"Javiera Espinoza" newer_than:120d'),
        ('Viviana Cardenas', '"Viviana Cardenas" newer_than:120d'),
        ('Ariel Araya', 'subject:"Ariel Araya" newer_than:120d'),
        ('MJ ARGANDOÑA', 'subject:"ARGANDOÑA" newer_than:120d'),
        ('Marcela Escalona', 'subject:"Marcela Escalona" newer_than:120d'),
        ('Maria Encina', 'subject:"María Encina" newer_than:120d'),
    ]
    vistos = set()
    for tag, q in consultas:
        r = svc.users().messages().list(userId='me', q=q, maxResults=30).execute()
        msgs = r.get('messages', [])
        tids = []
        for m in msgs:
            if m['threadId'] not in tids:
                tids.append(m['threadId'])
        print(f'\n######## CASO: {tag} — {len(tids)} hilos ########')
        for tid in tids[:3]:
            if tid in vistos:
                continue
            vistos.add(tid)
            th = svc.users().threads().get(userId='me', id=tid, format='full').execute()
            print(f'--- hilo {tid} ({len(th["messages"])} msgs) ---')
            for mm in th['messages']:
                c = await asyncio.to_thread(gp._msg_a_correo, svc, mm['id'])
                cuerpo = ' '.join((c['body'] or '').split())
                cuerpo = re.split(r'El (?:lun|mar|mi[eé]|jue|vie|s[aá]b|dom)[,\s]', cuerpo)[0]
                cuerpo = re.split(r'Saludos, \*?CENTRALMUTUOS', cuerpo)[0]
                frm = re.sub(r'<.*?>', '', c['from']).strip()[:30]
                print(f"  >> {c['date'][:16]} | {frm}")
                print(f"     {cuerpo[:600]}")

asyncio.run(t())
