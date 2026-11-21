from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    employee_code = db.Column(db.String(30), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="employee")  # admin | employee
    active = db.Column(db.Boolean, default=True)
    gender = db.Column(db.String(1))  # M | F
    dob = db.Column(db.Date)
    position = db.Column(db.String(80))
    photo = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.now)
    department = db.Column(db.String(80))
    device_id = db.Column(db.String(64))
    telegram_chat_id = db.Column(db.String(32))
    tg_code = db.Column(db.String(10))
    tg_code_exp = db.Column(db.DateTime)

    def to_dict(self):
        return dict(id=self.id, employee_code=self.employee_code, name=self.name, role=self.role, active=bool(self.active),
                    department=self.department, telegram_linked=bool(self.telegram_chat_id), device_bound=bool(self.device_id),
                    gender=self.gender, dob=self.dob.isoformat() if self.dob else None,
                    position=self.position,
                    joined=self.created_at.date().isoformat() if self.created_at else None, photo=f"/api/uploads/{self.photo}" if self.photo else None)


class Attendance(db.Model):
    __tablename__ = "attendance"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    check_in = db.Column(db.DateTime)
    check_out = db.Column(db.DateTime)
    check_in2 = db.Column(db.DateTime)   # afternoon in
    check_out2 = db.Column(db.DateTime)  # afternoon out
    note = db.Column(db.String(255))     # set when an admin edits the record
    status = db.Column(db.String(10), default="present")  # present | late
    user = db.relationship("User")
    __table_args__ = (db.UniqueConstraint("user_id", "date"),)


class LeaveRequest(db.Model):
    __tablename__ = "leave_requests"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    leave_type = db.Column(db.String(20))  # Sick | Personal | Annual
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text)
    attachment = db.Column(db.String(255))
    status = db.Column(db.String(10), default="Pending")  # Pending | Approved | Rejected
    created_at = db.Column(db.DateTime, default=datetime.now)
    user = db.relationship("User")

    def to_dict(self):
        return dict(id=self.id, user=self.user.name, code=self.user.employee_code,
                    leave_type=self.leave_type, start_date=self.start_date.isoformat(),
                    end_date=self.end_date.isoformat(), reason=self.reason,
                    attachment=f"/api/uploads/{self.attachment}" if self.attachment else None,
                    status=self.status, created_at=self.created_at.strftime("%Y-%m-%d %H:%M"))


class QRToken(db.Model):
    __tablename__ = "qr_tokens"
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), index=True)
    created_at = db.Column(db.DateTime, default=datetime.now)


class SystemSetting(db.Model):
    __tablename__ = "system_settings"
    k = db.Column(db.String(50), primary_key=True)
    v = db.Column(db.String(255))


class Holiday(db.Model):
    __tablename__ = "holidays"
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    name = db.Column(db.String(120))


class Location(db.Model):
    __tablename__ = "locations"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    lat = db.Column(db.Float)        # (unused since the switch from GPS to WiFi check)
    lng = db.Column(db.Float)
    radius_m = db.Column(db.Integer, default=150)
    wifi_ips = db.Column(db.Text)    # public IPs / CIDR ranges of this location's WiFi, one per line
    active = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return dict(id=self.id, name=self.name, wifi_ips=self.wifi_ips or "", active=bool(self.active))


class ScanLog(db.Model):
    __tablename__ = "scan_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    ts = db.Column(db.DateTime, default=datetime.now)
    slot = db.Column(db.String(5))
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"))
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    distance_m = db.Column(db.Float)
    device_id = db.Column(db.String(64))
    selfie = db.Column(db.String(255))
    ip = db.Column(db.String(64))
    user = db.relationship("User")
    location = db.relationship("Location")


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    date = db.Column(db.Date)
    action = db.Column(db.String(40))
    detail = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    admin = db.relationship("User", foreign_keys=[admin_id])
    user = db.relationship("User", foreign_keys=[user_id])


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(120))
    body = db.Column(db.Text)
    key = db.Column(db.String(80), index=True)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)


class ScanEvent(db.Model):
    """A scan attempt that was refused because the person already scanned (announced by the station)."""
    __tablename__ = "scan_events"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    ts = db.Column(db.DateTime, default=datetime.now)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"))
    kind = db.Column(db.String(10), default="dup")
    user = db.relationship("User")
