"""
Startup preflight check — run before starting the Flask server.
Validates Python packages, database connection, and app import.
"""
import os
import sys

from dotenv import load_dotenv


def main():
    load_dotenv()
    print("  [preflight] Checking packages...")
    try:
        import flask  # noqa: F401
        import flask_login  # noqa: F401
        import pymysql  # noqa: F401
    except ImportError as exc:
        print(f"  [FAIL] Missing package: {exc}")
        print("  Run: pip install -r requirements.txt")
        return 1

    print("  [preflight] Checking database...")
    try:
        import pymysql
        conn = pymysql.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', '3306')),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'cognitive_monitoring_db'),
            connect_timeout=5,
        )
        conn.close()
    except Exception as exc:
        print(f"  [FAIL] Database: {exc}")
        print("  Start XAMPP MySQL, then run: python init_db.py")
        return 1

    print("  [preflight] Applying migrations...")
    try:
        from app import create_app, db
        from app.utils.migrations import run_migrations
        app = create_app('development')
        with app.app_context():
            run_migrations()
    except Exception as exc:
        print(f"  [FAIL] Migration error: {exc}")
        return 1

    print("  [preflight] Loading application...")
    try:
        from app import create_app
        create_app('development')
    except Exception as exc:
        print(f"  [FAIL] App error: {exc}")
        return 1

    print("  [OK] Preflight passed — starting server...")
    return 0


if __name__ == '__main__':
    sys.exit(main())
