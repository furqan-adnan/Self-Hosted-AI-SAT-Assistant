from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def health_check():
    return {"status": "AI SAT Tutor Backend is awake and running!"}
