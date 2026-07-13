"""API endpoint for looking up medicine prices using Gemini web search."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..core.security import CurrentUser, get_current_user
from ..services.medicine_price_service import search_medicine_prices

router = APIRouter()


def _require_patient(current_user: CurrentUser) -> None:
    if current_user.role != "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients can access this resource",
        )


@router.post("/medicine-prices")
async def lookup_medicine_prices(
    body: dict,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Look up prices for a list of medicine names using Gemini web search.

    Request body:
    {
        "medicines": ["Medicine A", "Medicine B", ...]
    }

    Returns:
    {
        "results": [
            {
                "medicine_name": "...",
                "purpose": "...",
                "price": "₹XXX",
                "platform_name": "...",
                "source_url": "..."
            },
            ...
        ]
    }
    """
    _require_patient(current_user)

    medicines = body.get("medicines", [])
    if not medicines or not isinstance(medicines, list):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide a non-empty 'medicines' array",
        )

    # Limit to reasonable number
    if len(medicines) > 20:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Maximum 20 medicines per request",
        )

    # Clean medicine names
    medicine_names = [
        str(m).strip() for m in medicines if str(m).strip()
    ]
    if not medicine_names:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide at least one valid medicine name",
        )

    results = await search_medicine_prices(medicine_names)
    return {"results": results}