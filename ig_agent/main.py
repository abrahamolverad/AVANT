import os, json, asyncio
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse
from dotenv import load_dotenv
import httpx

# ── Load envs (Render uses dashboard env; local dev uses .env) ────────────────
load_dotenv()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "OEDA901124HQTLZB01")

# WhatsApp
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
PHONE_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "") or os.getenv("PHONE_ID", "")

# Instagram (Messaging uses a Page)
IG_PAGE_ID = os.getenv("IG_PAGE_ID", "")
IG_PAGE_ACCESS_TOKEN = os.getenv("IG_PAGE_ACCESS_TOKEN", "")

# OpenAI (optional, for GPT replies)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ── HTTP client ───────────────────────────────────────────────────────────────
client = httpx.AsyncClient(timeout=30.0)

app = FastAPI(title="Avant Webhook", version="1.0")


# ── Healthcheck ───────────────────────────────────────────────────────────────
@app.get("/healthz")
async def healthz():
    return {"ok": True}


# ── Shared: tiny GPT helper (optional) ────────────────────────────────────────
async def generate_reply(user_text: str) -> str:
    """
    Uses OpenAI GPT if OPENAI_API_KEY present; otherwise echo.
    """
    if not OPENAI_API_KEY:
        return f"You said: {user_text}"

    try:
        # Lazy import to avoid hard dependency if not used
        from openai import OpenAI
        ai = OpenAI(api_key=OPENAI_API_KEY)
        resp = ai.chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {"role": "system", "content": "You are a concise, friendly WhatsApp/Instagram assistant."},
                {"role": "user", "content": user_text},
            ],
            temperature=0.4,
        )
        msg = resp.choices[0].message["content"]
        return msg.strip() if msg else f"You said: {user_text}"
    except Exception as e:
        print("❗OpenAI error:", e)
        return f"You said: {user_text}"


# ── WhatsApp: VERIFY (GET) ────────────────────────────────────────────────────
@app.get("/webhook")
async def wa_verify(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        try:
            return PlainTextResponse(str(int(challenge)))
        except Exception:
            return PlainTextResponse(challenge)
    return PlainTextResponse("Verification failed", status_code=403)


# ── WhatsApp: RECEIVE (POST) ──────────────────────────────────────────────────
@app.post("/webhook")
async def wa_receive(req: Request):
    data = await req.json()
    print("📩 WA event:", json.dumps(data, indent=2))

    if data.get("object") != "whatsapp_business_account":
        return PlainTextResponse("ignored")

    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                if not messages:
                    continue

                for m in messages:
                    msg_type = m.get("type")
                    from_wa = m.get("from")
                    text_body = None

                    if msg_type == "text":
                        text_body = (m.get("text") or {}).get("body")

                    # You can add image/audio handling here if needed

                    if from_wa and text_body:
                        reply = await generate_reply(text_body)
                        await send_whatsapp_text(from_wa, reply)
    except Exception as e:
        print("❗WA handling error:", e)

    return PlainTextResponse("ok")


async def send_whatsapp_text(to: str, body: str):
    if not (WHATSAPP_TOKEN and PHONE_ID):
        print("❗Missing WHATSAPP_TOKEN or WHATSAPP_PHONE_NUMBER_ID")
        return

    url = f"https://graph.facebook.com/v22.0/{PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body[:4096]},
    }

    try:
        r = await client.post(url, headers=headers, json=payload)
        print("➡️ send_whatsapp_text:", r.status_code, r.text)
    except Exception as e:
        print("❗WA send error:", e)


# ── Instagram: VERIFY (GET) ───────────────────────────────────────────────────
@app.get("/ig_webhook")
async def ig_verify(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        try:
            return PlainTextResponse(str(int(challenge)))
        except Exception:
            return PlainTextResponse(challenge)
    return PlainTextResponse("Verification failed", status_code=403)


# ── Instagram: RECEIVE (POST) ─────────────────────────────────────────────────
@app.post("/ig_webhook")
async def ig_receive(req: Request):
    data = await req.json()
    print("📩 IG event:", json.dumps(data, indent=2))

    # Instagram messages can arrive with object 'instagram' (Webhooks for Instagram)
    # or via Messenger-style 'page' for IG messaging. Handle both shapes.
    obj = data.get("object")
    try:
        if obj in ("instagram", "page"):
            for entry in data.get("entry", []):
                # Messenger-style "messaging" array (common for IG DMs)
                for m in entry.get("messaging", []):
                    sender_id = (m.get("sender") or {}).get("id")
                    message = m.get("message") or {}
                    text = message.get("text")
                    if sender_id and text:
                        reply = await generate_reply(text)
                        await ig_send_text(sender_id, reply)

                # Instagram webhooks can also come as "changes"
                for ch in entry.get("changes", []):
                    value = ch.get("value", {})
                    msgs = value.get("messages", [])
                    for vmsg in msgs:
                        sender_id = (vmsg.get("from") or {}).get("id") or vmsg.get("from")
                        text = (vmsg.get("text") or {}).get("body") or vmsg.get("message")
                        if sender_id and text:
                            reply = await generate_reply(text)
                            await ig_send_text(sender_id, reply)
    except Exception as e:
        print("❗IG handling error:", e)

    return PlainTextResponse("ok")


async def ig_send_text(psid: str, body: str):
    if not (IG_PAGE_ID and IG_PAGE_ACCESS_TOKEN):
        print("❗Missing IG_PAGE_ID or IG_PAGE_ACCESS_TOKEN")
        return

    url = f"https://graph.facebook.com/v19.0/{IG_PAGE_ID}/messages"
    params = {"access_token": IG_PAGE_ACCESS_TOKEN}
    payload = {
        "recipient": {"id": psid},
        "message": {"text": body[:1000]},
        "messaging_type": "RESPONSE",
    }

    try:
        r = await client.post(url, params=params, json=payload)
        print("➡️ ig_send_text:", r.status_code, r.text)
    except Exception as e:
        print("❗IG send error:", e)


# ── Graceful shutdown: close HTTPX client ─────────────────────────────────────
@app.on_event("shutdown")
async def _shutdown():
    await client.aclose()
