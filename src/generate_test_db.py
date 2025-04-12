import aiosqlite
import asyncio
import datetime
import uuid
from faker import Faker
import argparse

from config import DATABASE, USERS_AMMOUNT_IF_TEST

fake = Faker()


async def generate_test_db(num_users=USERS_AMMOUNT_IF_TEST):
    """Generate test database with fake user data"""
    print(f"Generating test database with {num_users} users...")

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
                hostname TEXT
            )
            """
        )
        await db.commit()

        answer = input("Delete existing user data? (y/n): ").strip().lower()
        if answer == "y":
            await db.execute("DELETE FROM user")
            print("Existing data cleared.")

        batch_size = 100
        total_inserted = 0

        print(f"Generating {num_users} fake users in batches of {batch_size}...")

        for batch_start in range(0, num_users, batch_size):
            users = []
            batch_end = min(batch_start + batch_size, num_users)
            batch_count = batch_end - batch_start

            for _ in range(batch_count):

                is_active = fake.boolean(chance_of_getting_true=30)

                first_ping_days_ago = fake.random_int(min=1, max=30)
                first_ping = datetime.datetime.now() - datetime.timedelta(
                    days=first_ping_days_ago
                )

                max_days_since_first = (datetime.datetime.now() - first_ping).days
                last_ping_days_ago = fake.random_int(
                    min=0, max=max(1, max_days_since_first)
                )
                last_ping = datetime.datetime.now() - datetime.timedelta(
                    days=last_ping_days_ago
                )

                users.append(
                    (
                        fake.hostname(),
                        fake.ipv4(),
                        fake.country(),
                        float(fake.latitude()),
                        float(fake.longitude()),
                        last_ping.strftime("%Y-%m-%d %H:%M:%S"),
                        first_ping.strftime("%Y-%m-%d %H:%M:%S"),
                        is_active,
                        str(uuid.uuid4()),  # Random HWID
                        fake.hostname(),
                    )
                )

            await db.executemany(
                """
                INSERT INTO user (pcname, ip_address, country, latitude, longitude, last_ping, first_ping, is_active, hwid, hostname)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                users,
            )
            await db.commit()

            total_inserted += len(users)
            print(
                f"Progress: {total_inserted}/{num_users} users inserted ({(total_inserted/num_users)*100:.1f}%)"
            )

        async with db.execute("SELECT COUNT(*) FROM user") as cursor:
            count = await cursor.fetchone()
            print(f"Database now contains {count[0]} users")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate test database with fake users"
    )
    parser.add_argument(
        "--users",
        type=int,
        default=USERS_AMMOUNT_IF_TEST,
        help=f"Number of users to generate (default: {USERS_AMMOUNT_IF_TEST})",
    )

    args = parser.parse_args()

    print("Database Test Generator")
    print("======================")
    print(f"Database path: {DATABASE}")

    asyncio.run(generate_test_db(args.users))
    print("Test database generation complete!")
