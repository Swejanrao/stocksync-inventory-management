import os

from pathlib import Path
from dotenv import load_dotenv

from flask import Flask, jsonify, render_template

from .extensions import db, cors, migrate


BASE_DIR = Path(__file__).resolve().parent.parent


def create_app(test_config=None):

    load_dotenv(BASE_DIR / ".env")

    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static")
    )

    app.config["SECRET_KEY"] = os.getenv(
        "SECRET_KEY",
        "development-secret-change-this"
    )

    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL",
        "sqlite:///stocksync.db"
    )

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    cors.init_app(app)
    migrate.init_app(app, db)

    from .routes.api import api_bp

    app.register_blueprint(
        api_bp,
        url_prefix="/api"
    )

    from .cli import register_commands

    register_commands(app)

    @app.route("/")
    def home():
        return render_template("index.html")

    @app.route("/health")
    def health():
        return jsonify({
            "status": "success",
            "application": "StockSync",
            "message": "API is running"
        })

    return app
