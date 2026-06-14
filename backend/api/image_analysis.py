"""Image analysis endpoint with vision provider selection.

Usage:
    POST /api/images/analyze
    Body: multipart/form-data with image file
    Headers: Authorization: Bearer <token>

    POST /api/images/analyze/base64
    Body: { "image_base64": "<base64 string>", "prompt": "optional prompt" }
    Headers: Authorization: Bearer <token>

Vision provider is controlled by VISION_ENDPOINT:
    gemini  → Gemini via OpenAI-compatible vision API
    imagga  → Imagga REST API (tagging / categorization)
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field

from ..core.config import settings
from ..core.security import CurrentUser, get_current_user
from ..ai.core_services.llm_client import (
    _normalize_text,
    get_llm_client,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/images", tags=["images"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ImageAnalysisRequest(BaseModel):
    """JSON request for base64 image analysis."""
    model_config = ConfigDict(extra="forbid")

    image_base64: str = Field(..., min_length=1, description="Base64-encoded image data")
    prompt: str | None = Field(
        default=None,
        description="Optional custom prompt. Defaults to a medical analysis prompt.",
    )
    model: str | None = Field(
        default=None,
        description="Override the vision model to use.",
    )


class ImageAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool = True
    provider: str = Field(..., description="Which provider handled the request (gemini or imagga)")
    model_used: str | None = Field(default=None, description="The model that was used")
    analysis: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured analysis result from the provider.",
    )
    raw_text: str | None = Field(
        default=None,
        description="Raw text response from the provider (if available).",
    )
    error: str | None = Field(default=None, description="Error message if something went wrong.")


# ---------------------------------------------------------------------------
# Default medical analysis prompt
# ---------------------------------------------------------------------------

_MEDICAL_ANALYSIS_PROMPT = """You are a medical image analysis assistant. Analyze the provided medical image carefully and return a JSON object with the following fields:
- "findings": a list of key observations from the image
- "impression": your overall clinical impression
- "recommendations": any follow-up recommendations
- "confidence": a float between 0.0 and 1.0 indicating confidence
- "is_abnormal": boolean, whether you detect anything abnormal

