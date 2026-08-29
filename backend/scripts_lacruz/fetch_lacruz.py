from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
import sys
sys.path.insert(0, "/app/backend")
import email_service as es
import email
from pathlib import Path
out = Path("/app/backend/scripts_lacruz/adjuntos"); out.mkdir(exist_ok=True)
acc = next(a for a in es.ACCOUNTS if a["rol"] == "principal")
m = es._connect(acc); m.select("INBOX", readonly=True)
for uid in ["4307", "4308", "4288", "4287", "4286", "4297", "4298"]:
    typ, md = m.uid("fetch", uid, "(BODY.PEEK[])")
    if not md or not isinstance(md[0], tuple):
        print(uid, "SIN DATA"); continue
    info = es._parse_full_message(email.message_from_bytes(md[0][1]), with_bytes=True)
    print("=" * 80)
    print("UID", uid, "|", info["date"], "|", info["subject"])
    print("BODY:", info["body"][:1600])
    for a in info["attachments"]:
        fn = f"{uid}__{a['filename']}"
        (out / fn).write_bytes(a.get("content_bytes") or b"")
        print("  ADJ:", fn, a["size"])
m.logout()
