from fastapi import FastAPI, Request
import redis
import json
import os

app = FastAPI()

# Redis connection config from Railway-provided environment
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=int(os.getenv("REDIS_DB", 0)),
    password=os.getenv("REDIS_PASSWORD", None),
    decode_responses=True
)

TTL_SECONDS = 7200  # 2 hours

@app.post("/buffer")
async def save_message(request: Request, user_id: str):
    data = await request.json()
    message = data.get("message")
    last_update = data.get("last_update")

    if not message:
        return {"error": "Message is required."}

    # Push new message to the end of the list
    redis_client.rpush(f"buffer:{user_id}:messages", message)

    # Keep only the last 3 messages
    redis_client.ltrim(f"buffer:{user_id}:messages", -3, -1)

    # Set expiration
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
