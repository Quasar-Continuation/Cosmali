from quart import Blueprint, request, render_template, redirect, url_for, jsonify
import aiosqlite
import html
from config import DATABASE
from util.blacklist.ip_blacklist import black_list_ip
from util.rate_limit import api_rate_limit

groups_bp = Blueprint("groups", __name__, url_prefix="/groups")


def sanitize_input(value):
    if isinstance(value, str):
        return html.escape(value)
    return value


@groups_bp.route("/")
@black_list_ip()
async def manage_groups():
    """View and manage client groups and tags"""
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT g.*, COUNT(cga.client_id) as client_count
            FROM client_groups g
            LEFT JOIN client_group_assignments cga ON g.id = cga.group_id
            GROUP BY g.id
            ORDER BY g.name
            """
        )
        groups = await cursor.fetchall()

        cursor = await db.execute(
            """
            SELECT t.*, COUNT(cta.client_id) as client_count
            FROM client_tags t
            LEFT JOIN client_tag_assignments cta ON t.id = cta.tag_id
            GROUP BY t.id
            ORDER BY t.name
            """
        )
        tags = await cursor.fetchall()

        return await render_template(
            "groups/manage.html",
            groups=[dict(g) for g in groups],
            tags=[dict(t) for t in tags],
            active_page="groups",
        )


@groups_bp.route("/create-group", methods=["POST"])
@black_list_ip()
async def create_group():
    """Create a new client group"""
    form = await request.form
    name = sanitize_input(form.get("name"))
    description = sanitize_input(form.get("description", ""))
    color = sanitize_input(form.get("color", "#007bff"))

    if not name:
        return jsonify({"status": "error", "message": "Group name is required"}), 400

    async with aiosqlite.connect(DATABASE) as db:
        try:
            await db.execute(
                "INSERT INTO client_groups (name, description, color) VALUES (?, ?, ?)",
                (name, description, color),
            )
            await db.commit()
            return jsonify(
                {"status": "success", "message": f"Group '{name}' created successfully"}
            )
        except aiosqlite.IntegrityError:
            return (
                jsonify({"status": "error", "message": "Group name already exists"}),
                400,
            )


@groups_bp.route("/create-tag", methods=["POST"])
@black_list_ip()
async def create_tag():
    """Create a new client tag"""
    form = await request.form
    name = sanitize_input(form.get("name"))
    color = sanitize_input(form.get("color", "#6c757d"))

    if not name:
        return jsonify({"status": "error", "message": "Tag name is required"}), 400

    async with aiosqlite.connect(DATABASE) as db:
        try:
            await db.execute(
                "INSERT INTO client_tags (name, color) VALUES (?, ?)", (name, color)
            )
            await db.commit()
            return jsonify(
                {"status": "success", "message": f"Tag '{name}' created successfully"}
            )
        except aiosqlite.IntegrityError:
            return (
                jsonify({"status": "error", "message": "Tag name already exists"}),
                400,
            )


@groups_bp.route("/assign-group", methods=["POST"])
@black_list_ip()
async def assign_group():
    """Assign clients to a group"""
    form = await request.form
    group_id = sanitize_input(form.get("group_id"))
    client_ids = [sanitize_input(cid) for cid in form.getlist("client_ids")]

    if not group_id or not client_ids:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Group and at least one client must be selected",
                }
            ),
            400,
        )

    async with aiosqlite.connect(DATABASE) as db:
        placeholders = ",".join("?" * len(client_ids))
        await db.execute(
            f"DELETE FROM client_group_assignments WHERE group_id = ? AND client_id IN ({placeholders})",
            [group_id] + client_ids,
        )

        for client_id in client_ids:
            await db.execute(
                "INSERT OR IGNORE INTO client_group_assignments (client_id, group_id) VALUES (?, ?)",
                (client_id, group_id),
            )

        await db.commit()
        return jsonify(
            {
                "status": "success",
                "message": f"Assigned {len(client_ids)} clients to group",
            }
        )


@groups_bp.route("/assign-tag", methods=["POST"])
@black_list_ip()
async def assign_tag():
    """Assign clients to a tag"""
    form = await request.form
    tag_id = sanitize_input(form.get("tag_id"))
    client_ids = [sanitize_input(cid) for cid in form.getlist("client_ids")]

    if not tag_id or not client_ids:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Tag and at least one client must be selected",
                }
            ),
            400,
        )

    async with aiosqlite.connect(DATABASE) as db:
        for client_id in client_ids:
            await db.execute(
                "INSERT OR IGNORE INTO client_tag_assignments (client_id, tag_id) VALUES (?, ?)",
                (client_id, tag_id),
            )

        await db.commit()
        return jsonify(
            {"status": "success", "message": f"Tagged {len(client_ids)} clients"}
        )


@groups_bp.route("/remove-from-group", methods=["POST"])
@black_list_ip()
async def remove_from_group():
    """Remove clients from a group"""
    form = await request.form
    group_id = sanitize_input(form.get("group_id"))
    client_ids = [sanitize_input(cid) for cid in form.getlist("client_ids")]

    if not group_id or not client_ids:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Group and at least one client must be selected",
                }
            ),
            400,
        )

    async with aiosqlite.connect(DATABASE) as db:
        placeholders = ",".join("?" * len(client_ids))
        await db.execute(
            f"DELETE FROM client_group_assignments WHERE group_id = ? AND client_id IN ({placeholders})",
            [group_id] + client_ids,
        )
        await db.commit()
        return jsonify(
            {
                "status": "success",
                "message": f"Removed {len(client_ids)} clients from group",
            }
        )


@groups_bp.route("/remove-tag", methods=["POST"])
@black_list_ip()
async def remove_tag():
    """Remove tag from clients"""
    form = await request.form
    tag_id = sanitize_input(form.get("tag_id"))
    client_ids = [sanitize_input(cid) for cid in form.getlist("client_ids")]

    if not tag_id or not client_ids:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Tag and at least one client must be selected",
                }
            ),
            400,
        )

    async with aiosqlite.connect(DATABASE) as db:
        placeholders = ",".join("?" * len(client_ids))
        await db.execute(
            f"DELETE FROM client_tag_assignments WHERE tag_id = ? AND client_id IN ({placeholders})",
            [tag_id] + client_ids,
        )
        await db.commit()
        return jsonify(
            {
                "status": "success",
                "message": f"Removed tag from {len(client_ids)} clients",
            }
        )


@groups_bp.route("/delete-group/<int:group_id>", methods=["POST"])
@black_list_ip()
async def delete_group(group_id):
    """Delete a client group"""
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute(
            "SELECT name FROM client_groups WHERE id = ?", (group_id,)
        )
        group = await cursor.fetchone()

        if not group:
            return jsonify({"status": "error", "message": "Group not found"}), 404

        await db.execute("DELETE FROM client_groups WHERE id = ?", (group_id,))
        await db.commit()

        return jsonify(
            {"status": "success", "message": f"Group '{group[0]}' deleted successfully"}
        )


@groups_bp.route("/delete-tag/<int:tag_id>", methods=["POST"])
@black_list_ip()
async def delete_tag(tag_id):
    """Delete a client tag"""
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute(
            "SELECT name FROM client_tags WHERE id = ?", (tag_id,)
        )
        tag = await cursor.fetchone()

        if not tag:
            return jsonify({"status": "error", "message": "Tag not found"}), 404

        await db.execute("DELETE FROM client_tags WHERE id = ?", (tag_id,))
        await db.commit()

        return jsonify(
            {"status": "success", "message": f"Tag '{tag[0]}' deleted successfully"}
        )


@groups_bp.route("/update-group", methods=["POST"])
@black_list_ip()
async def update_group():
    """Update a client group"""
    form = await request.form
    group_id = sanitize_input(form.get("group_id"))
    name = sanitize_input(form.get("name"))
    description = sanitize_input(form.get("description", ""))
    color = sanitize_input(form.get("color", "#007bff"))

    if not group_id or not name:
        return (
            jsonify({"status": "error", "message": "Group ID and name are required"}),
            400,
        )

    async with aiosqlite.connect(DATABASE) as db:
        try:
            await db.execute(
                "UPDATE client_groups SET name = ?, description = ?, color = ? WHERE id = ?",
                (name, description, color, group_id),
            )
            await db.commit()
            return jsonify(
                {"status": "success", "message": f"Group '{name}' updated successfully"}
            )
        except aiosqlite.IntegrityError:
            return (
                jsonify({"status": "error", "message": "Group name already exists"}),
                400,
            )


@groups_bp.route("/update-tag", methods=["POST"])
@black_list_ip()
async def update_tag():
    """Update a client tag"""
    form = await request.form
    tag_id = sanitize_input(form.get("tag_id"))
    name = sanitize_input(form.get("name"))
    color = sanitize_input(form.get("color", "#6c757d"))

    if not tag_id or not name:
        return (
            jsonify({"status": "error", "message": "Tag ID and name are required"}),
            400,
        )

    async with aiosqlite.connect(DATABASE) as db:
        try:
            await db.execute(
                "UPDATE client_tags SET name = ?, color = ? WHERE id = ?",
                (name, color, tag_id),
            )
            await db.commit()
            return jsonify(
                {"status": "success", "message": f"Tag '{name}' updated successfully"}
            )
        except aiosqlite.IntegrityError:
            return (
                jsonify({"status": "error", "message": "Tag name already exists"}),
                400,
            )


@groups_bp.route("/api/groups", methods=["GET"])
@api_rate_limit()
async def api_get_groups():
    """API endpoint to get all groups"""
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM client_groups ORDER BY name")
        groups = await cursor.fetchall()
        return jsonify({"groups": [dict(g) for g in groups]})


@groups_bp.route("/api/tags", methods=["GET"])
@api_rate_limit()
async def api_get_tags():
    """API endpoint to get all tags"""
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM client_tags ORDER BY name")
        tags = await cursor.fetchall()
        return jsonify({"tags": [dict(t) for t in tags]})


def register_group_routes(app):
    """Register group routes with the app"""
    app.register_blueprint(groups_bp)
    return app
