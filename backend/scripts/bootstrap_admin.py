from __future__ import annotations

import asyncio
import os
import sys

from ..core.database import connect_prisma, disconnect_prisma, prisma
from ..services.auth_service import AuthService


async def main() -> int:
    admin_id = os.getenv("ADMIN_ID", "").strip()
    admin_name = os.getenv("ADMIN_NAME", "").strip()
    admin_password = os.getenv("ADMIN_PASSWORD", "").strip()
    admin_email = os.getenv("ADMIN_EMAIL", "").strip() or None

    if not admin_id or not admin_name or not admin_password:
        print("ADMIN_ID, ADMIN_NAME, and ADMIN_PASSWORD are required for bootstrap admin creation.")
        return 1

    await connect_prisma()
    try:
        service = AuthService(prisma)
        result = await service.create_bootstrap_admin(
            admin_id,
            admin_name,
            admin_password,
            email=admin_email,
            is_super_admin=True,
        )
        print(f"Bootstrap admin created for {result.user_id}")
        return 0
    finally:
        await disconnect_prisma()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
