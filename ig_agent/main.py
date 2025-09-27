import os
import json
import logging
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# -------------------------------------------------------------
# FastAPI app
# -------------------------------------------------------------
app = FastAPI(title="Avant Webhooks")
logger = logging.getLogger("uvicorn")
logging.getLogger("urllib3").setLevel(logging.WARNING)

# -------------------------------------------------------------
# Environment
# -------------------------------------------------------------
# Accept either env name for the webhook secret
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN") or os.getenv("WEBHOOK_VERIFY_TOKEN", "OEDA901124HQTLZB01")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")  # optional

# WhatsApp (Cloud API)
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v20.0")  # safe default

# Instagram Messaging (via Page) – optional in this app
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
def _normalize_e164(number: str) -> str:
    """Ensure the destination is +E.164. Meta returns wa_id digits only."""
    if not number:
        return number
    number = str(number).strip()
    return number if number.startswith("+") else "+" + number


def send_whatsapp_text(to: str, body: str) -> dict:
    """Send a text message via WhatsApp Cloud API."""
    if not (WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID):
        logger.error("❗Missing WHATSAPP_TOKEN or WHATSAPP_PHONE_NUMBER_ID")
        return {"error": "Missing WhatsApp credentials"}

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": _normalize_e164(to),
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
    logger.info("==> Your service is live 🎉")
    logger.info("==> Available at your primary URL")
    logger.info("==> Routes: %s", ", ".join(routes))
    logger.info(
        "ENV present: VERIFY_TOKEN=%s, WHATSAPP_TOKEN=%s, PHONE_ID=%s",
        bool(VERIFY_TOKEN), bool(WHATSAPP_TOKEN), bool(WHATSAPP_PHONE_NUMBER_ID),
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
# Compliance pages (for Live submission)
# -------------------------------------------------------------
PRIVACY_HTML = """
<h1>Privacy Policy – Avant Media</h1>
<p>We operate WhatsApp chatbots that forward incoming messages (phone number, message content, media metadata, timestamps) from WhatsApp Cloud API to our server to generate automated replies (including via third-party AI providers such as OpenAI). We use this data to provide customer support and automation.</p>
<p><strong>Sharing:</strong> Data flows to Meta (WhatsApp Cloud API) and our processors (Render hosting, logging, and OpenAI for response generation). We do not sell personal data.</p>
<p><strong>Retention:</strong> Webhook logs are retained for troubleshooting and deleted or anonymized on a rolling basis; message content is stored only as needed to provide the service.</p>
<p><strong>Security:</strong> Transport is HTTPS; secrets are stored as environment variables.</p>
<p><strong>Your rights:</strong> Request access or deletion by emailing <a href=\"mailto:abrahamolvera_a@hotmail.com\">abrahamolvera_a@hotmail.com</a>.</p>
<p><strong>Jurisdiction:</strong> UAE law applies.</p>
"""

DELETION_HTML = """
<h1>Data Deletion</h1>
<p>To delete your data, email <a href=\"mailto:abrahamolvera_a@hotmail.com\">abrahamolvera_a@hotmail.com</a> from the same WhatsApp number and request deletion. We will locate records related to your number and erase them from application logs/storage within 30 days.</p>
"""

TERMS_HTML = """
<h1>Terms of Service – Avant Media</h1>
<p>By messaging our WhatsApp numbers you consent to automated processing to generate replies. Do not send sensitive data. Service is provided \"as-is\".</p>
"""

@app.get("/privacy", response_class=HTMLResponse)
def privacy():
    return HTMLResponse(PRIVACY_HTML)

@app.get("/data-deletion", response_class=HTMLResponse)
def data_deletion():
    return HTMLResponse(DELETION_HTML)

@app.get("/terms", response_class=HTMLResponse)
def terms():
    return HTMLResponse(TERMS_HTML)

# -------------------------------------------------------------
# WhatsApp Webhook (verify + receive)
# -------------------------------------------------------------
@app.get("/webhook")
async def wa_verify(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN and challenge:
        # Return raw text, not JSON
        return HTMLResponse(content=str(challenge), media_type="text/plain")
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
            from_wa = msg.get("from")  # digits only wa_id
            msg_type = msg.get("type")
            if msg_type == "text":
                body = msg.get("text", {}).get("body", "")
                # TODO: replace with GPT call; for now echo
                reply = f"Thanks! You said: {body}"
                send_whatsapp_text(from_wa, reply)
    except Exception as e:
        logger.exception("Failed to process WA message: %s", e)

    return {"status": "ok"}

# -------------------------------------------------------------
# Instagram Webhook (verify + receive) – optional
# -------------------------------------------------------------
@app.get("/ig_webhook")
async def ig_verify(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN and challenge:
        return HTMLResponse(content=str(challenge), media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")

@app.post("/ig_webhook")
async def ig_receive(payload: dict):
    logger.info("📩 IG Incoming event: %s", json.dumps(payload))
    return {"status": "ok"}

# -------------------------------------------------------------
# Optional: simple WhatsApp send test endpoint (POST JSON)
# -------------------------------------------------------------
@app.post("/send_wa_text")
async def send_wa_text_api(item: WhatsAppText):
    return send_whatsapp_text(item.to, item.body)
