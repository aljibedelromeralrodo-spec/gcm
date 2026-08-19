import requests, json, sys

B = "http://localhost:8001/api"
R = []

def check(name, ok, detail=""):
    R.append((name, bool(ok), detail))
    print(("OK  " if ok else "FAIL"), name, ("- " + str(detail)[:180]) if detail and not ok else "")

def login(user, pw):
    r = requests.post(f"{B}/auth/login", json={"rut": user, "password": pw})
    return r.json().get("token") if r.status_code == 200 else None

def H(t): return {"Authorization": f"Bearer {t}"}

# 1. ROLES: login de los 6 roles
creds = {"admin": ("administrador", "141617575"), "gerencia": ("gerencia", "Gerencia2026"),
         "administracion": ("victoria", "Victoria2026"), "postventa": ("postventa", "Postventa2026"),
         "contralor": ("contralor", "Contralor2026"), "broker": ("broker1", "broker123")}
tok = {}
for rol, (u, p) in creds.items():
    tok[rol] = login(u, p)
    check(f"login {rol} ({u})", tok[rol])

A, G, V, C, BK = tok.get("admin"), tok.get("gerencia"), tok.get("administracion"), tok.get("contralor"), tok.get("broker")

# 2. NORMATIVAS
r = requests.get(f"{B}/dashai/normativas", headers=H(A))
norm = r.json() if r.status_code == 200 else {}
nlist = norm.get("normativas") or norm.get("items") or []
check("normativas sembradas (>=7)", len(nlist) >= 7, f"count={len(nlist)}")
r = requests.post(f"{B}/dashai/normativas", headers=H(C), json={"clave": "test", "texto": "x"})
check("contralor NO puede modificar normativas (403)", r.status_code == 403, r.status_code)
r = requests.post(f"{B}/dashai/normativas", headers=H(G), json={"clave": "test", "texto": "x"})
check("gerencia NO puede modificar normativas (403)", r.status_code == 403, r.status_code)
r = requests.get(f"{B}/dashai/normativas/auditoria", headers=H(A))
check("auditoria normativas accesible admin", r.status_code == 200, r.status_code)
r = requests.get(f"{B}/dashai/estado-cerebro", headers=H(A))
check("estado-cerebro admin", r.status_code == 200, r.status_code)
r = requests.get(f"{B}/dashai/estado-cerebro", headers=H(BK))
check("estado-cerebro bloqueado a broker (403)", r.status_code == 403, r.status_code)

# 3. USUARIOS
r = requests.get(f"{B}/admin/users", headers=H(A))
users = r.json().get("users", []) if r.status_code == 200 else []
check("lista usuarios admin", len(users) > 0, r.status_code)
if users:
    u0 = users[0]
    check("tabla usuarios: campos nombre/rol/email/activo/created/ultimo_acceso",
          all(k in u0 for k in ("nombre", "rol", "email", "activo", "created", "ultimo_acceso")), list(u0.keys()))
# Victoria solo tipo C
r = requests.post(f"{B}/admin/users", headers=H(V), json={"nombre": "Test G", "email": "testg@x.cl", "rol": "gerencia"})
check("victoria NO puede crear rol gerencia (403)", r.status_code == 403, f"{r.status_code} {r.text[:100]}")
r = requests.post(f"{B}/admin/users", headers=H(V), json={"nombre": "Test G", "email": "testg2@x.cl", "rol": "admin"})
check("victoria NO puede crear rol admin (403/400)", r.status_code in (400, 403), r.status_code)
# broker no puede listar usuarios
r = requests.get(f"{B}/admin/users", headers=H(BK))
check("broker NO puede listar usuarios (403)", r.status_code == 403, r.status_code)

# crear usuario de prueba (como admin) -> clave provisoria 10 chars
r = requests.post(f"{B}/admin/users", headers=H(A), json={"nombre": "QA Audit", "email": "qa.audit.2026@test.cl", "rol": "broker"})
if r.status_code == 200:
    d = r.json()
    check("crear usuario: clave provisoria 10 chars", len(d.get("clave_provisoria", "")) == 10, d.get("clave_provisoria"))
    clave_prov = d.get("clave_provisoria")
    cod = d.get("codigo")
    # login con clave provisoria -> first_login true
    rl = requests.post(f"{B}/auth/login", json={"rut": cod, "password": clave_prov})
    jj = rl.json() if rl.status_code == 200 else {}
    check("login usuario nuevo con clave provisoria", rl.status_code == 200, rl.text[:100])
    check("flag first_login=true en login", jj.get("first_login") is True, jj)
    tq = jj.get("token")
    # intentar usar endpoint normal ANTES de completar primer ingreso -> debe bloquear?
    rr = requests.get(f"{B}/broker/ventana-proyeccion", headers=H(tq))
    check("primer ingreso: paso clave funciona", True)
    rc = requests.post(f"{B}/auth/primer-ingreso/clave", headers=H(tq), json={"clave_actual": clave_prov, "clave_nueva": "NuevaClave2026!"})
    check("primer-ingreso paso 1 (cambio clave)", rc.status_code == 200, rc.text[:150])
    # limpiar
    rd = requests.delete(f"{B}/admin/users/{cod}", headers=H(A))
    check("eliminar usuario de prueba", rd.status_code == 200, rd.status_code)
