from __future__ import annotations

from ..core.database import prisma
from .file_service import AssetConfig, MedicalFileService


PRESCRIPTION_CONFIG = AssetConfig(
    model_name="prescription",
    storage_folder="prescriptions",
    api_prefix="/api/prescriptions",
    file_type="prescription",
    allowed_mime_types=frozenset({"application/pdf", "image/jpeg", "image/png"}),
    allowed_extensions=frozenset({".pdf", ".jpg", ".jpeg", ".png"}),
)


class PrescriptionService(MedicalFileService):
    def __init__(self, client=prisma) -> None:
        super().__init__(PRESCRIPTION_CONFIG, client=client)
