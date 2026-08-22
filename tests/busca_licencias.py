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
    objetivos = [('Javiera Espinoza', 'subject:"Javiera Espinoza" newer_than:60d'),
                 ('Yan Carmona', 'subject:"Yan Carmona" newer_than:60d'),
                 ('Francisca Hernandez', 'subject:"EVALUACION 18.709.872-6" newer_than:60d'),
                 ('Gloria Bolados', '"Gloria Bolados" newer_than:60d'),
                 ('Julieth Marin', 'subject:"JULIETH MARIN" newer_than:60d')]
    for nombre, q in objetivos:
        r = svc.users().messages().list(userId='me', q=q, maxResults=3).execute()
        for m in r.get('messages', [])[:2]:
            c = await asyncio.to_thread(gp._msg_a_correo, svc, m['id'])
            cuerpo = ' '.join((c['body'] or '').split())
            frags = []
            for pat in ['licencia', 'natal', 'embaraz', 'trabajad', 'incapacidad', 'reposo', 'ccaf']:
                for mm in re.finditer(pat, cuerpo, re.I):
                    s = max(0, mm.start() - 70)
                    frags.append(cuerpo[s:mm.end() + 90])
            adjs = [p['filename'] for p in c['pdfs']]
            lic_adj = [a for a in adjs if re.search('licencia|subsidio|natal|pago', a, re.I)]
            if frags or lic_adj:
                print(f'== {nombre} | {c["subject"][:60]} ==')
                for f in list(dict.fromkeys(frags))[:4]:
                    print('   ...', f[:170])
                print('   ADJ:', (lic_adj or adjs)[:8])

asyncio.run(t())
