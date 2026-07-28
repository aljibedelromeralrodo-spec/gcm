"""Encola correos específicos (por seq num en gerardo.ext) en proc_queue para prueba E2E."""
import asyncio
import os
import sys
import uuid
import email as em
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
load_dotenv("/app/backend/.env")
import email_service as m
import pdf_service as pdfs
from server import _safe_name

PROC_DIR = Path("/app/backend/storage/proc")
SEQS = sys.argv[1:] or ["9851", "9697", "9696"]


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    acc = next(a for a in m.ACCOUNTS if "gerardo.ext" in a["user"])
    c = m._connect(acc)
    c.select("INBOX", readonly=True)
    for seq in SEQS:
        typ, msgdata = c.fetch(seq, "(BODY.PEEK[])")
        if not msgdata or not isinstance(msgdata[0], tuple):
            print(seq, "NO DATA")
            continue
        info = m._parse_full_message(em.message_from_bytes(msgdata[0][1]), with_bytes=True)
        exists = await db.proc_queue.find_one({"subject": info["subject"], "date_iso": info["date"]})
        if exists:
            print(seq, "YA EXISTE:", info["subject"][:50])
            continue
        qid = str(uuid.uuid4())
        folder = PROC_DIR / qid
        folder.mkdir(parents=True, exist_ok=True)
        attachments = []
        for a in info["attachments"]:
            raw, nombre = a.get("content_bytes"), a["filename"]
            if not raw:
                continue
            try:
                raw, nombre, _ = pdfs.convertir_a_pdf(raw, nombre)
            except Exception:
                continue
            fn = _safe_name(nombre)
            (folder / fn).write_bytes(raw)
            attachments.append(fn)
        await db.proc_queue.insert_one({
            "id": qid, "subject": info["subject"], "sender": info["from"],
            "date_iso": info["date"], "status": "pendiente",
            "body_preview": (info.get("body") or "")[:500],
            "body_full": (info.get("body") or "")[:8000],
            "attachments": attachments, "attachments_bytes_dir": str(folder),
            "classification": {}, "campos": {}, "drive_folder_id": None,
        })
        print(seq, "ENCOLADO", qid, "|", info["subject"][:55], "| adjuntos:", attachments)
    c.logout()

asyncio.run(main())
