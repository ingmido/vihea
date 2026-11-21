import os
from datetime import timedelta
from dotenv import load_dotenv
load_dotenv()
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from werkzeug.security import generate_password_hash
from apscheduler.schedulers.background import BackgroundScheduler
from models import db, User, Location


def ensure_database(uri):
    """Create the MySQL database automatically if it does not exist yet."""
    from sqlalchemy.engine import make_url
    import pymysql
    u = make_url(uri)
    if not u.drivername.startswith("mysql"):
        return
    conn = pymysql.connect(host=u.host or "localhost", port=u.port or 3306,
                           user=u.username or "root", password=u.password or "")
    with conn.cursor() as c:
        c.execute(f"CREATE DATABASE IF NOT EXISTS `{u.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    conn.commit(); conn.close()


def ensure_columns():
    """Add new columns to existing tables (create_all does not alter tables)."""
    from sqlalchemy import inspect, text
    wanted = {
        "users": (("gender", "VARCHAR(1)"), ("dob", "DATE"), ("position", "VARCHAR(80)"),
                  ("photo", "VARCHAR(255)"), ("created_at", "DATETIME"), ("department", "VARCHAR(80)"),
                  ("device_id", "VARCHAR(64)"), ("telegram_chat_id", "VARCHAR(32)"),
                  ("tg_code", "VARCHAR(10)"), ("tg_code_exp", "DATETIME")),
        "attendance": (("check_in2", "DATETIME"), ("check_out2", "DATETIME"), ("note", "VARCHAR(255)")),
        "locations": (("wifi_ips", "TEXT"),),
        "scan_logs": (("ip", "VARCHAR(64)"),),
    }
    insp = inspect(db.engine)
    for table, cols in wanted.items():
        have = {c["name"] for c in insp.get_columns(table)}
        for name, ddl in cols:
            if name not in have:
                db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN `{name}` {ddl} NULL"))
    db.session.commit()


def create_app():
    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "mysql+pymysql://root:@localhost/moeys_attendance?charset=utf8mb4"),
        JWT_SECRET_KEY=os.getenv("JWT_SECRET", "dev-secret-change-me-please-32chars!"),
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(hours=12),
        QR_SECRET=os.getenv("QR_SECRET", "dev-qr-secret"),
        UPLOAD_DIR=os.path.join(os.path.dirname(__file__), "uploads"),
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
    )
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)
    CORS(app)
    JWTManager(app)
    db.init_app(app)
    from routes import api, check_and_alert, absent_notice
    from routes2 import api2, reminders_job, summary_job, poll_telegram
    app.register_blueprint(api)
    app.register_blueprint(api2)

    ensure_database(app.config["SQLALCHEMY_DATABASE_URI"])
    with app.app_context():
        db.create_all()
        ensure_columns()
        from models import SystemSetting
        import telegram_service
        saved = db.session.get(SystemSetting, "telegram_chat_id")
        telegram_service.configure(saved.v if saved else None)
        if not Location.query.first():
            db.session.add(Location(name="ការិយាល័យកណ្ដាល", radius_m=150)); db.session.commit()
        if not User.query.filter_by(role="admin").first():
            db.session.add(User(employee_code="admin", name="អ្នកគ្រប់គ្រង",
                                password_hash=generate_password_hash("admin123"), role="admin"))
            db.session.commit()

    def job():
        with app.app_context():
            check_and_alert()
    def save_migrated_chat(new_id):
        with app.app_context():
            from routes import set_setting
            set_setting("telegram_chat_id", new_id)
    import telegram_service
    telegram_service.ON_MIGRATE = save_migrated_chat

    def tick():
        with app.app_context():
            absent_notice()
    sched = BackgroundScheduler(timezone="Asia/Phnom_Penh")
    sched.add_job(job, "cron", day_of_week="mon-fri", hour=10, minute=0)
    def wrap(fn):
        def run():
            with app.app_context():
                try: fn()
                except Exception as e: print("job error:", fn.__name__, e)
        return run
    sched.add_job(tick, "interval", minutes=1)
    sched.add_job(wrap(reminders_job), "interval", minutes=1)
    sched.add_job(wrap(summary_job), "interval", minutes=5)
    sched.add_job(wrap(poll_telegram), "interval", seconds=10, max_instances=1)
    sched.start()
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=os.getenv("FLASK_DEBUG") == "1", use_reloader=False)  # never debug when exposed via a tunnel
