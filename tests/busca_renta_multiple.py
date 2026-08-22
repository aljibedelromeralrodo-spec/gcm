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
        ('EDAD/PLAZO', '(("edad maxima" OR "edad máxima" OR "por la edad" OR "años de plazo" OR "plazo maximo" OR "plazo máximo" OR "acorta el plazo") AND (credito OR crédito OR mesa)) newer_than:120d'),
        ('DOS EMPLEADORES', '("dos empleadores" OR "segundo empleador" OR "dos trabajos" OR "ambos empleadores" OR "dos contratos" OR "renta multiple" OR "rentas de ambos") newer_than:120d'),
        ('DEP+INDEP', '(liquidaciones AND ("boletas de honorarios" OR honorarios)) newer_than:120d'),
        ('TRES TRABAJOS', '("tres empleadores" OR "tres trabajos" OR "tercer empleador") newer_than:120d'),
        ('MESA plazo/edad', 'from:aprobaciones@centralmutuos.cl (plazo OR edad OR años) newer_than:120d'),
    ]
    for tag, q in consultas:
        r = svc.users().messages().list(userId='me', q=q, maxResults=15).execute()
        msgs = r.get('messages', [])
        print(f'=== {tag}: {len(msgs)} ===')
        for m in msgs[:12]:
            d = svc.users().messages().get(userId='me', id=m['id'], format='metadata',
                                           metadataHeaders=['From', 'Subject', 'Date']).execute()
            hs = {h['name'].lower(): h['value'] for h in d['payload'].get('headers', [])}
            lb = 'IN' if 'INBOX' in (d.get('labelIds') or []) else 'OUT'
            print(f"  [{lb}] {hs.get('date','')[5:17]} | {hs.get('from','')[:34]} | {hs.get('subject','')[:66]}")

asyncio.run(t())
