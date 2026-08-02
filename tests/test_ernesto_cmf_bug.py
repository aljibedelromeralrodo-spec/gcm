"""
Tests for the Ernesto Díaz CMF misclassification bug + email preview / incompleto gating.
NO se envían correos reales: confirm=false / o confirm=true SIN force_incompleto (esperamos 412).
"""
import os
import sys
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # frontend/.env value
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

ERNESTO_ID = "7a510501-b702-4707-bc10-b1b3d4e8868a"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---- 1. GET folders?q=ernesto: verify classification ----
def test_ernesto_folder_no_cmf(session):
    r = session.get(f"{BASE_URL}/api/clientes/folders", params={"q": "ernesto"}, timeout=90)
    assert r.status_code == 200, r.text
    data = r.json()
    folders = data.get("folders") or data.get("items") or data
    if isinstance(folders, dict):
        folders = folders.get("folders", [])
    # find Ernesto
    ern = None
    for f in folders:
        if f.get("id") == ERNESTO_ID or "ERNESTO" in (f.get("name") or f.get("cliente") or "").upper():
            ern = f
            break
    assert ern is not None, f"Ernesto folder not found. Got: {[f.get('name') for f in folders[:5]]}"
    print("Ernesto folder:", ern.get("name"), "id=", ern.get("id"))
    cats = ern.get("doc_categories") or []
    assert "cmf" not in cats, f"'cmf' should NOT be in doc_categories, got {cats}"
    assert ern.get("is_ready_to_send") is False, f"is_ready_to_send should be False, got {ern.get('is_ready_to_send')}"
    prob = ern.get("prob_aprobacion") or {}
    factores = prob.get("factores") or []
    joined = " | ".join(factores)
    assert "cmf" in joined.lower() or "CMF" in joined, f"factores should mention CMF: {factores}"


# ---- 2. send-email preview confirm:false => 200 with missing_docs ----
def test_send_email_preview_incompleto(session):
    r = session.post(
        f"{BASE_URL}/api/clientes/folders/{ERNESTO_ID}/send-email",
        json={"to_addr": "test@centralmutuos.cl", "confirm": False, "include_merged": False},
        timeout=60,
    )
    assert r.status_code == 200, f"{r.status_code}: {r.text[:400]}"
    d = r.json()
    assert d.get("docs_completos") is False, d
    missing = d.get("missing_docs") or []
    assert any("CMF" in m or "cmf" in m.lower() for m in missing), f"expected CMF in missing_docs: {missing}"
    assert d.get("body_html"), "body_html empty"
    assert len(d["body_html"]) > 50


# ---- 3. confirm=true sin force_incompleto => 412 ----
def test_send_email_confirm_without_force_returns_412(session):
    r = session.post(
        f"{BASE_URL}/api/clientes/folders/{ERNESTO_ID}/send-email",
        json={"to_addr": "test@centralmutuos.cl", "confirm": True, "include_merged": False},
        timeout=60,
    )
    assert r.status_code == 412, f"expected 412, got {r.status_code}: {r.text[:400]}"
    body = r.text.lower()
    assert "incompleta" in body or "incomplet" in body, r.text[:400]


# ---- 4. classifier unit tests via python ----
def test_classifier_functions():
    sys.path.insert(0, "/app/backend")
    import folders_service
    import ai_extract

    assert folders_service.cat_de_texto("INFNOMAT-19492155.pdf") == "extras", \
        f"got {folders_service.cat_de_texto('INFNOMAT-19492155.pdf')}"
    assert folders_service.cat_de_texto("informe_de_deudas_cmf.pdf") == "cmf", \
        f"got {folders_service.cat_de_texto('informe_de_deudas_cmf.pdf')}"
    res = ai_extract._fallback_clasificar(
        "INFORME DE NO MATRIMONIO Servicio de Registro Civil",
        "INFNOMAT-x.pdf",
    )
    assert res == "otro", f"got {res}"