If the image is not a medical image or cannot be analyzed, return:
{"findings": ["Unable to analyze the provided image"], "impression": "Non-medical or unprocessable image", "recommendations": [], "confidence": 0.0, "is_abnormal": false}
"""


# ---------------------------------------------------------------------------
# Helper: read image bytes from UploadFile
# ---------------------------------------------------------------------------

async def _read_upload(file: UploadFile, max_size_mb: int = 20) -> bytes:
    contents = await file.read()
    if len(contents) > max_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {max_size_mb}MB limit.",
        )
    return contents


def _detect_mime(suffix: str) -> str:
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
    }
    return mime_map.get(suffix.lower(), "image/png")


# ---------------------------------------------------------------------------
# Build vision messages for OpenAI-compatible providers
# ---------------------------------------------------------------------------

def _build_vision_messages(
    image_bytes: bytes,
    mime_type: str,
    prompt: str | None = None,
) -> list[dict[str, Any]]:
    """Build a messages list suitable for any OpenAI-compatible vision API."""
    b64_data = base64.b64encode(image_bytes).decode("ascii")
    effective_prompt = prompt or _MEDICAL_ANALYSIS_PROMPT

    user_content: list[dict[str, Any]] = [
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{b64_data}",
                "detail": "high",
            },
        },
        {"type": "text", "text": "Return valid JSON only."},
    ]

    return [
        {"role": "system", "content": effective_prompt},
        {"role": "user", "content": user_content},
    ]


# ---------------------------------------------------------------------------
# Vision provider: Gemini (OpenAI-compatible vision API)
# ---------------------------------------------------------------------------

async def _analyze_with_gemini_vision(
    image_bytes: bytes,
    mime_type: str,
    prompt: str | None = None,
    model: str | None = None,
) -> ImageAnalysisResponse:
    """Analyze image using Gemini via its OpenAI-compatible vision API."""
    from openai import AsyncOpenAI

    gemini_api_key = str(settings.gemini_api_key or "").strip()
    gemini_base_url = str(settings.gemini_base_url or "").strip() or None
    effective_model = model or str(settings.gemini_model or "").strip() or "gemini-2.0-flash"

    if not gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set — required for vision (VISION_ENDPOINT=gemini)")

    client = AsyncOpenAI(api_key=gemini_api_key, base_url=gemini_base_url)
    messages = _build_vision_messages(image_bytes, mime_type, prompt)

    response = await client.chat.completions.create(
        model=effective_model,
        messages=messages,
        temperature=0.2,
        max_tokens=2048,
        response_format={"type": "json_object"},
    )
    choice = response.choices[0] if response.choices else None
    content = getattr(getattr(choice, "message", None), "content", "") if choice else ""
    if isinstance(content, list):
        content = "".join(
            str(item.get("text") or item.get("content") or "")
            for item in content if isinstance(item, dict)
        )
    raw_text = _normalize_text(str(content or ""))

    # Try to parse JSON
    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            return ImageAnalysisResponse(
                provider="gemini",
                model_used=effective_model,
                analysis=parsed,
                raw_text=raw_text,
            )
    except (json.JSONDecodeError, ValueError):
        pass

    # If we got text but it wasn't valid JSON, return it anyway
    if raw_text:
        return ImageAnalysisResponse(
            provider="gemini",
            model_used=effective_model,
            analysis={"raw_response": raw_text},
            raw_text=raw_text,
        )

    raise RuntimeError("Gemini vision returned empty response")


# ---------------------------------------------------------------------------
# Vision provider: Imagga (REST API)
# ---------------------------------------------------------------------------

async def _analyze_with_imagga(image_bytes: bytes) -> ImageAnalysisResponse:
    """Image analysis using Imagga REST API."""
    import httpx

    api_key = str(settings.imgaga_api_key or "").strip()
    api_url = str(settings.imgaga_api_url or "https://api.imagga.com/v2").strip().rstrip("/")

    if not api_key:
        raise RuntimeError("IMGAGA_API_KEY is not configured. Cannot use Imagga (VISION_ENDPOINT=imagga).")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Upload image
        files = {"image": ("image.jpg", image_bytes, "image/jpeg")}
        upload_resp = await client.post(
            f"{api_url}/uploads",
            auth=(api_key, api_key),
            files=files,
        )
        upload_resp.raise_for_status()
        upload_data = upload_resp.json()
        upload_id = (upload_data.get("result", {}) or {}).get("upload_id")

        # Tagging
        if not upload_id:
            raise RuntimeError("Imagga upload did not return an upload_id")

        tags_resp = await client.get(
            f"{api_url}/tags",
            auth=(api_key, api_key),
            params={"image_upload_id": upload_id, "limit": 20},
        )
        tags_resp.raise_for_status()
        tags_data = tags_resp.json()
        tags_result = tags_data.get("result", {})
        tags = tags_result.get("tags", [])

        # Categories
        categories_resp = await client.get(
            f"{api_url}/categories",
            auth=(api_key, api_key),
            params={"image_upload_id": upload_id},
        )
        categories_resp.raise_for_status()
        categories_data = categories_resp.json()
        categories_result = categories_data.get("result", {})
        categories = categories_result.get("categories", [])

        analysis: dict[str, Any] = {
            "tags": [
                {"tag": t.get("tag", {}).get("en", ""), "confidence": t.get("confidence", 0.0)}
                for t in tags if t.get("tag", {}).get("en")
            ],
            "categories": [
                {"name": c.get("name", {}).get("en", ""), "confidence": c.get("confidence", 0.0)}
                for c in categories if c.get("name", {}).get("en")
            ],
        }

        return ImageAnalysisResponse(
            provider="imagga",
            model_used="imagga-v2",
            analysis=analysis,
            raw_text=json.dumps(analysis),
        )


# ---------------------------------------------------------------------------
# Main analysis orchestrator — uses VISION_ENDPOINT switch
# ---------------------------------------------------------------------------

async def _analyze_image(
    image_bytes: bytes,
    mime_type: str = "image/png",
    prompt: str | None = None,
    model: str | None = None,
) -> ImageAnalysisResponse:
    """Analyze image using the configured vision endpoint."""
    endpoint = str(settings.vision_endpoint or "gemini").strip().lower()

    if endpoint == "imagga":
        try:
            return await _analyze_with_imagga(image_bytes)
        except Exception as exc:
            return ImageAnalysisResponse(
                success=False,
                provider="imagga",
                error=f"Imagga analysis failed: {exc}",
            )

    # Default: gemini
    try:
        return await _analyze_with_gemini_vision(
            image_bytes,
            mime_type,
            prompt=prompt,
            model=model,
        )
    except Exception as exc:
        logger.warning("Gemini vision failed: %s", exc)
        return ImageAnalysisResponse(
            success=False,
            provider="none",
            error=f"Vision analysis failed: {exc}",
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/analyze", response_model=ImageAnalysisResponse)
async def analyze_image_upload(
    file: UploadFile = File(..., description="Image file to analyze"),
    prompt: str | None = None,
    model: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
) -> ImageAnalysisResponse:
    """Upload an image file for AI-powered analysis.

    Uses the configured vision endpoint (controlled by VISION_ENDPOINT).
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be an image.",
        )

    image_bytes = await _read_upload(file)
    mime_type = file.content_type

    return await _analyze_image(image_bytes, mime_type=mime_type, prompt=prompt, model=model)


@router.post("/analyze/base64", response_model=ImageAnalysisResponse)
async def analyze_image_base64(
    request: ImageAnalysisRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> ImageAnalysisResponse:
    """Analyze a base64-encoded image.

    The image_base64 field should contain the raw base64 data (with or without
    the 'data:image/...;base64,' prefix).
    """
    raw = request.image_base64.strip()

    # Strip data URI prefix if present
    if raw.startswith("data:"):
        # Extract mime type and base64 data
        try:
            header, _, b64_data = raw.partition(",")
            mime_type = header.replace("data:", "").split(";")[0] or "image/png"
        except Exception:
            mime_type = "image/png"
            b64_data = raw
    else:
        mime_type = "image/png"
        b64_data = raw

    try:
        image_bytes = base64.b64decode(b64_data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid base64 data: {exc}",
        )

    return await _analyze_image(
        image_bytes,
        mime_type=mime_type,
        prompt=request.prompt,
        model=request.model,
    )


@router.get("/providers", response_model=dict[str, Any])
async def list_image_providers(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """List available image analysis providers and their status."""
    endpoint = str(settings.vision_endpoint or "gemini").strip().lower()
    imagga_key = str(settings.imgaga_api_key or "").strip()
    gemini_key = str(settings.gemini_api_key or "").strip()

    return {
        "vision_endpoint": endpoint,
        "gemini_configured": bool(gemini_key),
        "imagga_configured": bool(imagga_key),
        "available_endpoints": ["gemini", "imagga"],
    }