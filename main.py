from fastapi import FastAPI, Request
import redis
import json
import os
import time

app = FastAPI()

# Redis connection config from Railway environment
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=int(os.getenv("REDIS_DB", 0)),
    password=os.getenv("REDIS_PASSWORD", None),
    decode_responses=True
)

TTL_SECONDS = 7200  # 2 hours

# ----------------------------------
# SHORT-TERM MEMORY: BUFFER ENDPOINTS
# ----------------------------------

@app.post("/buffer")
async def save_message(request: Request, user_id: str):
    data = await request.json()
    message = data.get("message")
    last_update = data.get("last_update")

    if not message:
        return {"error": "Message is required."}

    # Save message to buffer list
    redis_client.rpush(f"buffer:{user_id}:messages", message)
    redis_client.ltrim(f"buffer:{user_id}:messages", -3, -1)
    redis_client.expire(f"buffer:{user_id}:messages", TTL_SECONDS)

    if last_update:
        redis_client.setex(f"buffer:{user_id}:last_update", TTL_SECONDS, last_update)

    return {"status": "ok"}

@app.get("/buffer")
def get_messages(user_id: str):
    messages = redis_client.lrange(f"buffer:{user_id}:messages", 0, -1)
    last_update = redis_client.get(f"buffer:{user_id}:last_update")

    return {
        "messages": messages,
        "last_update": last_update
    }

# ----------------------------------
# NEW: WAKE-UP REMINDER ENDPOINTS
# ----------------------------------

@app.post("/wake-up")
async def set_wake_up(request: Request):
    data = await request.json()
    user_id = data.get("user_id")
    if not user_id:
        return {"error": "Missing user_id"}

    key = f"wake:{user_id}"
    timestamp = int(time.time())
    redis_client.setex(key, TTL_SECONDS, timestamp)
    return {"status": "ok", "key": key, "timestamp": timestamp}

@app.get("/wake-up/expired")
def get_expired_wakeups():
    now = int(time.time())
    expired = []

    for key in redis_client.scan_iter("wake:*"):
        try:
            timestamp = int(redis_client.get(key) or 0)
            if now - timestamp > TTL_SECONDS:
                user_id = key.split(":")[1]
                expired.append(user_id)
                redis_client.delete(key)
        except Exception as e:
            print(f"Error with key {key}: {e}")
    
    return {"expired_users": expired}
