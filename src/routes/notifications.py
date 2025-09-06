import aiosqlite
import aiohttp
import asyncio
import datetime
from quart import render_template, request, jsonify, redirect, url_for
from util.blacklist.ip_blacklist import black_list_ip
from config import DATABASE


def register_notification_routes(app):
    """Register notification routes with the app"""

    @app.route("/notifications")
    @black_list_ip()
    async def notifications_page():
        """Display notifications configuration page"""
        try:
            async with aiosqlite.connect(DATABASE) as db:
                db.row_factory = aiosqlite.Row
                
                # Get existing notification configurations
                cursor = await db.execute(
                    "SELECT * FROM notification_configs ORDER BY id DESC"
                )
                configs = await cursor.fetchall()
                
                # Convert Row objects to dictionaries for JSON serialization
                configs_list = []
                for config in configs:
                    configs_list.append({
                        'id': config['id'],
                        'type': config['type'],
                        'webhook_url': config['webhook_url'],
                        'bot_token': config['bot_token'],
                        'chat_id': config['chat_id'],
                        'is_enabled': config['is_enabled'],
                        'created_at': config['created_at'],
                        'updated_at': config['updated_at']
                    })
                
                return await render_template(
                    "notifications.html",
                    configs=configs_list,
                    active_page="notifications"
                )
        except Exception as e:
            print(f"Error loading notifications page: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/notifications/config", methods=["POST"])
    @black_list_ip()
    async def add_notification_config():
        """Add a new notification configuration"""
        try:
            data = await request.get_json()
            
            if not data:
                return jsonify({"status": "error", "message": "Invalid request data"}), 400
            
            notification_type = data.get("type")
            webhook_url = data.get("webhook_url", "")
            bot_token = data.get("bot_token", "")
            chat_id = data.get("chat_id", "")
            is_enabled = data.get("is_enabled", True)
            
            if not notification_type:
                return jsonify({"status": "error", "message": "Notification type is required"}), 400
            
            if notification_type == "discord" and not webhook_url:
                return jsonify({"status": "error", "message": "Discord webhook URL is required"}), 400
            
            if notification_type == "telegram" and (not bot_token or not chat_id):
                return jsonify({"status": "error", "message": "Telegram bot token and chat ID are required"}), 400
            
            async with aiosqlite.connect(DATABASE) as db:
                await db.execute(
                    """
                    INSERT INTO notification_configs 
                    (type, webhook_url, bot_token, chat_id, is_enabled, created_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    [notification_type, webhook_url, bot_token, chat_id, is_enabled]
                )
                await db.commit()
                
                return jsonify({
                    "status": "success", 
                    "message": f"{notification_type.title()} notification configuration added successfully"
                })
                
        except Exception as e:
            print(f"Error adding notification config: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/notifications/config/<int:config_id>", methods=["PUT"])
    @black_list_ip()
    async def update_notification_config(config_id):
        """Update an existing notification configuration"""
        try:
            data = await request.get_json()
            
            if not data:
                return jsonify({"status": "error", "message": "Invalid request data"}), 400
            
            webhook_url = data.get("webhook_url", "")
            bot_token = data.get("bot_token", "")
            chat_id = data.get("chat_id", "")
            is_enabled = data.get("is_enabled", True)
            
            async with aiosqlite.connect(DATABASE) as db:
                db.row_factory = aiosqlite.Row
                
                # Get current config to check type
                cursor = await db.execute(
                    "SELECT type FROM notification_configs WHERE id = ?", 
                    [config_id]
                )
                config = await cursor.fetchone()
                
                if not config:
                    return jsonify({"status": "error", "message": "Configuration not found"}), 404
                
                notification_type = config["type"]
                
                if notification_type == "discord" and not webhook_url:
                    return jsonify({"status": "error", "message": "Discord webhook URL is required"}), 400
                
                if notification_type == "telegram" and (not bot_token or not chat_id):
                    return jsonify({"status": "error", "message": "Telegram bot token and chat ID are required"}), 400
                
                await db.execute(
                    """
                    UPDATE notification_configs 
                    SET webhook_url = ?, bot_token = ?, chat_id = ?, is_enabled = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    [webhook_url, bot_token, chat_id, is_enabled, config_id]
                )
                await db.commit()
                
                return jsonify({
                    "status": "success", 
                    "message": f"{notification_type.title()} notification configuration updated successfully"
                })
                
        except Exception as e:
            print(f"Error updating notification config: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/notifications/config/<int:config_id>", methods=["DELETE"])
    @black_list_ip()
    async def delete_notification_config(config_id):
        """Delete a notification configuration"""
        try:
            async with aiosqlite.connect(DATABASE) as db:
                await db.execute(
                    "DELETE FROM notification_configs WHERE id = ?", 
                    [config_id]
                )
                await db.commit()
                
                return jsonify({
                    "status": "success", 
                    "message": "Notification configuration deleted successfully"
                })
                
        except Exception as e:
            print(f"Error deleting notification config: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/notifications/test/<int:config_id>", methods=["POST"])
    @black_list_ip()
    async def test_notification_config(config_id):
        """Test a notification configuration by sending a test message"""
        try:
            async with aiosqlite.connect(DATABASE) as db:
                db.row_factory = aiosqlite.Row
                
                cursor = await db.execute(
                    "SELECT * FROM notification_configs WHERE id = ?", 
                    [config_id]
                )
                config = await cursor.fetchone()
                
                if not config:
                    return jsonify({"status": "error", "message": "Configuration not found"}), 404
                
                if not config["is_enabled"]:
                    return jsonify({"status": "error", "message": "Configuration is disabled"}), 400
                
                # Send test notification
                success = await send_notification(
                    config["type"],
                    config["webhook_url"],
                    config["bot_token"],
                    config["chat_id"],
                    "🧪 Test Notification",
                    "This is a test notification from Cosmali. If you receive this, your notification configuration is working correctly!",
                    is_test=True
                )
                
                if success:
                    return jsonify({
                        "status": "success", 
                        "message": "Test notification sent successfully"
                    })
                else:
                    return jsonify({
                        "status": "error", 
                        "message": "Failed to send test notification. Check your configuration."
                    }), 500
                
        except Exception as e:
            print(f"Error testing notification config: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    return app


async def send_notification(notification_type, webhook_url, bot_token, chat_id, title, message, is_test=False):
    """Send a notification via Discord webhook or Telegram bot"""
    try:
        if notification_type == "discord":
            return await send_discord_notification(webhook_url, title, message, is_test)
        elif notification_type == "telegram":
            return await send_telegram_notification(bot_token, chat_id, title, message, is_test)
        else:
            print(f"Unknown notification type: {notification_type}")
            return False
    except Exception as e:
        print(f"Error sending notification: {e}")
        return False


async def send_discord_notification(webhook_url, title, message, is_test=False):
    """Send notification to Discord webhook"""
    try:
        embed = {
            "title": title,
            "description": message,
            "color": 0x00ff00 if is_test else 0xff6b35,  # Green for test, orange for real
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "footer": {
                "text": "Cosmali" + (" - Test" if is_test else "")
            }
        }
        
        payload = {
            "embeds": [embed]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as response:
                return response.status == 204  # Discord returns 204 on success
                
    except Exception as e:
        print(f"Error sending Discord notification: {e}")
        return False


async def send_telegram_notification(bot_token, chat_id, title, message, is_test=False):
    """Send notification to Telegram bot"""
    try:
        bot_api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        full_message = f"**{title}**\n\n{message}"
        if is_test:
            full_message += "\n\n🧪 This is a test notification."
        
        payload = {
            "chat_id": chat_id,
            "text": full_message,
            "parse_mode": "Markdown"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(bot_api_url, json=payload) as response:
                result = await response.json()
                return result.get("ok", False)
                
    except Exception as e:
        print(f"Error sending Telegram notification: {e}")
        return False


async def send_agent_join_notification(agent_info):
    """Send notification when a new agent joins or rejoins"""
    try:
        async with aiosqlite.connect(DATABASE) as db:
            db.row_factory = aiosqlite.Row
            
            # Get all enabled notification configurations
            cursor = await db.execute(
                "SELECT * FROM notification_configs WHERE is_enabled = 1"
            )
            configs = await cursor.fetchall()
            
            if not configs:
                return  # No notifications configured
            
            # Determine notification type and message
            is_new = agent_info.get('is_new', True)
            was_deleted = agent_info.get('was_deleted', False)
            
            if was_deleted:
                # Agent was previously removed and is rejoining
                title = "🔄 Agent Rejoined"
                message = f"""
**Agent Rejoined After Removal:**
• **Hostname:** {agent_info.get('hostname', 'Unknown')}
• **IP Address:** {agent_info.get('ip_address', 'Unknown')}
• **Country:** {agent_info.get('country', 'Unknown')}
• **Elevated Status:** {agent_info.get('elevated_status', 'Unknown')}
• **HWID:** `{agent_info.get('hwid', 'Unknown')}`

**Status:** Previously removed agent has rejoined the network
**Connection Time:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

⚠️ **Note:** This agent was previously marked for deletion and has now reconnected.
            """.strip()
            else:
                # Completely new agent
                title = "🆕 New Agent Connected"
                message = f"""
**New Agent Connected:**
• **Hostname:** {agent_info.get('hostname', 'Unknown')}
• **IP Address:** {agent_info.get('ip_address', 'Unknown')}
• **Country:** {agent_info.get('country', 'Unknown')}
• **Elevated Status:** {agent_info.get('elevated_status', 'Unknown')}
• **HWID:** `{agent_info.get('hwid', 'Unknown')}`

**Status:** First-time connection to the network
**Connection Time:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
            """.strip()
            
            # Send notifications to all configured channels
            notification_tasks = []
            for config in configs:
                task = send_notification(
                    config["type"],
                    config["webhook_url"],
                    config["bot_token"],
                    config["chat_id"],
                    title,
                    message,
                    is_test=False
                )
                notification_tasks.append(task)
            
            # Execute all notifications concurrently
            if notification_tasks:
                await asyncio.gather(*notification_tasks, return_exceptions=True)
                
    except Exception as e:
        print(f"Error sending agent join notification: {e}")



