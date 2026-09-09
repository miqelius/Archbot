from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_copilot_status():
    return {"status": "copilot active"}
