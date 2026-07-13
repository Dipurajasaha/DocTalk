import asyncio
from core.database import connect_prisma, disconnect_prisma, prisma

async def clear_chats():
    # print("Connecting to the database...")
    await connect_prisma()
    try:
        # Delete all messages first (though cascade would handle it, this is safer and clearer)
        deleted_messages = await prisma.aichatmessage.delete_many()
        # print(f"Deleted {deleted_messages} AI chat messages.")
        
        # Delete all sessions
        deleted_sessions = await prisma.aichatsession.delete_many()
        # print(f"Deleted {deleted_sessions} AI chat sessions.")
        
        # print("Successfully cleared all AI chats from the database.")
    except Exception as e:
        print(f"Error while clearing chats: {e}")
    finally:
        # print("Disconnecting from the database...")
        await disconnect_prisma()

if __name__ == "__main__":
    asyncio.run(clear_chats())
