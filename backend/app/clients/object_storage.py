from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from werkzeug.utils import secure_filename


class LocalObjectStorageClient:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def save_resume(self, resume_id: str, file_name: str, file_bytes: bytes) -> str:
        safe_name = secure_filename(file_name) or "resume.bin"
        object_name = f"{uuid4().hex[:8]}_{safe_name}"
        relative_path = Path("resumes") / resume_id / object_name
        target_path = self.root_dir / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(file_bytes)
        return relative_path.as_posix()