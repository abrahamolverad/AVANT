import os
from fastapi import FastAPI, Request, HTTPException

app = FastAPI(title="Studio Agents API")

@app.get("/healthz")
def healthz():
    return {"ok": True, "env": os.getenv("ENV", "dev")}

@app.get("/webhooks/whatsapp")
def wa_verify(hub_mode: str | None = None, hub_challenge: str | None = None, hub_verify_token: str | None = None):
    verify = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
    if not verify or hub_verify_token != verify:
        raise HTTPException(status_code=403, detail="bad verify token")
    return int(hub_challenge or "0")

@app.post("/webhooks/whatsapp")
async def wa_receive(req: Request):
    payload = await req.json()
    return {"received": True}

@app.post("/webhooks/instagram")
async def ig_receive(req: Request):
    payload = await req.json()
    return {"received": True}

@app.post("/webhooks/calendly")
async def calendly_receive(req: Request):
    payload = await req.json()
    return {"ok": True}
