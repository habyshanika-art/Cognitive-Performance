"""
Flask Application Factory
-------------------------
Creates and configures the Flask application instance.
Registers blueprints, extensions, and error handlers.
Follows MVC architecture pattern.
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

from app.config import config_by_name

# Initialize extensions (bound to app in create_app)
db = SQLAlchemy()
login_manager = LoginManager()


def create_app(config_name='default'):
    """
    Application factory function.
    Args:
        config_name: 'development', 'production', or 'default'
    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')

    # Load configuration
    app.config.from_object(config_by_name[config_name])

    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'
    login_manager.remember_cookie_duration = app.config.get('REMEMBER_COOKIE_DURATION')

    # Import models so SQLAlchemy knows about them
    from app.models import user, role, session, task, interaction_data
    from app.models import cognitive_metrics, aggregated_metrics, alert
    from app.models import publication, feedback_request, feedback, notification
    from app.models import analytics_report, system_log, system_settings
    from app.models import email_message

    # User loader for Flask-Login
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints (controllers) - expanded in later modules
    from app.controllers.main_controller import main_bp
    from app.controllers.auth_controller import auth_bp
    from app.controllers.user_controller import user_bp
    from app.controllers.researcher_controller import researcher_bp
    from app.controllers.admin_controller import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)  # /login, /register, /logout (no /auth prefix)
    app.register_blueprint(user_bp)
    app.register_blueprint(researcher_bp)
    app.register_blueprint(admin_bp)

    # Allow browser API tester / Postman-style HTML (file:// or other origins) in development
    @app.after_request
    def add_cors_headers(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Expose-Headers'] = 'Location, Content-Type'
        return response

    @app.before_request
    def handle_cors_preflight():
        from flask import request, make_response
        if request.method == 'OPTIONS':
            return make_response('', 204)

    @app.before_request
    def check_maintenance_mode():
        """Block non-admin access when maintenance mode is enabled."""
        from flask import request, redirect, url_for, flash
        from flask_login import current_user
        from app.utils.helpers import is_maintenance_mode

        if not is_maintenance_mode():
            return

        allowed_endpoints = {
            'auth.login', 'auth.logout', 'auth.forgot_password',
            'auth.verify_email', 'auth.register', 'static',
            'admin.dashboard', 'admin.settings',
        }
        if request.endpoint in allowed_endpoints:
            return
        if request.endpoint and request.endpoint.startswith('admin.'):
            return
        if current_user.is_authenticated and current_user.is_admin():
            return

        # Avoid login ↔ dashboard redirect loop for logged-in non-admins
        if current_user.is_authenticated:
            logout_needed = True
        else:
            logout_needed = False

        flash('The system is under maintenance. Please try again later.', 'warning')
        if logout_needed:
            from flask_login import logout_user
            logout_user()
        return redirect(url_for('auth.login'))

    # Create upload folder and database tables (development helper)
    import os
    with app.app_context():
        os.makedirs(app.config.get('UPLOAD_FOLDER', ''), exist_ok=True)
        db.create_all()
        from app.utils.migrations import run_migrations
        run_migrations()

    return app
