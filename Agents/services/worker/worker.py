import os
from redis import Redis
from rq import Queue

redis = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
q = Queue("events", connection=redis)

def process_event(event: dict):
    print("Processing:", event)
    return {"status": "ok", "event": event}

def enqueue_event(event: dict):
    return q.enqueue(process_event, event)
