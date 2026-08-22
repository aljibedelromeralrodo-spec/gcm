from dotenv import load_dotenv
load_dotenv('/app/backend/.env')
import sys
sys.path.insert(0, '/app/backend')
import asyncio
import re
from pathlib import Path

RX = re.compile(r"licencia|pre.?natal|post.?natal|embaraz|d[ií]as\s+trabajados?\s*:?\s*\d+|incapacidad|reposo|subsidio\s+maternal", re.I)


async def t():
    from database import db
    import ocr_service
    for patron in ['Javiera Espinoza', 'Yan Carmona', 'Gloria Bolados', 'JULIETH MARIN', 'Ignacio Pizarro']:
        it = await db.proc_queue.find_one({'subject': {'$regex': patron, '$options': 'i'}})
        if not it:
            continue
        folder = Path(it.get('attachments_bytes_dir') or '')
        hallado = []
        for fn in (it.get('attachments') or [])[:20]:
            p = folder / fn
            if not p.exists():
                continue
            texto = ocr_service.texto_embebido(p.read_bytes())
            if not texto or len(texto) < 60:
                continue
            plano = ' '.join(texto.split())
            for m in RX.finditer(plano):
                s = max(0, m.start() - 60)
                hallado.append((fn[:42], plano[s:m.end() + 100][:190]))
        if hallado:
            print(f"== {patron} | {(it.get('subject') or '')[:60]} ==")
            vistos = set()
            for fn, frag in hallado[:6]:
                k = frag[:60]
                if k in vistos:
                    continue
                vistos.add(k)
                print(f"   [{fn}] ...{frag}")

asyncio.run(t())
