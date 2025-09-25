import os
import json
import logging
import requests
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel

# -------------------------------------------------------------
# FastAPI app
# -------------------------------------------------------------
app = FastAPI(title="Avant Webhooks")
logger = logging.getLogger("uvicorn")

# -------------------------------------------------------------
# Environment
# -------------------------------------------------------------
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "OEDA901124HQTLZB01")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")  # optional

# WhatsApp (Cloud API)
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")

# Instagram Messaging (via Page)
IG_PAGE_ID = os.getenv("IG_PAGE_ID", "")
IG_PAGE_ACCESS_TOKEN = os.getenv("IG_PAGE_ACCESS_TOKEN", "")

# -------------------------------------------------------------
# Models
# -------------------------------------------------------------
class WhatsAppText(BaseModel):
    to: str
    body: str

# -------------------------------------------------------------
# Utilities
# -------------------------------------------------------------

def send_whatsapp_text(to: str, body: str) -> dict:
    """Send a text message via WhatsApp Cloud API."""
    if not (WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID):
        logger.error("❗Missing WHATSAPP_TOKEN or WHATSAPP_PHONE_NUMBER_ID")
        return {"error": "Missing WhatsApp credentials"}

    url = (
        f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    )
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": body},
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    try:
        data = resp.json()
    except Exception:
        data = {"text": resp.text}
    status = resp.status_code
    level = logger.info if status < 300 else logger.error
    level("➡️ send_whatsapp_text: %s %s", status, json.dumps(data))
    return data

# -------------------------------------------------------------
# Debug helpers (safe to keep; helpful in Render)
# -------------------------------------------------------------
@app.on_event("startup")
async def _print_routes_and_env():
    routes = [getattr(r, "path", str(r)) for r in app.router.routes]
    logger.info("DEBUG :: ROUTES = %s", routes)
    logger.info(
        "DEBUG :: VERIFY_TOKEN set:%s len:%d | IG_PAGE_ID set:%s | IG_TOKEN set:%s len:%d | WA creds:%s",
        "yes" if VERIFY_TOKEN else "no",
        len(VERIFY_TOKEN),
        "yes" if IG_PAGE_ID else "no",
        "yes" if IG_PAGE_ACCESS_TOKEN else "no",
        len(IG_PAGE_ACCESS_TOKEN),
        "yes" if (WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID) else "no",
    )

@app.middleware("http")
async def _log_request_path(request: Request, call_next):
    logger.info("DEBUG :: %s %s", request.method, request.url.path)
    return await call_next(request)

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/routes")
def list_routes():
    return [getattr(r, "path", str(r)) for r in app.router.routes]

# -------------------------------------------------------------
# WhatsApp Webhook (verify + receive)
# -------------------------------------------------------------
@app.get("/webhook")
async def wa_verify(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN and challenge:
        return int(challenge)
    raise HTTPException(status_code=404, detail="Not Found")

@app.post("/webhook")
async def wa_receive(payload: dict):
    logger.info("📩 WA Incoming event: %s", json.dumps(payload))

    try:
        entry = payload.get("entry", [])[0]
        change = entry.get("changes", [])[0]
        value = change.get("value", {})
        messages = value.get("messages")
        if messages:
            msg = messages[0]
            from_wa = msg.get("from")
            msg_type = msg.get("type")
            if msg_type == "text":
                body = msg.get("text", {}).get("body", "")
                # Simple echo/ack
                reply = f"Thanks! You said: {body}"
                send_whatsapp_text(from_wa, reply)
    except Exception as e:
        logger.exception("Failed to process WA message: %s", e)

    return {"status": "ok"}

# -------------------------------------------------------------
# Instagram Webhook (verify + receive)
# -------------------------------------------------------------
@app.get("/ig_webhook")
async def ig_verify(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN and challenge:
        # Must return the challenge number to verify
        return int(challenge)
    raise HTTPException(status_code=403, detail="Verification failed")

@app.post("/ig_webhook")
async def ig_receive(payload: dict):
    logger.info("📩 IG Incoming event: %s", json.dumps(payload))
    # For now, just 200 OK so Meta considers delivery successful
    return {"status": "ok"}

# -------------------------------------------------------------
# Optional: simple WhatsApp send test endpoint (POST JSON)
# -------------------------------------------------------------
@app.post("/send_wa_text")
async def send_wa_text_api(item: WhatsAppText):
    return send_whatsapp_text(item.to, item.body)
