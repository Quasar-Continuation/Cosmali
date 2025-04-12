from quart import render_template

from util.blacklist.ip_blacklist import black_list_ip


def register_user_routes(app):
    """Register user routes with the app"""

    @app.route("/profile")
    @black_list_ip()
    async def profile():
        return await render_template("profile.html", active_page="profile")

    @app.route("/settings")
    @black_list_ip()
    async def settings():
        return await render_template("settings.html", active_page="settings")

    return app
