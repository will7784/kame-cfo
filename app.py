import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Por favor inicia sesión para acceder."

    from routes.auth import bp as auth_bp
    from routes.companies import bp as companies_bp
    from routes.ledger import bp as ledger_bp
    from routes.reports import bp as reports_bp
    from routes.main import bp as main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(companies_bp)
    app.register_blueprint(ledger_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(main_bp)

    @login_manager.user_loader
    def load_user(user_id):
        from models.user import User
        return User.query.get(int(user_id))

    with app.app_context():
        from models.user import User
        from models.company import Company
        from models.ledger import LedgerEntry
        from models.account_review import AccountReview
        try:
            db.create_all()
            if not User.query.first():
                from werkzeug.security import generate_password_hash
                admin = User(username="will", password_hash=generate_password_hash("7784"))
                db.session.add(admin)
                db.session.commit()
        except Exception as e:
            app.logger.warning(f"No se pudo conectar a la base de datos al arrancar: {e}")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
