from quart import Blueprint, render_template
import aiosqlite
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from config import DATABASE
from util.system.stats import get_system_stats
from util.blacklist.ip_blacklist import black_list_ip

# Create a Blueprint for statistics routes
statistics_bp = Blueprint("statistics", __name__)


@statistics_bp.route("/statistics")
@black_list_ip()
async def statistics_page():
    """Display statistics about clients and system"""

    system_stats = get_system_stats()

    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT COUNT(*) as total FROM user")
        total_users = (await cursor.fetchone())["total"]

        cursor = await db.execute(
            "SELECT COUNT(*) as active FROM user WHERE is_active = 1"
        )
        active_users = (await cursor.fetchone())["active"]

        cursor = await db.execute(
            "SELECT country, COUNT(*) as count FROM user WHERE country IS NOT NULL GROUP BY country ORDER BY count DESC"
        )
        country_data = await cursor.fetchall()
        country_stats = [
            {"name": row["country"], "count": row["count"]} for row in country_data
        ]

        total_with_country = sum(item["count"] for item in country_stats)
        if total_with_country > 0:
            for item in country_stats:
                item["percentage"] = round(
                    (item["count"] / total_with_country) * 100, 1
                )

        today = datetime.now()
        two_weeks_ago = today - timedelta(days=14)
        two_weeks_ago_str = two_weeks_ago.strftime("%Y-%m-%d")

        cursor = await db.execute(
            "SELECT date(first_ping) as date, COUNT(*) as count FROM user "
            "WHERE date(first_ping) >= ? GROUP BY date(first_ping) ORDER BY date(first_ping)",
            [two_weeks_ago_str],
        )
        registration_data = await cursor.fetchall()

        date_counts = {row["date"]: row["count"] for row in registration_data}
        registration_trend = []

        for i in range(14):
            date_key = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            registration_trend.append(
                {"date": date_key, "count": date_counts.get(date_key, 0)}
            )

        registration_trend.reverse()

        active_inactive = [
            {
                "name": "Active",
                "count": active_users,
                "percentage": (
                    round(active_users / total_users * 100, 1) if total_users > 0 else 0
                ),
            },
            {
                "name": "Inactive",
                "count": total_users - active_users,
                "percentage": (
                    round((total_users - active_users) / total_users * 100, 1)
                    if total_users > 0
                    else 0
                ),
            },
        ]

        cursor = await db.execute("SELECT COUNT(*) as total FROM scripts")
        total_scripts = (await cursor.fetchone())["total"]

        cursor = await db.execute(
            "SELECT COUNT(*) as executed FROM scripts WHERE executed = 1"
        )
        executed_scripts = (await cursor.fetchone())["executed"]

        script_execution = [
            {
                "name": "Executed",
                "count": executed_scripts,
                "percentage": (
                    round(executed_scripts / total_scripts * 100, 1)
                    if total_scripts > 0
                    else 0
                ),
            },
            {
                "name": "Pending",
                "count": total_scripts - executed_scripts,
                "percentage": (
                    round((total_scripts - executed_scripts) / total_scripts * 100, 1)
                    if total_scripts > 0
                    else 0
                ),
            },
        ]

    return await render_template(
        "statistics.html",
        active_page="statistics",
        system_stats=system_stats,
        total_users=total_users,
        active_users=active_users,
        country_stats=country_stats,
        registration_trend=registration_trend,
        active_inactive=active_inactive,
        script_execution=script_execution,
        total_scripts=total_scripts,
    )


def register_statistics_routes(app):
    """Register statistics routes with the app"""
    app.register_blueprint(statistics_bp)
    return app
