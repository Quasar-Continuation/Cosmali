import aiosqlite
from config import DATABASE


async def get_users(offset, limit, sort_by=None, order=None, search_term=None):
    """Get paginated and sorted users from the database"""
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row

        # no deleted mfs
        query = "SELECT * FROM user WHERE pcname NOT LIKE 'PENDING_DELETION_%'"
        params = []

        if search_term:
            query += " AND (pcname LIKE ? OR ip_address LIKE ? OR country LIKE ? OR hwid LIKE ?)"
            search_pattern = f"%{search_term}%"
            params.extend(
                [search_pattern, search_pattern, search_pattern, search_pattern]
            )

        if sort_by and order:

            allowed_columns = [
                "id",
                "pcname",
                "ip_address",
                "country",
                "last_ping",
                "first_ping",
                "is_active",
                "hwid",
                "hostname",
            ]
            if sort_by in allowed_columns and order in ["asc", "desc"]:
                query += f" ORDER BY {sort_by} {order}"

        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with db.execute(query, params) as cursor:
            users = await cursor.fetchall()

    return [dict(user) for user in users]


async def get_user_count(search_term=None):
    """Get total number of users in the database"""
    async with aiosqlite.connect(DATABASE) as db:
        search_pattern = f"%{search_term}%" if search_term else None
        if search_term:
            query = """
                SELECT COUNT(*) FROM user
                WHERE pcname NOT LIKE 'PENDING_DELETION_%'
                AND (pcname LIKE ? OR ip_address LIKE ? OR country LIKE ? OR hwid LIKE ?)
            """
            async with db.execute(
                query, [search_pattern, search_pattern, search_pattern, search_pattern]
            ) as cursor:
                count = await cursor.fetchone()
        else:
            async with db.execute(
                "SELECT COUNT(*) FROM user WHERE pcname NOT LIKE 'PENDING_DELETION_%'"
            ) as cursor:
                count = await cursor.fetchone()

    return count[0]


async def fetch_users_for_map():
    """Fetch user location data for map display"""
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT pcname, latitude, longitude, country FROM user"
        ) as cursor:
            users = await cursor.fetchall()

    return [dict(user) for user in users]
