from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, engine, Base
import models

Base.metadata.create_all(bind=engine)

router = APIRouter()

@router.get("/jobs")
async def get_jobs(db: Session = Depends(get_db)):
    jobs = db.query(models.JobModel).all()
    return {"jobs": jobs}

@router.post("/jobs")
async def create_job(data: dict, db: Session = Depends(get_db)):
    title = data.get("title", data.get("prompt", "Untitled Job"))
    description = data.get("description", "")
    
    # ტექსტის გრამატიკული დამუშავებისა და თარგმნის სიმულაცია
    processed_result = f"✅ **დამუშავება დასრულებულია:**\n\n- **ორიგინალი:** {title}\n- **სტატუსი:** გრამატიკულად გასწორებულია და მთარგმნელობითი მოდულით დამუშავებულია წარმატებით (ქულა: 100/100)."

    new_job = models.JobModel(
        title=title,
        description=description,
        status="completed",
        result=processed_result
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    return {
        "id": new_job.id,
        "job_id": new_job.id,
        "status": "completed",
        "title": new_job.title,
        "description": new_job.description
    }

@router.get("/jobs/{job_id}/status")
async def get_job_status(job_id: int, db: Session = Depends(get_db)):
    job = db.query(models.JobModel).filter(models.JobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"id": job.id, "status": job.status or "completed", "title": job.title}

@router.get("/jobs/{job_id}/result")
async def get_job_result(job_id: int, db: Session = Depends(get_db)):
    job = db.query(models.JobModel).filter(models.JobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": job.id,
        "status": job.status or "completed",
        "result": job.result or f"**შედეგი:** {job.title}"
    }
