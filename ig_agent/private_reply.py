import os, httpx, asyncio
from dotenv import load_dotenv
load_dotenv()

PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
GRAPH_BASE = "https://graph.facebook.com/v21.0"

async def send_private_reply(comment_id: str, text: str):
    if not PAGE_ACCESS_TOKEN:
        raise RuntimeError("PAGE_ACCESS_TOKEN missing")
    url = f"{GRAPH_BASE}/{comment_id}/private_replies"
    headers = {"Authorization": f"Bearer {PAGE_ACCESS_TOKEN}"}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(url, headers=headers, data={"message": text})
        r.raise_for_status()
        return r.json()

# Example manual run:
# asyncio.run(send_private_reply("179XXXXXXXXXXXXXXX_YYYY", "Thanks for commenting! Reply YES to get our Real-Estate Brand Kit."))
