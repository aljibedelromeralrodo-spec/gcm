from pdf2image import convert_from_path
import pytesseract, json, re
from pathlib import Path

src = Path("/app/backend/scripts_lacruz/rodrigo_arriendo/Arriendo Rodrigo")
out = {}
for p in sorted(src.glob("*.pdf")):
    try:
        pages = convert_from_path(str(p), dpi=150, first_page=1, last_page=2)
        t = "\n".join(pytesseract.image_to_string(pg, lang="spa") for pg in pages)
        out[p.stem] = " ".join(t.split())[:4500]
        print("OK", p.stem, len(out[p.stem]), flush=True)
    except Exception as e:
        out[p.stem] = f"[ERROR {e}]"
        print("ERR", p.stem, e, flush=True)
json.dump(out, open("/app/backend/scripts_lacruz/rodrigo_ocr.json", "w"), ensure_ascii=False)
print("LISTO", len(out))
