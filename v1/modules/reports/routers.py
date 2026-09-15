from fastapi import APIRouter, BackgroundTasks, HTTPException
from core.constants import ALLOWED_RELATORIES
from .service import run_export, export_lock
from .schemas import ReportSchema

router = APIRouter()

@router.post("/{relatory}", response_model=ReportSchema)
def request_export(relatory: str, background_tasks: BackgroundTasks):
    if relatory not in ALLOWED_RELATORIES:
        raise HTTPException(status_code=400, detail="Relatory not supported")
    
    if export_lock.locked():
        raise HTTPException(status_code=409, detail="Another export is already running")
    
    background_tasks.add_task(run_export, relatory)
    return {"status": "processing", "relatory" : relatory}