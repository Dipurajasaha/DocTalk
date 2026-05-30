from __future__ import annotations

from ..core.database import prisma
from .file_service import AssetConfig, MedicalFileService


MEDICAL_IMAGE_CONFIG = AssetConfig(
    model_name="medicalimage",
    storage_folder="medical_images",
    api_prefix="/api/medical_images",
    file_type="medical_image",
    allowed_mime_types=frozenset({"image/jpeg", "image/png", "image/webp"}),
    allowed_extensions=frozenset({".jpg", ".jpeg", ".png", ".webp"}),
)


class MedicalImageService(MedicalFileService):
    def __init__(self, client=prisma) -> None:
        super().__init__(MEDICAL_IMAGE_CONFIG, client=client)
