from quart import Blueprint, request, render_template, redirect, url_for, jsonify
import aiosqlite
import base64
import html
from config import DATABASE
from util.blacklist.ip_blacklist import black_list_ip
from util.rate_limit import api_rate_limit

script_bp = Blueprint("script", __name__, url_prefix="/script")


def sanitize_input(value):
    if isinstance(value, str):
        return html.escape(value)
    return value


@script_bp.route("/user/<int:user_id>")
@black_list_ip()
async def user_scripts(user_id):
    """View/edit scripts for a specific user"""
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT * FROM user WHERE id = ?", (user_id,))
        user = await cursor.fetchone()

        if not user:
            return "User not found", 404

        cursor = await db.execute(
            "SELECT * FROM scripts WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        )
        user_scripts = await cursor.fetchall()

        cursor = await db.execute(
            "SELECT * FROM scripts WHERE is_global = 1 ORDER BY created_at DESC"
        )
        global_scripts = await cursor.fetchall()

        return await render_template(
            "scripts/user_scripts.html",
            user=dict(user),
            user_scripts=[dict(s) for s in user_scripts],
            global_scripts=[dict(s) for s in global_scripts],
            active_page="dashboard",  # highlight dashboard in the menu
        )


@script_bp.route("/add", methods=["POST"])
@black_list_ip()
async def add_script():
    """Add a new script for a user"""
    form = await request.form
    name = sanitize_input(form.get("name"))
    content = form.get("content")
    user_id = sanitize_input(form.get("user_id"))

    if not user_id:
        return "User ID is required", 400

    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT id FROM user WHERE id = ?", (user_id,))
        user = await cursor.fetchone()

        if not user:
            return "User not found", 404

        await db.execute(
            """
            INSERT INTO scripts (name, content, is_global, user_id)
            VALUES (?, ?, 0, ?)
            """,
            (name, content, user_id),
        )
        await db.commit()

    return redirect(url_for("script.user_scripts", user_id=user_id))


@script_bp.route("/update", methods=["POST"])
@black_list_ip()
async def update_script():
    """Update an existing script"""
    form = await request.form
    script_id = sanitize_input(form.get("script_id"))
    name = sanitize_input(form.get("name"))
    content = form.get("content")

    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT user_id FROM scripts WHERE id = ?", (script_id,)
        )
        script = await cursor.fetchone()

        if not script:
            return "Script not found", 404

        user_id = script["user_id"]

        await db.execute(
            """
            UPDATE scripts 
            SET name = ?, content = ?, executed = 0
            WHERE id = ?
            """,
            (name, content, script_id),
        )
        await db.commit()

    return redirect(url_for("script.user_scripts", user_id=user_id))


@script_bp.route("/delete/<int:script_id>", methods=["POST"])
@black_list_ip()
async def delete_script(script_id):
    """Delete a script"""
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT user_id FROM scripts WHERE id = ?", (script_id,)
        )
        script = await cursor.fetchone()

        if not script:
            return "Script not found", 404

        user_id = script["user_id"]

        await db.execute("DELETE FROM scripts WHERE id = ?", (script_id,))
        await db.commit()

    return redirect(url_for("script.user_scripts", user_id=user_id))


@script_bp.route("/execute/<int:script_id>", methods=["POST"])
@black_list_ip()
async def execute_script(script_id):
    """Queue a script for execution by a client"""
    user_id = sanitize_input(request.args.get("user_id"))

    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT * FROM scripts WHERE id = ?", (script_id,))
        script = await cursor.fetchone()

        if not script:
            return "Script not found", 404

        target_user_id = script["user_id"] or user_id

        if not target_user_id:
            return "No target user specified", 400

        cursor = await db.execute(
            "SELECT hwid FROM user WHERE id = ?", (target_user_id,)
        )
        user = await cursor.fetchone()

        if not user:
            return "User not found", 404

        await db.execute(
            """
            UPDATE scripts 
            SET executed = 0 
            WHERE id = ?
            """,
            (script_id,),
        )
        await db.commit()

    return redirect(url_for("script.user_scripts", user_id=target_user_id))


