"""Run one Gemini-web (gemini.google.com) chat call on a GitHub runner. Called by gemini-web.yml.
argv: prompt_file web_model level out_file. Cookies come from the GEMINI_WEB_COOKIES secret (JSON)."""
import asyncio, json, os, sys, traceback
from gemini_webapi import GeminiClient
from gemini_webapi.client import REQ_OVERRIDES
pf, web_model, level, outf = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
CANON = {6: "gemini-flash-lite", 1: "gemini-flash", 3: "gemini-pro", 8: "gemini-argon"}
def done(text, fail=None):
    with open(outf, "w") as f:
        f.write(text if not fail else f"##GWEB_FAIL## {fail}\n")
    return 0 if not fail else 3
async def main():
    raw = os.environ.get("GEMINI_WEB_COOKIES", "").strip()
    if not raw: return done("", "secret GEMINI_WEB_COOKIES missing")
    try: ck = json.loads(raw)
    except Exception: return done("", "secret GEMINI_WEB_COOKIES is not valid JSON")
    if isinstance(ck, list): ck = {c.get("name"): c.get("value") for c in ck if isinstance(c, dict)}
    if not ck.get("__Secure-1PSID"): return done("", "cookie __Secure-1PSID missing")
    c = GeminiClient(ck["__Secure-1PSID"], ck.get("__Secure-1PSIDTS"))
    for k, v in ck.items():
        if k not in ("__Secure-1PSID", "__Secure-1PSIDTS") and isinstance(v, str) and v:
            try: c._cookies.set(k, v, domain=".google.com", secure=True)
            except Exception: pass
    try: await c.init(timeout=1500, auto_refresh=False)
    except Exception as e: return done("", f"init {type(e).__name__}: {str(e)[:200]}")
    alias = {CANON.get(m.model_number, m.model_name): m.model_name for m in (c.list_models() or []) if m.is_available}
    if len(alias) <= 1: return done("", "signed_out (cookies expired)")
    if web_model not in alias: return done("", f"model {web_model} not available on this account ({sorted(alias)})")
    REQ_OVERRIDES.set({"inner": {80: level}, "think": level})
    out = []
    try:
        async for ch in c.generate_content_stream(open(pf).read(), model=alias[web_model], extended_thinking=(level != 1)):
            if ch.text_delta: out.append(ch.text_delta)
    except Exception as e:
        return done("", f"{type(e).__name__}: {str(e)[:200]}")
    finally:
        try: await c.close()
        except Exception: pass
    text = "".join(out).strip()
    return done(text) if text else done("", "empty answer")
sys.exit(asyncio.run(main()))
