"""Tests iter 16 — folders con Melisa Rivera, seguimiento, gastos operacionales pagos, SMTP log, autocorreo."""
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://risk-assess-17.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# 1) folders-light incluye Melisa Rivera
def test_folders_light_melisa(sess):
    r = sess.get(f"{API}/clientes/folders-light", timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    # Might be dict {folders: [...]} or list
    folders = data.get("folders") if isinstance(data, dict) else data
    assert isinstance(folders, list)
    print(f"Total folders: {len(folders)}")
    names = []
    for f in folders:
        n = f.get("nombre") or f.get("name") or f.get("cliente") or ""
        names.append(n)
    joined = " | ".join(names).lower()
    print("Sample folders:", names[:20])
    assert "melisa" in joined, f"Melisa Rivera not found in folders. Names sample: {names[:40]}"
    assert not any(n.strip().lower() == "gerardo" for n in names), "Found bogus 'Gerardo' folder"


# 2) seguimiento clientes populado
def test_seguimiento_clientes(sess):
    r = sess.get(f"{API}/seguimiento/clientes", timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    lst = data.get("clientes") if isinstance(data, dict) else data
    assert isinstance(lst, list)
    print(f"Total seguimiento clientes: {len(lst)}")
    assert len(lst) >= 1, "Empty seguimiento list"
    sample = lst[0]
    print("Sample keys:", list(sample.keys()))
    print("Sample:", sample)
    # Required fields per request
    for k in ["cliente_display", "estado", "ejecutivo_externo", "correo_remitente", "total_correos"]:
        assert k in sample, f"missing field {k} in seguimiento cliente"


# 3) Excel export
def test_seguimiento_excel(sess):
    r = sess.get(f"{API}/reportes/seguimiento/excel", timeout=60)
    assert r.status_code == 200, r.text
    ct = r.headers.get("Content-Type", "")
    print("Content-Type:", ct)
    assert "excel" in ct.lower() or "spreadsheet" in ct.lower() or "ms-excel" in ct.lower()
    assert b"<table" in r.content.lower() or b"<tr" in r.content.lower()


# 4) gastos log with pagado/saldo/estado_pago
def test_gastos_log_fields(sess):
    r = sess.get(f"{API}/gastos-operacionales/log", timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    lst = data.get("log") if isinstance(data, dict) else data
    assert isinstance(lst, list), f"Expected list, got {type(lst)}: {data}"
    print(f"Total gastos entries: {len(lst)}")
    if lst:
        sample = lst[0]
        print("Sample keys:", list(sample.keys()))
        for k in ["pagado", "saldo", "estado_pago"]:
            assert k in sample, f"missing field {k}"


# 5) Register a payment then delete it
def test_gastos_pago_lifecycle(sess):
    r = sess.get(f"{API}/gastos-operacionales/log", timeout=60)
    assert r.status_code == 200
    data = r.json()
    lst = data.get("log") if isinstance(data, dict) else data
    if not lst:
        pytest.skip("Empty gastos log")
    # find entry with numeric total and no prior pagos to keep clean
    entry = None
    for e in lst:
        total = e.get("total") or e.get("monto") or e.get("monto_total")
        if total and float(total) > 0:
            entry = e
            break
    if not entry:
        pytest.skip("No gastos entry with total")
    eid = entry.get("id") or entry.get("_id")
    total = float(entry.get("total") or entry.get("monto") or entry.get("monto_total"))
    pagado_before = float(entry.get("pagado") or 0)
    print(f"Using entry id={eid} total={total} pagado_before={pagado_before}")

    # Register payment of 1 UF (small)
    pago_monto = 1
    rp = sess.post(f"{API}/gastos-operacionales/log/{eid}/pago",
                    json={"monto": pago_monto, "fecha": "2026-08-03"}, timeout=30)
    assert rp.status_code == 200, f"pago failed: {rp.status_code} {rp.text}"
    print("Pago response:", rp.json())

    # Verify saldo
    r2 = sess.get(f"{API}/gastos-operacionales/log", timeout=60)
    lst2 = r2.json().get("log") if isinstance(r2.json(), dict) else r2.json()
    updated = next((e for e in lst2 if (e.get("id") or e.get("_id")) == eid), None)
    assert updated, "entry disappeared after payment"
    pagado_after = float(updated.get("pagado") or 0)
    saldo_after = float(updated.get("saldo") or 0)
    print(f"After pago: pagado={pagado_after} saldo={saldo_after} estado={updated.get('estado_pago')}")
    assert pagado_after == pagado_before + pago_monto
    assert abs(saldo_after - (total - pagado_after)) < 0.01
    assert updated.get("estado_pago") in ("parcial", "pagado")

    # Find the index of the pago just added
    pagos = updated.get("pagos") or []
    # delete last pago (highest index)
    idx = len(pagos) - 1
    rd = sess.delete(f"{API}/gastos-operacionales/log/{eid}/pago/{idx}", timeout=30)
    assert rd.status_code == 200, f"delete pago failed: {rd.status_code} {rd.text}"
    print("Delete response:", rd.json())

    # Verify cleanup
    r3 = sess.get(f"{API}/gastos-operacionales/log", timeout=60)
    lst3 = r3.json().get("log") if isinstance(r3.json(), dict) else r3.json()
    restored = next((e for e in lst3 if (e.get("id") or e.get("_id")) == eid), None)
    assert float(restored.get("pagado") or 0) == pagado_before, "pagado not restored"


# 6) Invalid amount
def test_gastos_pago_invalid(sess):
    r = sess.get(f"{API}/gastos-operacionales/log", timeout=60)
    lst = r.json().get("log") if isinstance(r.json(), dict) else r.json()
    if not lst:
        pytest.skip("Empty log")
    eid = lst[0].get("id") or lst[0].get("_id")
    # amount 0
    r1 = sess.post(f"{API}/gastos-operacionales/log/{eid}/pago",
                    json={"monto": 0, "fecha": "2026-08-03"}, timeout=30)
    print("monto=0 =>", r1.status_code, r1.text[:200])
    assert r1.status_code == 400
    # amount text
    r2 = sess.post(f"{API}/gastos-operacionales/log/{eid}/pago",
                    json={"monto": "abc", "fecha": "2026-08-03"}, timeout=30)
    print("monto=abc =>", r2.status_code, r2.text[:200])
    assert r2.status_code in (400, 422)


# 7) SMTP log
def test_smtp_log(sess):
    r = sess.get(f"{API}/correos/smtp-log?limit=10", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    lst = data.get("log") if isinstance(data, dict) else data
    assert isinstance(lst, list)
    print(f"SMTP log entries: {len(lst)}")
    if lst:
        sample = lst[0]
        print("Sample keys:", list(sample.keys()))
        assert "smtp_code" in sample or "code" in sample
        assert "smtp_response" in sample or "response" in sample


# 8) Autocorreo status
def test_autocorreo_status(sess):
    r = sess.get(f"{API}/autocorreo/status", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    print("autocorreo status keys:", list(data.keys()))
    print("data sample:", {k: data[k] for k in list(data.keys())[:8]})
    assert data.get("enabled") is True
