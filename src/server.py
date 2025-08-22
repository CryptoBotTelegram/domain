from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.presentation.server.routers.webhook import router as webhook_router
from os import getenv
from dotenv import load_dotenv

load_dotenv()

server = FastAPI()

server.include_router(webhook_router)

if getenv("ALLOW_ALL_ORIGINS") == "0":
    origins = [
        "http://localhost",
    ]
else:
    origins = ["*"]

server.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)