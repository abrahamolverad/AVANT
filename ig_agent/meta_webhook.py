@'
import os, requests
from fastapi import FastAPI, Request
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "MY_SECRET_TOKEN")
WAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

@app.get("/webhook")
async def verify_webhook(request: Request):
    params = dict(request.query_params)
    if params.get("hub.verify_token") == VERIFY_TOKEN:
        return int(params.get("hub.challenge", "0"))
    return "Verification failed"

@app.post("/webhook")
async def receive_webhook(req: Request):
    data = await req.json()
    print("📩 Incoming:", data)

    # Minimal WhatsApp message handler (Cloud API structure)
    try:
        entry = data["entry"][0]
        change = entry["changes"][0]["value"]
        if "messages" in change:
            msg = change["messages"][0]
            from_wa = msg["from"]               # sender phone
            # simple echo
            text = msg.get("text", {}).get("body", "Hello!")
            send_text(from_wa, f"You said: {text}")
    except Exception as e:
        print("Handler error:", e)

    return "ok"

def send_text(to, body):
    url = f"https://graph.facebook.com/v22.0/{PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {WAPP_TOKEN}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body}
    }
    r = requests.post(url, json=payload, headers=headers, timeout=30)
    print("➡️ send_text status:", r.status_code, r.text)
'@ | Set-Content -Encoding utf8 main.py
