from __future__ import annotations

from ..core.database import prisma
from .file_service import AssetConfig, MedicalFileService


REPORT_CONFIG = AssetConfig(
    model_name="report",
    storage_folder="reports",
    api_prefix="/api/reports",
    file_type="report",
    allowed_mime_types=frozenset({"application/pdf", "image/jpeg", "image/png"}),
    allowed_extensions=frozenset({".pdf", ".jpg", ".jpeg", ".png"}),
)


class ReportService(MedicalFileService):
    def __init__(self, client=prisma) -> None:
        super().__init__(REPORT_CONFIG, client=client)
