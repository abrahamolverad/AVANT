import os, hmac, hashlib, httpx
from fastapi import FastAPI, Request, HTTPException, Response
from dotenv import load_dotenv

load_dotenv()
APP_SECRET = os.getenv("APP_SECRET", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

GRAPH_BASE = "https://graph.facebook.com/v21.0"

app = FastAPI(title="IG DM Agent")

def verify_signature(payload: bytes, signature: str) -> bool:
    # Meta sends X-Hub-Signature-256: sha256=<hexdigest>
    if not signature or not APP_SECRET:
        # Dev mode: skip if you haven't set APP_SECRET
        return True
    try:
        sha_name, sig = signature.split("=")
        mac = hmac.new(APP_SECRET.encode(), msg=payload, digestmod=hashlib.sha256)
        return hmac.compare_digest(mac.hexdigest(), sig)
    except Exception:
        return False

@app.get("/webhook")
async def verify(req: Request):
    # Meta verification handshake: ?hub.mode=subscribe&hub.challenge=1234&hub.verify_token=...
    q = dict(req.query_params)
    if q.get("hub.mode") == "subscribe" and q.get("hub.verify_token") == VERIFY_TOKEN and "hub.challenge" in q:
        return Response(content=q["hub.challenge"], media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")

async def send_ig_message(ig_user_id: str, text: str):
    if not PAGE_ACCESS_TOKEN:
        raise RuntimeError("PAGE_ACCESS_TOKEN missing")
    url = f"{GRAPH_BASE}/me/messages"
    headers = {"Authorization": f"Bearer {PAGE_ACCESS_TOKEN}"}
    payload = {"recipient": {"id": ig_user_id}, "message": {"text": text}}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        return r.json()

async def llm_reply(user_text: str) -> str:
    # Minimal LLM call — keep it short, qualify the lead, invite to book when appropriate
    system = (
        "You are Avant Studio’s assistant for branding, design, and AI websites. "
        "Be concise, warm, and helpful. "
        "Qualify with 2-3 quick questions (industry, timeline, budget range in AED). "
        "Offer a Calendly link only after at least one answer or explicit request."
    )
    if not OPENAI_API_KEY:
        # Fallback if no key set
        return "Thanks for reaching out! Could you share your industry, timeline, and an approximate budget range (AED 5–10k / 10–25k / 25k+)? I’ll tailor a recommendation and next steps."
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={
                    "model": "gpt-4o-mini",
                    "temperature": 0.4,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": f"DM from prospect: {user_text}"},
                    ],
                },
            )
            r.raise_for_status()
            msg = r.json()["choices"][0]["message"]["content"].strip()
            return msg[:900]
    except Exception:
        return "Appreciate your message! Quick 3 to tailor a quote: 1) business type & city, 2) timeline, 3) budget range (AED 5–10k / 10–25k / 25k+)."

@app.post("/webhook")
async def receive(req: Request):
    raw = await req.body()
    if not verify_signature(raw, req.headers.get("x-hub-signature-256", "")):
        raise HTTPException(status_code=403, detail="Bad signature")

    data = await req.json()
    # Instagram uses the Messenger-style envelope (entry.messaging[])
    for entry in data.get("entry", []):
        for evt in entry.get("messaging", []):
            sender_id = (evt.get("sender") or {}).get("id")
            msg = evt.get("message") or {}
            text = msg.get("text")
            if sender_id and text:
                reply = await llm_reply(text)
                await send_ig_message(sender_id, reply)
    return {"status": "ok"}