@script_bp.route("/check-execution/<int:script_id>", methods=["GET"])
@api_rate_limit()
async def check_execution(script_id):
    """API endpoint to check if a script has been executed"""
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT executed FROM scripts WHERE id = ?", (script_id,)
        )
        script = await cursor.fetchone()

        if not script:
            return jsonify({"status": "error", "message": "Script not found"}), 404

        return jsonify(
            {
                "status": "success",
                "executed": bool(script["executed"]),
                "script_id": script_id,
            }
        )


@script_bp.route("/global")
@black_list_ip()
async def global_scripts():
    """View all global scripts"""
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            "SELECT * FROM scripts WHERE is_global = 1 ORDER BY created_at DESC"
        )
        global_scripts = await cursor.fetchall()

        cursor = await db.execute(
            "SELECT id, pcname, ip_address, is_active FROM user ORDER BY is_active DESC, pcname ASC"
        )
        users = await cursor.fetchall()

        cursor = await db.execute("SELECT * FROM client_groups ORDER BY name")
        groups = await cursor.fetchall()

        cursor = await db.execute("SELECT * FROM client_tags ORDER BY name")
        tags = await cursor.fetchall()

        return await render_template(
            "scripts/global_scripts.html",
            global_scripts=[dict(s) for s in global_scripts],
            users=[dict(u) for u in users],
            groups=[dict(g) for g in groups],
            tags=[dict(t) for t in tags],
            active_page="global_scripts",
        )


@script_bp.route("/add-global", methods=["POST"])
@black_list_ip()
async def add_global_script():
    """Add a new global script"""
    form = await request.form
    name = sanitize_input(form.get("name"))
    content = form.get("content")

    async with aiosqlite.connect(DATABASE) as db:

        await db.execute(
            """
            INSERT INTO scripts (name, content, is_global, user_id)
            VALUES (?, ?, 1, NULL)
            """,
            (name, content),
        )
        await db.commit()

    return redirect(url_for("script.global_scripts"))


@script_bp.route("/execute-global", methods=["POST"])
@black_list_ip()
async def execute_global_script():
    """Execute a global script on selected users"""
    form = await request.form
    script_id = sanitize_input(form.get("script_id"))
    selected_users = [sanitize_input(user) for user in form.getlist("selected_users")]

    if not script_id or not selected_users:
        return "Script ID and at least one user are required", 400

    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            "SELECT content FROM scripts WHERE id = ?", (script_id,)
        )
        script = await cursor.fetchone()

        if not script:
            return "Script not found", 404

        for user_id in selected_users:
            await db.execute(
                """
                INSERT INTO scripts (name, content, is_global, user_id, executed)
                SELECT name, content, 0, ?, 0 FROM scripts WHERE id = ?
                """,
                (user_id, script_id),
            )

        await db.commit()

    return redirect(url_for("script.global_scripts"))


@script_bp.route("/api/global-scripts", methods=["GET"])
@api_rate_limit()
async def api_get_global_scripts():
    """API endpoint to get all global scripts for bulk operations"""
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, name, created_at FROM scripts WHERE is_global = 1 ORDER BY name"
        )
        scripts = await cursor.fetchall()
        return jsonify({"scripts": [dict(s) for s in scripts]})


@script_bp.route("/api/users-by-group/<int:group_id>", methods=["GET"])
@api_rate_limit()
async def api_get_users_by_group(group_id):
    """Get users in a specific group"""
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT u.id, u.pcname, u.ip_address, u.is_active
            FROM user u
            JOIN client_group_assignments cga ON u.id = cga.client_id
            WHERE cga.group_id = ?
            ORDER BY u.is_active DESC, u.pcname ASC
            """,
            (group_id,),
        )
        users = await cursor.fetchall()
        return jsonify({"users": [dict(u) for u in users]})


@script_bp.route("/api/users-by-tag/<int:tag_id>", methods=["GET"])
@api_rate_limit()
async def api_get_users_by_tag(tag_id):
    """Get users with a specific tag"""
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT u.id, u.pcname, u.ip_address, u.is_active
            FROM user u
            JOIN client_tag_assignments cta ON u.id = cta.client_id
            WHERE cta.tag_id = ?
            ORDER BY u.is_active DESC, u.pcname ASC
            """,
            (tag_id,),
        )
        users = await cursor.fetchall()
        return jsonify({"users": [dict(u) for u in users]})


def register_script_routes(app):
    """Register script routes with the app"""
    app.register_blueprint(script_bp)
    return app
