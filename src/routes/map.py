from quart import render_template, jsonify, current_app
import logging

from util.blacklist.ip_blacklist import black_list_ip
from util.db.user_queries import fetch_users_for_map
from util.system.stats import get_system_stats


def register_map_routes(app):
    """Register map routes with the app"""

    @app.route("/map")
    @black_list_ip()
    async def map_view():

        map_data = await fetch_users_for_map()
        current_app.logger.info(f"Fetched {len(map_data)} users for map")

        valid_coordinates = [
            user
            for user in map_data
            if user.get("latitude")
            and user.get("longitude")
            and isinstance(user.get("latitude"), (int, float))
            and isinstance(user.get("longitude"), (int, float))
        ]
        current_app.logger.info(
            f"Found {len(valid_coordinates)} users with valid coordinates"
        )

        system_stats = get_system_stats()

        total_users = len(map_data)

        return await render_template(
            "map.html",
            active_page="map",
            map_data=valid_coordinates,
            system_stats=system_stats,
            total_users=total_users,
        )

    @app.route("/api/map-data")
    @black_list_ip()
    async def map_data_api():
        """API endpoint for map data"""
        users = await fetch_users_for_map()

        valid_users = [
            user
            for user in users
            if user.get("latitude")
            and user.get("longitude")
            and isinstance(user.get("latitude"), (int, float))
            and isinstance(user.get("longitude"), (int, float))
        ]
        return jsonify(valid_users)

    return app
