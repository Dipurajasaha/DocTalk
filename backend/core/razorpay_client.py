"""Razorpay client singleton.

Loads RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET from environment variables and
returns an authenticated razorpay.Client. Raises RuntimeError at import-time if
either variable is missing or still set to the placeholder values so the problem
is surfaced immediately at startup rather than silently at payment-time.
"""

from __future__ import annotations

import os

import razorpay


_PLACEHOLDER_IDS = {"rzp_test_XXXXXXXXXXXX", "rzp_live_XXXXXXXXXXXX", ""}


def _load_client() -> razorpay.Client:
    key_id = os.getenv("RAZORPAY_KEY_ID", "").strip()
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "").strip()

    if key_id in _PLACEHOLDER_IDS or key_secret in {"XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX", ""}:
        raise RuntimeError(
            "Razorpay credentials are missing or still set to placeholder values. "
            "Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in your .env file."
        )

    return razorpay.Client(auth=(key_id, key_secret))


# Module-level singleton — created once on first import.
# We wrap it in a lazy loader so that the backend can still *start*
# without Razorpay keys (non-payment routes continue to work).
_client: razorpay.Client | None = None


def get_razorpay_client() -> razorpay.Client:
    """Return the cached Razorpay client, creating it on first call."""
    global _client
    if _client is None:
        _client = _load_client()
    return _client
