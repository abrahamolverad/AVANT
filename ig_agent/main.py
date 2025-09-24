import os, json, urllib.request, requests
from fastapi import FastAPI, Request, Response
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "MY_SECRET_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-5-nano"  # good balance of cost/quality

print("PHONE_ID:", PHONE_ID or "missing")
print("WHATSAPP_TOKEN:", "present" if WHATSAPP_TOKEN else "missing")
print("OPENAI_API_KEY:", "present" if OPENAI_API_KEY else "missing")

# ---------- WhatsApp helpers ----------
def send_whatsapp_text(to: str, body: str):
    if not (WHATSAPP_TOKEN and PHONE_ID):
        print("❗Missing WHATSAPP_TOKEN or WHATSAPP_PHONE_NUMBER_ID")
        return
    url = f"https://graph.facebook.com/v22.0/{PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body[:4096]},  # WA limit
    }
    r = requests.post(url, json=payload, headers=headers, timeout=30)
    print("➡️ send_whatsapp_text:", r.status_code, r.text)

# ---------- AI helper ----------
def ai_reply(user_text: str) -> str:
    if not OPENAI_API_KEY:
        return f"(dev) You said: {user_text}"
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful WhatsApp assistant. Be concise, friendly, and avoid walls of text."},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.5,
        "max_tokens": 350,
    }
    req = urllib.request.Request(
        OPENAI_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("❗OpenAI error:", e)
        return f"(fallback) You said: {user_text}"

# ---------- Webhook endpoints ----------
@app.get("/webhook")
async def verify_webhook(request: Request):
    p = request.query_params
    if p.get("hub.mode") == "subscribe" and p.get("hub.verify_token") == VERIFY_TOKEN and p.get("hub.challenge"):
        return Response(content=str(p["hub.challenge"]), media_type="text/plain")
    return Response(content="Verification failed", status_code=403)

@app.post("/webhook")
async def receive_webhook(req: Request):
    body = await req.json()
    print("📩 Incoming event:", body)

    try:
        entry = body.get("entry", [])[0]
        change = entry.get("changes", [])[0].get("value", {})
        # Message events
        for msg in change.get("messages", []):
            wa_from = msg.get("from")
            msg_type = msg.get("type")
            if msg_type == "text":
                user_text = (msg.get("text") or {}).get("body") or ""
                reply = ai_reply(user_text)
                send_whatsapp_text(to=wa_from, body=reply)
            else:
                # Optional: handle images, audio, locations, buttons, etc.
                send_whatsapp_text(to=wa_from, body="I can read text for now. Send me a message 🙂")

        # Status updates (sent/delivered/read) are in change.get("statuses", [])
    except Exception as e:
        print("❗Handler error:", e)

    return {"status": "ok"}
