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
            "SELECT * FROM scripts WHERE user_id = ? AND is_system = 0 ORDER BY execution_order ASC, created_at DESC",
            (user_id,),
        )
        user_scripts = await cursor.fetchall()

        cursor = await db.execute(
            "SELECT * FROM scripts WHERE is_global = 1 AND is_system = 0 ORDER BY execution_order ASC, created_at DESC"
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

        # Get the next execution order for user scripts
        cursor = await db.execute(
            "SELECT COALESCE(MAX(execution_order), 0) + 1 as next_order FROM scripts WHERE is_global = 0 AND is_system = 0"
        )
        next_order = await cursor.fetchone()
        execution_order = next_order[0] if next_order else 1
        
        await db.execute(
            """
            INSERT INTO scripts (name, content, is_global, user_id, autorun, startup, manually_triggered, execution_order)
            VALUES (?, ?, 0, ?, 0, 0, 0, ?)
            """,
            (name, content, user_id, execution_order),
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
            "SELECT user_id, is_global FROM scripts WHERE id = ?", (script_id,)
        )
        script = await cursor.fetchone()

        if not script:
            return "Script not found", 404

        await db.execute(
            """
            UPDATE scripts 
            SET name = ?, content = ?, executed = 0
            WHERE id = ?
            """,
            (name, content, script_id),
        )
        await db.commit()

        # Redirect based on script type
        if script["is_global"]:
            return redirect(url_for("script.global_scripts"))
        else:
            user_id = script["user_id"]
            if user_id:
                return redirect(url_for("script.user_scripts", user_id=user_id))
            else:
                # Fallback to global scripts if no user_id
                return redirect(url_for("script.global_scripts"))


@script_bp.route("/delete/<int:script_id>", methods=["POST"])
@black_list_ip()
async def delete_script(script_id):
    """Delete a script"""
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT user_id, is_global FROM scripts WHERE id = ?", (script_id,)
        )
        script = await cursor.fetchone()

        if not script:
            return "Script not found", 404

        await db.execute("DELETE FROM scripts WHERE id = ?", (script_id,))
        await db.commit()

        # Redirect based on script type
        if script["is_global"]:
            return redirect(url_for("script.global_scripts"))
        else:
            user_id = script["user_id"]
            if user_id:
                return redirect(url_for("script.user_scripts", user_id=user_id))
            else:
                # Fallback to global scripts if no user_id
                return redirect(url_for("script.global_scripts"))





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
            "SELECT * FROM scripts WHERE is_global = 1 AND is_system = 0 ORDER BY execution_order ASC, created_at DESC"
        )
        global_scripts = await cursor.fetchall()

        cursor = await db.execute(
            "SELECT id, pcname, ip_address, is_active FROM user ORDER BY is_active DESC, pcname ASC"
        )
        users = await cursor.fetchall()

        return await render_template(
            "scripts/global_scripts.html",
            global_scripts=[dict(s) for s in global_scripts],
            users=[dict(u) for u in users],
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
        # Get the next execution order for global scripts
        cursor = await db.execute(
            "SELECT COALESCE(MAX(execution_order), 0) + 1 as next_order FROM scripts WHERE is_global = 1 AND is_system = 0"
        )
        next_order = await cursor.fetchone()
        execution_order = next_order[0] if next_order else 1

        await db.execute(
            """
            INSERT INTO scripts (name, content, is_global, user_id, autorun, startup, manually_triggered, execution_order)
            VALUES (?, ?, 1, NULL, 0, 0, 0, ?)
            """,
            (name, content, execution_order),
        )
        await db.commit()

    return redirect(url_for("script.global_scripts"))


@script_bp.route("/execute-global", methods=["POST"])
@black_list_ip()
async def execute_global_script():
    """Execute a global script on selected users or random users based on count"""
    form = await request.form
    script_id = sanitize_input(form.get("script_id"))
    execution_mode = form.get("execution_mode", "users")
    
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            "SELECT content, autorun, startup FROM scripts WHERE id = ?", (script_id,)
        )
        script = await cursor.fetchone()

        if not script:
            return "Script not found", 404

        if execution_mode == "users":
            # Mode 1: Execute on specific selected users
            selected_users = [sanitize_input(user) for user in form.getlist("selected_users")]
            if not selected_users:
                return "At least one user must be selected", 400
                
            target_users = selected_users
        else:
            # Mode 2: Execute on random active users based on count
            execution_count = int(form.get("execution_count", 5))
            if execution_count < 1:
                return "Execution count must be at least 1", 400
                
            # Get random active users
            cursor = await db.execute(
                "SELECT id FROM user WHERE is_active = 1 ORDER BY RANDOM() LIMIT ?",
                (execution_count,)
            )
            random_users = await cursor.fetchall()
            target_users = [user["id"] for user in random_users]
            
            if not target_users:
                return "No active users available for execution", 400

        for user_id in target_users:
            # Check if this script already exists for this user
            cursor = await db.execute(
                "SELECT id FROM scripts WHERE user_id = ? AND is_global = 0 AND name = (SELECT name FROM scripts WHERE id = ?)",
                (user_id, script_id)
            )
            existing_script = await cursor.fetchone()
            
            if existing_script:
                # Update existing script instead of creating a duplicate
                await db.execute(
                    """
                    UPDATE scripts 
                    SET content = ?, autorun = ?, startup = ?, executed = 0
                    WHERE id = ?
                    """,
                    (script["content"], script["autorun"], script["startup"], existing_script["id"])
                )
            else:
                # Get the next execution order for user scripts
                cursor = await db.execute(
                    "SELECT COALESCE(MAX(execution_order), 0) + 1 as next_order FROM scripts WHERE is_global = 0 AND is_system = 0"
                )
                next_order = await cursor.fetchone()
                execution_order = next_order[0] if next_order else 1
                
                # Create new script only if it doesn't exist
                await db.execute(
                    """
                    INSERT INTO scripts (name, content, is_global, user_id, executed, autorun, startup, manually_triggered, execution_order)
                    SELECT name, content, 0, ?, 0, autorun, startup, 1, ? FROM scripts WHERE id = ?
                    """,
                    (user_id, execution_order, script_id),
                )

        await db.commit()

    # Redirect back to the user's script page if we have a specific user context
    # Check if we have a user_id in the form (indicating execution from user page)
    user_context = form.get("user_context")
    if user_context:
        try:
            user_id = int(user_context)
            return redirect(url_for("script.user_scripts", user_id=user_id))
        except (ValueError, TypeError):
            pass
    
    # Fallback to global scripts if no user context
    return redirect(url_for("script.global_scripts"))


