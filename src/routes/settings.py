from quart import Blueprint, request, render_template, redirect, url_for, jsonify
import aiosqlite
import html
from config import DATABASE
from util.blacklist.ip_blacklist import black_list_ip
from util.rate_limit import api_rate_limit

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


def sanitize_input(value):
    """Sanitize input to prevent XSS attacks"""
    if isinstance(value, str):
        return html.escape(value)
    return value


@settings_bp.route("/")
@black_list_ip()
async def settings_page():
    """Settings page with script execution order management"""
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        
        # Get all global scripts with their current execution order
        cursor = await db.execute(
            """
            SELECT id, name, autorun, startup, execution_order, created_at
            FROM scripts 
            WHERE is_global = 1 AND is_system = 0 
            ORDER BY execution_order ASC, created_at DESC
            """
        )
        global_scripts = await cursor.fetchall()
        
        # Get all user scripts with their current execution order
        cursor = await db.execute(
            """
            SELECT s.id, s.name, s.autorun, s.startup, s.execution_order, s.created_at, u.pcname
            FROM scripts s
            JOIN user u ON s.user_id = u.id
            WHERE s.is_global = 0 AND s.is_system = 0 
            ORDER BY s.execution_order ASC, s.created_at DESC
            """
        )
        user_scripts = await cursor.fetchall()
        
        return await render_template(
            "settings.html",
            global_scripts=[dict(s) for s in global_scripts],
            user_scripts=[dict(s) for s in user_scripts],
            active_page="settings"
        )


@settings_bp.route("/update-execution-order", methods=["POST"])
@black_list_ip()
async def update_execution_order():
    """Update the execution order of scripts"""
    try:
        data = await request.get_json()
        script_orders = data.get("script_orders", [])
        
        if not script_orders:
            return jsonify({"status": "error", "message": "No script orders provided"}), 400
        
        async with aiosqlite.connect(DATABASE) as db:
            # Update execution order for each script
            for script_order in script_orders:
                script_id = script_order.get("script_id")
                execution_order = script_order.get("execution_order")
                
                if script_id is None or execution_order is None:
                    continue
                
                # Validate that the script exists
                cursor = await db.execute(
                    "SELECT id FROM scripts WHERE id = ?", (script_id,)
                )
                script = await cursor.fetchone()
                
                if not script:
                    continue
                
                # Update the execution order
                await db.execute(
                    "UPDATE scripts SET execution_order = ? WHERE id = ?",
                    (execution_order, script_id)
                )
            
            await db.commit()
        
        return jsonify({"status": "success", "message": "Execution order updated successfully"})
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@settings_bp.route("/reset-execution-order", methods=["POST"])
@black_list_ip()
async def reset_execution_order():
    """Reset execution order to default (by creation date)"""
    try:
        async with aiosqlite.connect(DATABASE) as db:
            # Reset execution order for global scripts
            await db.execute(
                """
                UPDATE scripts 
                SET execution_order = (
                    SELECT ROW_NUMBER() OVER (ORDER BY created_at ASC)
                    FROM scripts s2 
                    WHERE s2.is_global = 1 AND s2.is_system = 0
                    AND s2.id = scripts.id
                )
                WHERE is_global = 1 AND is_system = 0
                """
            )
            
            # Reset execution order for user scripts
            await db.execute(
                """
                UPDATE scripts 
                SET execution_order = (
                    SELECT ROW_NUMBER() OVER (ORDER BY created_at ASC)
                    FROM scripts s2 
                    WHERE s2.is_global = 0 AND s2.is_system = 0
                    AND s2.id = scripts.id
                )
                WHERE is_global = 0 AND is_system = 0
                """
            )
            
            await db.commit()
        
        return jsonify({"status": "success", "message": "Execution order reset to default"})
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@settings_bp.route("/get-script-execution-order")
@black_list_ip()
async def get_script_execution_order():
    """Get current script execution order for display"""
    try:
        async with aiosqlite.connect(DATABASE) as db:
            db.row_factory = aiosqlite.Row
            
            # Get global scripts with execution order
            cursor = await db.execute(
                """
                SELECT id, name, autorun, startup, execution_order, created_at
                FROM scripts 
                WHERE is_global = 1 AND is_system = 0 
                ORDER BY execution_order ASC, created_at DESC
                """
            )
            global_scripts = await cursor.fetchall()
            
            # Get user scripts with execution order
            cursor = await db.execute(
                """
                SELECT s.id, s.name, s.autorun, s.startup, s.execution_order, s.created_at, u.pcname
                FROM scripts s
                JOIN user u ON s.user_id = u.id
                WHERE s.is_global = 0 AND s.is_system = 0 
                ORDER BY s.execution_order ASC, s.created_at DESC
                """
            )
            user_scripts = await cursor.fetchall()
            
            return jsonify({
                "status": "success",
                "global_scripts": [dict(s) for s in global_scripts],
                "user_scripts": [dict(s) for s in user_scripts]
            })
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


def register_settings_routes(app):
    """Register settings routes with the app"""
    app.register_blueprint(settings_bp)
    return app
