"""Extrae el JWT de un login: cookie HttpOnly primero, JSON legado después."""


def tok(r):
    try:
        v = r.cookies.get("cm_token")
        if v:
            return v
    except Exception:
        pass
    try:
        j = r.json() or {}
        return j.get("token") or j.get("access_token") or ""
    except Exception:
        return ""