@script_bp.route("/toggle-autorun/<int:script_id>", methods=["POST"])
@black_list_ip()
async def toggle_autorun(script_id):
    """Toggle autorun setting for a script"""
    form = await request.form
    autorun = form.get("autorun") == "1"
    
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT user_id, is_global FROM scripts WHERE id = ?", (script_id,)
        )
        script = await cursor.fetchone()
        
        if not script:
            return "Script not found", 404
        
        await db.execute(
            "UPDATE scripts SET autorun = ? WHERE id = ?",
            (autorun, script_id)
        )
        await db.commit()
        
        if script["is_global"]:
            return redirect(url_for("script.global_scripts"))
        else:
            return redirect(url_for("script.user_scripts", user_id=script["user_id"]))


@script_bp.route("/toggle-startup/<int:script_id>", methods=["POST"])
@black_list_ip()
async def toggle_startup(script_id):
    """Toggle startup setting for a script"""
    form = await request.form
    startup = form.get("startup") == "1"
    
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT user_id, is_global FROM scripts WHERE id = ?", (script_id,)
        )
        script = await cursor.fetchone()
        
        if not script:
            return "Script not found", 404
        
        await db.execute(
            "UPDATE scripts SET startup = ? WHERE id = ?",
            (startup, script_id)
        )
        await db.commit()
        
        if script["is_global"]:
            return redirect(url_for("script.global_scripts"))
        else:
            return redirect(url_for("script.user_scripts", user_id=script["user_id"]))


