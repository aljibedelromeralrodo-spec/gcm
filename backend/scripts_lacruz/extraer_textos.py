import sys, json
from pathlib import Path
from pdfminer.high_level import extract_text
src = Path("/app/backend/scripts_lacruz/adjuntos")
out = {}
for p in sorted(src.glob("*.pdf")):
    try:
        t = extract_text(str(p)) or ""
    except Exception as e:
        t = f"[ERROR {e}]"
    out[p.name] = t[:6000]
Path("/app/backend/scripts_lacruz/textos.json").write_text(json.dumps(out, ensure_ascii=False))
for k, v in out.items():
    vv = " ".join(v.split())
    print("=" * 20, k, f"({len(v)} chars)")
    print(vv[:700])
