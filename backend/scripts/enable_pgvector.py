"""Enable the pgvector extension on Supabase before the first `prisma db push`.

Usage (from project root):
    python backend/scripts/enable_pgvector.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

from prisma import Prisma  # noqa: E402


async def main() -> None:
    prisma = Prisma()
    await prisma.connect()
    try:
        await prisma.execute_raw("CREATE EXTENSION IF NOT EXISTS vector")
        print("pgvector extension is enabled.")
    finally:
        await prisma.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"Failed to enable pgvector: {exc}", file=sys.stderr)
        sys.exit(1)
