import os

from flask import Flask, jsonify
from flask_cors import CORS
from flask_migrate import Migrate
from sqlalchemy.exc import SQLAlchemyError

from backend.config import Config
from backend.database import db
from backend.routes import api_bp


def _cors_origins(value: str):
    return [origin.strip() for origin in value.split(",") if origin.strip()]


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config["JSON_SORT_KEYS"] = False
    config_class.validate()

    CORS(
        app,
        resources={r"/api/*": {"origins": _cors_origins(app.config["CORS_ORIGINS"])}},
        supports_credentials=False,
    )

    db.init_app(app)
    migrate = Migrate()
    migrate.init_app(app, db)
    app.extensions["migrate"] = migrate
    app.register_blueprint(api_bp)

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({"error": "Bad Request", "message": str(getattr(error, "description", error))}), 400

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": "Resource Not Found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify({"error": "Method Not Allowed"}), 405

    @app.errorhandler(SQLAlchemyError)
    def database_error(_error):
        db.session.rollback()
        app.logger.exception("Database request failed")
        return jsonify({"error": "Database request failed", "message": "The request could not be completed."}), 500

    @app.errorhandler(Exception)
    def internal_error(_error):
        db.session.rollback()
        app.logger.exception("Unhandled application error")
        return jsonify({"error": "Internal Server Error", "message": "The server could not complete the request."}), 500

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
