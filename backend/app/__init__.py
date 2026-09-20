import logging

from flask import Flask


def create_app() -> Flask:
    logging.basicConfig(level=logging.INFO)

    app = Flask(__name__)

    from app.routes.health import bp as health_bp
    from app.routes.search import bp as search_bp
    from app.routes.watches import bp as watches_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(watches_bp)

    return app
