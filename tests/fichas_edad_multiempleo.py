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

    print('===== A) FICHAS CON EDAD (entrantes, 120d) =====')
    q = '("Edad:" OR "edad :") -from:ethangerardobarr@gmail.com newer_than:120d'
    r = svc.users().messages().list(userId='me', q=q, maxResults=60).execute()
    edades = []
    for m in r.get('messages', []):
        c = await asyncio.to_thread(gp._msg_a_correo, svc, m['id'])
        cuerpo = ' '.join((c['body'] or '').split())
        em = re.search(r'[Ee]dad\s*:?\s*(\d{2})', cuerpo)
        if not em:
            continue
        edad = int(em.group(1))
        nm = re.search(r'[Nn]ombre\s*[Cc]ompleto\s*:?\s*([A-ZÁÉÍÓÚÑa-záéíóúñ ]{5,45})', cuerpo)
        nombre = nm.group(1).strip() if nm else c['subject'][:40]
        edades.append((edad, nombre, c['date'][:10], c['from'][:30]))
    edades.sort(reverse=True)
    for e in edades[:25]:
        print(f'  {e[0]} años | {e[1][:38]} | {e[2]} | {e[3]}')
    print(f'  TOTAL fichas con edad: {len(edades)} | >=55: {sum(1 for x in edades if x[0]>=55)} | >=60: {sum(1 for x in edades if x[0]>=60)}')

    print('\n===== B) HONORARIOS (entrantes, 120d) =====')
    q = 'honorarios -from:ethangerardobarr@gmail.com -from:aprobaciones@centralmutuos.cl newer_than:120d'
    r = svc.users().messages().list(userId='me', q=q, maxResults=30).execute()
    for m in r.get('messages', [])[:20]:
        d = svc.users().messages().get(userId='me', id=m['id'], format='metadata',
                                       metadataHeaders=['From', 'Subject', 'Date']).execute()
        hs = {h['name'].lower(): h['value'] for h in d['payload'].get('headers', [])}
        print(f"  {hs.get('date','')[5:17]} | {hs.get('from','')[:32]} | {hs.get('subject','')[:62]}")

    print('\n===== C) MULTI-EMPLEO en fichas (2+ empleadores / suma rentas) =====')
    q = '("empleador 1" OR "empleador 2" OR "trabajo 1" OR "trabajo 2" OR "renta 1" OR "renta 2" OR "dos liquidaciones" OR "ambas liquidaciones" OR "los dos trabajos") -from:ethangerardobarr@gmail.com newer_than:120d'
    r = svc.users().messages().list(userId='me', q=q, maxResults=25).execute()
    for m in r.get('messages', [])[:15]:
        c = await asyncio.to_thread(gp._msg_a_correo, svc, m['id'])
        cuerpo = ' '.join((c['body'] or '').split())[:420]
        print(f"  >> {c['date'][:10]} | {c['from'][:30]} | {c['subject'][:52]}")
        print(f"     {cuerpo}")

    print('\n===== D) COMPLEMENTO/CODEUDOR conteo 120d =====')
    for kw in ['complementa', 'complemento', 'codeudor', 'codeudora']:
        q = f'{kw} -from:ethangerardobarr@gmail.com newer_than:120d'
        r = svc.users().messages().list(userId='me', q=q, maxResults=100).execute()
        print(f'  "{kw}": {len(r.get("messages", []))} correos')

asyncio.run(t())
