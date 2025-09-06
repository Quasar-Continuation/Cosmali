from .dashboard import register_dashboard_routes
from .map import register_map_routes
from .user import register_user_routes
from .client_api import register_client_routes
from .script_routes import register_script_routes
from .statistics import register_statistics_routes
from .builder import builder_bp
from .groups import register_group_routes


def register_all_routes(app):
    """Register all application routes"""
    app = register_dashboard_routes(app)
    app = register_map_routes(app)
    app = register_user_routes(app)
    app = register_client_routes(app)
    app = register_script_routes(app)
    app = register_statistics_routes(app)
    app = register_group_routes(app)

    # Builder Blueprint
    app.register_blueprint(builder_bp)

    return app
