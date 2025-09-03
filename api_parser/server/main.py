from fastapi import FastAPI, Request
from redis import asyncio as aioredis
from contextlib import asynccontextmanager
import json
from os import getenv
from dotenv import load_dotenv
load_dotenv()

redis = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis
    redis = await aioredis.from_url(f"redis://:{getenv('REDIS_PASSWORD')}@redis:6379")
    try:
        yield
    finally:
        await redis.close()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def webhook_handler(request: Request):
    data = await request.json()
    await redis.xadd({"data": json.dumps(data)})
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
