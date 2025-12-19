from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from app.utils.file_storage import save_upload_file
from app.core.security import get_current_user
from app.utils.database import get_db
from shared.models.user import User
from fastapi import Depends
from sqlalchemy.orm import Session
router = APIRouter(prefix="/api/files", tags=["Files"])

@router.post("/upload")
def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    max_size = int(os.getenv("MAX_FILE_SIZE", "10485760"))
    if file.size > max_size:
        raise HTTPException(400, "File too large")

    try:
        file_url = save_upload_file(file, prefix="upload_")
        return {"file_url": file_url}
    except Exception as e:
        raise HTTPException(500, f"Upload failed: {str(e)}")

@router.get("/{filename}")
def serve_file(filename: str):
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(file_path)