from fastapi import APIRouter, Request

router = APIRouter(prefix="/webhook")

@router.post("/")
async def webhook(request: Request):
    pass