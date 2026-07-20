import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

import asyncio
from prisma import Prisma

async def main():
    print("Starting prisma...")
    prisma = Prisma()
    await prisma.connect()
    print("Connected.")
    doctor = await prisma.doctor.find_first()
    print(doctor)
    await prisma.disconnect()
    print("Done.")

if __name__ == '__main__':
    asyncio.run(main())
