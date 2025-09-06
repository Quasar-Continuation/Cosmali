import aiosqlite
import asyncio
from config import DATABASE

async def migrate_manually_triggered():
    """Add manually_triggered column to existing scripts table"""
    print("Migrating scripts table to add manually_triggered column...")

    async with aiosqlite.connect(DATABASE) as db:
        try:
            cursor = await db.execute("PRAGMA table_info(scripts)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

            if 'manually_triggered' not in column_names:
                print("Adding manually_triggered column...")
                await db.execute("ALTER TABLE scripts ADD COLUMN manually_triggered BOOLEAN DEFAULT 0")
                await db.commit()
                print("Migration completed successfully!")
            else:
                print("manually_triggered column already exists!")

        except Exception as e:
            print(f"Error during migration: {e}")
            await db.rollback()
            raise

if __name__ == "__main__":
    asyncio.run(migrate_manually_triggered())