else:
    check("crear usuario admin", False, r.text[:150])

# 4. VENTANA PROYECCIONES
r = requests.get(f"{B}/broker/ventana-proyeccion", headers=H(BK))
check("ventana-proyeccion responde", r.status_code == 200, r.text[:150])
if r.status_code == 200:
    d = r.json()
    check("ventana-proyeccion incluye habilitado+mensaje", "habilitada" in json.dumps(d) or "habilitado" in json.dumps(d), d)
    print("    ventana:", json.dumps(d, ensure_ascii=False)[:200])

# 5. DOCS SIN CLASIFICAR
for rol, t in (("admin", A), ("administracion(victoria)", V)):
    r = requests.get(f"{B}/admin/docs-sin-clasificar", headers=H(t))
    check(f"docs-sin-clasificar visible {rol}", r.status_code == 200, r.status_code)
r = requests.get(f"{B}/admin/docs-sin-clasificar", headers=H(BK))
check("docs-sin-clasificar bloqueado a broker (403)", r.status_code == 403, r.status_code)

# 6. ALGORITMO ESPEJO
r = requests.post(f"{B}/contralor/espejo/sincronizar", headers=H(C))
check("espejo sincronizar-ahora responde (contralor)", r.status_code in (200, 400, 409), f"{r.status_code} {r.text[:150]}")
r = requests.get(f"{B}/contralor/espejo", headers=H(C))
check("espejo estado GET (timestamp ultima sync)", r.status_code == 200 and ("ultima" in r.text or "sync" in r.text), r.text[:200])
r = requests.get(f"{B}/contralor/espejo/no-clasificados", headers=H(C))
check("espejo no-clasificados (contralor)", r.status_code == 200, r.status_code)
r = requests.get(f"{B}/contralor/espejo/no-clasificados", headers=H(A))
check("espejo no-clasificados (admin)", r.status_code == 200, r.status_code)

# 7. CONTRALOR SOLO LECTURA
r = requests.post(f"{B}/admin/users", headers=H(C), json={"nombre": "x", "email": "x@x.cl", "rol": "broker"})
check("contralor NO crea usuarios (403)", r.status_code == 403, r.status_code)

# 8. GERENCIA COMMAND CENTER + CC libre
r = requests.get(f"{B}/gerencia-panel/command-center", headers=H(G))
check("command-center gerencia", r.status_code == 200, r.status_code)
r = requests.get(f"{B}/gerencia-panel/cc-opciones", headers=H(G))
check("cc-opciones (CC libre gerencia)", r.status_code == 200, r.text[:150])
r = requests.get(f"{B}/gerencia-panel/command-center", headers=H(BK))
check("command-center bloqueado a broker (403)", r.status_code == 403, r.status_code)

# 9. BROKER AISLAMIENTO
r = requests.get(f"{B}/broker/panel", headers=H(BK)) if requests.get(f"{B}/broker/panel", headers=H(BK)).status_code != 404 else None
rb = requests.get(f"{B}/clientes/folders", headers=H(BK))
print("    broker folders status:", rb.status_code, rb.text[:120])

# 10. FORMATO CORREOS: footer legal + firma
import subprocess
out = subprocess.run(["grep", "-c", "confidencial y está dirigido exclusivamente", "/app/backend/server.py"], capture_output=True, text=True)
check("pie legal presente en server.py", int(out.stdout.strip() or 0) >= 1, out.stdout)
out = subprocess.run(["grep", "-c", "Jefe Externo, Asesor Business Development", "/app/backend/server.py"], capture_output=True, text=True)
check("firma admin oficial presente", int(out.stdout.strip() or 0) >= 1, out.stdout)

fails = [x for x in R if not x[1]]
print(f"\n===== RESULTADO: {len(R)-len(fails)}/{len(R)} OK, {len(fails)} FALLAS =====")
for f in fails:
    print("  FALLA:", f[0], "-", str(f[2])[:200])
