from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_automation():
    return {"status": "automation active"}
