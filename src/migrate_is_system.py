import aiosqlite
import asyncio
from config import DATABASE

async def migrate_is_system():
    """Add is_system column to existing scripts table"""
    print("Migrating scripts table to add is_system column...")

    async with aiosqlite.connect(DATABASE) as db:
        try:
            cursor = await db.execute("PRAGMA table_info(scripts)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

            if 'is_system' not in column_names:
                print("Adding is_system column...")
                await db.execute("ALTER TABLE scripts ADD COLUMN is_system BOOLEAN DEFAULT 0")
                await db.commit()
                print("Migration completed successfully!")
            else:
                print("is_system column already exists!")

        except Exception as e:
            print(f"Error during migration: {e}")
            await db.rollback()
            raise

if __name__ == "__main__":
    asyncio.run(migrate_is_system())
