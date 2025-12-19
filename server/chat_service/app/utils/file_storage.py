import os
import uuid
from pathlib import Path

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(exist_ok=True)

def save_upload_file(upload_file, prefix: str = ""):
    file_ext = upload_file.filename.split(".")[-1]
    filename = f"{prefix}{uuid.uuid4()}.{file_ext}"
    file_path = UPLOAD_DIR / filename
    with open(file_path, "wb") as f:
        f.write(upload_file.file.read())
    return f"/files/{filename}"