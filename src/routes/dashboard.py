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

        async with aiosqlite.connect(DATABASE) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute("SELECT * FROM client_groups ORDER BY name")
            groups = await cursor.fetchall()

            cursor = await db.execute("SELECT * FROM client_tags ORDER BY name")
            tags = await cursor.fetchall()

            if users:
                user_ids = [str(user["id"]) for user in users]
                placeholders = ",".join("?" * len(user_ids))
                cursor = await db.execute(
                    f"""
                    SELECT cga.client_id, cg.id, cg.name, cg.color
                    FROM client_group_assignments cga
                    JOIN client_groups cg ON cga.group_id = cg.id
                    WHERE cga.client_id IN ({placeholders})
                    """,
                    user_ids,
                )
                group_assignments = await cursor.fetchall()

                cursor = await db.execute(
                    f"""
                    SELECT cta.client_id, ct.id, ct.name, ct.color
                    FROM client_tag_assignments cta
                    JOIN client_tags ct ON cta.tag_id = ct.id
                    WHERE cta.client_id IN ({placeholders})
                    """,
                    user_ids,
                )
                tag_assignments = await cursor.fetchall()

                user_groups = {}
                user_tags = {}

                for assignment in group_assignments:
                    if assignment["client_id"] not in user_groups:
                        user_groups[assignment["client_id"]] = []
                    user_groups[assignment["client_id"]].append(dict(assignment))

                for assignment in tag_assignments:
                    if assignment["client_id"] not in user_tags:
                        user_tags[assignment["client_id"]] = []
                    user_tags[assignment["client_id"]].append(dict(assignment))

                for user in users:
                    user["groups"] = user_groups.get(user["id"], [])
                    user["tags"] = user_tags.get(user["id"], [])

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
            groups=[dict(g) for g in groups],
            tags=[dict(t) for t in tags],
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

    @app.route("/bulk-delete", methods=["POST"])
    @black_list_ip()
    async def bulk_delete_users():
        """Delete multiple users"""
        form = await request.form
        user_ids = [int(uid) for uid in form.getlist("user_ids") if uid.isdigit()]

        if not user_ids:
            return jsonify({"status": "error", "message": "No users selected"}), 400

        try:
            async with aiosqlite.connect(DATABASE) as db:
                placeholders = ",".join("?" * len(user_ids))

                # Delete related records first
                await db.execute(
                    f"DELETE FROM scripts WHERE user_id IN ({placeholders})", user_ids
                )
                await db.execute(
                    f"DELETE FROM client_group_assignments WHERE client_id IN ({placeholders})",
                    user_ids,
                )
                await db.execute(
                    f"DELETE FROM client_tag_assignments WHERE client_id IN ({placeholders})",
                    user_ids,
                )
                await db.execute(
                    f"DELETE FROM script_execution_logs WHERE client_id IN ({placeholders})",
                    user_ids,
                )

                # Delete users
                await db.execute(
                    f"DELETE FROM user WHERE id IN ({placeholders})", user_ids
                )
                await db.commit()

                return jsonify(
                    {
                        "status": "success",
                        "message": f"Successfully deleted {len(user_ids)} users",
                    }
                )
        except Exception as e:
            print(f"Error bulk deleting users: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/bulk-assign-group", methods=["POST"])
    @black_list_ip()
    async def bulk_assign_group():
        """Assign multiple users to a group"""
        form = await request.form
        user_ids = [int(uid) for uid in form.getlist("user_ids") if uid.isdigit()]
        group_id = form.get("group_id")

        if not user_ids or not group_id:
            return (
                jsonify(
                    {"status": "error", "message": "Users and group must be selected"}
                ),
                400,
            )

        try:
            async with aiosqlite.connect(DATABASE) as db:
                # Remove existing assignments to this group for these users
                placeholders = ",".join("?" * len(user_ids))
                await db.execute(
                    f"DELETE FROM client_group_assignments WHERE group_id = ? AND client_id IN ({placeholders})",
                    [group_id] + user_ids,
                )

                # Add new assignments
                for user_id in user_ids:
                    await db.execute(
                        "INSERT INTO client_group_assignments (client_id, group_id) VALUES (?, ?)",
                        (user_id, group_id),
                    )
                await db.commit()

                return jsonify(
                    {
                        "status": "success",
                        "message": f"Assigned {len(user_ids)} users to group",
                    }
                )
        except Exception as e:
            print(f"Error bulk assigning group: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/bulk-assign-tag", methods=["POST"])
    @black_list_ip()
    async def bulk_assign_tag():
        """Assign multiple users to a tag"""
        form = await request.form
        user_ids = [int(uid) for uid in form.getlist("user_ids") if uid.isdigit()]
        tag_id = form.get("tag_id")

        if not user_ids or not tag_id:
            return (
                jsonify(
                    {"status": "error", "message": "Users and tag must be selected"}
                ),
                400,
            )

        try:
            async with aiosqlite.connect(DATABASE) as db:
                # Add new assignments (ignore if already exists)
                for user_id in user_ids:
                    await db.execute(
                        "INSERT OR IGNORE INTO client_tag_assignments (client_id, tag_id) VALUES (?, ?)",
                        (user_id, tag_id),
                    )
                await db.commit()

                return jsonify(
                    {"status": "success", "message": f"Tagged {len(user_ids)} users"}
                )
        except Exception as e:
            print(f"Error bulk assigning tag: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/bulk-execute-script", methods=["POST"])
    @black_list_ip()
    async def bulk_execute_script():
        """Execute a script on multiple users"""
        form = await request.form
        user_ids = [int(uid) for uid in form.getlist("user_ids") if uid.isdigit()]
        script_id = form.get("script_id")

        if not user_ids or not script_id:
            return (
                jsonify(
                    {"status": "error", "message": "Users and script must be selected"}
                ),
                400,
            )

        try:
            async with aiosqlite.connect(DATABASE) as db:
                # Get the script content
                cursor = await db.execute(
                    "SELECT name, content FROM scripts WHERE id = ?", (script_id,)
                )
                script = await cursor.fetchone()

                if not script:
                    return (
                        jsonify({"status": "error", "message": "Script not found"}),
                        404,
                    )

                # Create script instances for each user
                for user_id in user_ids:
                    await db.execute(
                        """
                        INSERT INTO scripts (name, content, is_global, user_id, executed)
                        VALUES (?, ?, 0, ?, 0)
                        """,
                        (f"[BULK] {script['name']}", script["content"], user_id),
                    )
                await db.commit()

                return jsonify(
                    {
                        "status": "success",
                        "message": f"Queued script for execution on {len(user_ids)} users",
                    }
                )
        except Exception as e:
            print(f"Error bulk executing script: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    return app