@script_bp.route("/execute-manual/<int:script_id>", methods=["POST"])
@black_list_ip()
async def execute_manual_script(script_id):
    """Manually execute a script for a specific user (not autorun/startup)"""
    user_id = sanitize_input(request.args.get("user_id"))
    
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT user_id, is_global FROM scripts WHERE id = ?", (script_id,)
        )
        script = await cursor.fetchone()
        
        if not script:
            return "Script not found", 404
        
        target_user_id = script["user_id"] or user_id
        
        if not target_user_id:
            return "No target user specified", 400
        
        # Reset the executed flag and mark as manually triggered to allow the script to run again
        # This is for manual execution - the script will be fetched by the client
        await db.execute(
            "UPDATE scripts SET executed = 0, manually_triggered = 1 WHERE id = ?",
            (script_id,)
        )
        await db.commit()
        
        # If we have a user context (executing from user page), redirect back there
        if user_id:
            return redirect(url_for("script.user_scripts", user_id=user_id))
        # Otherwise, redirect based on script type
        elif script["is_global"]:
            return redirect(url_for("script.global_scripts"))
        else:
            return redirect(url_for("script.user_scripts", user_id=target_user_id))


@script_bp.route("/reset-startup/<int:script_id>", methods=["POST"])
@black_list_ip()
async def reset_startup_script(script_id):
    """Reset a startup script so it can run again on the next agent connection"""
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT user_id, is_global FROM scripts WHERE id = ?", (script_id,)
        )
        script = await cursor.fetchone()
        
        if not script:
            return "Script not found", 404
        
        # Reset the executed flag for startup scripts so they can run again
        await db.execute(
            "UPDATE scripts SET executed = 0 WHERE id = ?",
            (script_id,)
        )
        await db.commit()
        
        if script["is_global"]:
            return redirect(url_for("script.global_scripts"))
        else:
            user_id = script["user_id"]
            if user_id:
                return redirect(url_for("script.user_scripts", user_id=user_id))
            else:
                return redirect(url_for("script.global_scripts"))


@script_bp.route("/debug-scripts/<int:user_id>")
@black_list_ip()
async def debug_scripts(user_id):
    """Debug endpoint to check script status for a user"""
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        
        # Get user info
        cursor = await db.execute("SELECT * FROM user WHERE id = ?", (user_id,))
        user = await cursor.fetchone()
        
        if not user:
            return "User not found", 404
        
        # Get all scripts for this user
        cursor = await db.execute(
            "SELECT * FROM scripts WHERE user_id = ? AND is_system = 0 ORDER BY created_at DESC",
            (user_id,)
        )
        user_scripts = await cursor.fetchall()
        
        # Get global scripts
        cursor = await db.execute(
            "SELECT * FROM scripts WHERE is_global = 1 AND is_system = 0 ORDER BY created_at DESC"
        )
        global_scripts = await cursor.fetchall()
        
        debug_info = {
            "user": dict(user),
            "user_scripts": [dict(s) for s in user_scripts],
            "total_user_scripts": len(user_scripts),
            "total_global_scripts": len(global_scripts)
        }
        
        return jsonify(debug_info)


@script_bp.route("/api/execution-count/<int:script_id>")
@black_list_ip()
async def get_execution_count(script_id):
    """Get execution count for a global script"""
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        
        # Check if this is a global script
        cursor = await db.execute(
            "SELECT is_global FROM scripts WHERE id = ?", (script_id,)
        )
        script = await cursor.fetchone()
        
        if not script:
            return jsonify({"status": "error", "message": "Script not found"}), 404
        
        if not script["is_global"]:
            return jsonify({"status": "error", "message": "Not a global script"}), 400
        
        # Count how many times this script has been executed across all users
        cursor = await db.execute(
            """
            SELECT COUNT(*) as count
            FROM scripts 
            WHERE is_global = 0 
            AND name = (SELECT name FROM scripts WHERE id = ?)
            AND executed = 1
            """,
            (script_id,)
        )
        result = await cursor.fetchone()
        executed_count = result["count"] if result else 0
        
        # Check if this script was executed on specific targets (manually_triggered = 1)
        # and get the total target count
        cursor = await db.execute(
            """
            SELECT COUNT(*) as total_target
            FROM scripts 
            WHERE is_global = 0 
            AND name = (SELECT name FROM scripts WHERE id = ?)
            AND manually_triggered = 1
            """,
            (script_id,)
        )
        target_result = await cursor.fetchone()
        total_target = target_result["total_target"] if target_result else 0
        
        return jsonify({
            "status": "success",
            "count": executed_count,
            "total_target": total_target if total_target > 0 else None
        })


def register_script_routes(app):
    """Register script routes with the app"""
    app.register_blueprint(script_bp)
    return app
