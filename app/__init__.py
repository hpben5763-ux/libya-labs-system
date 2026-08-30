import os
from datetime import datetime, date
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


# =========================
# المستخدمون
# =========================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), default="viewer")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check(self, password):
        return check_password_hash(self.password_hash, password)


# =========================
# المرافق
# =========================

class Facility(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    facility_type = db.Column(db.String(120))
    region = db.Column(db.String(120))
    municipality = db.Column(db.String(120))
    city = db.Column(db.String(120))
    address = db.Column(db.String(255))
    phone = db.Column(db.String(80))
    manager = db.Column(db.String(160))
    status = db.Column(db.String(40), default="نشط")
    notes = db.Column(db.Text)


# =========================
# المختبرات
# =========================

class Laboratory(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    facility_id = db.Column(
        db.Integer,
        db.ForeignKey("facility.id", ondelete="CASCADE")
    )

    name = db.Column(db.String(200), nullable=False)
    laboratory_type = db.Column(db.String(120))
    level = db.Column(db.String(100))

    region = db.Column(db.String(120))
    municipality = db.Column(db.String(120))
    city = db.Column(db.String(120))
    address = db.Column(db.String(255))

    manager = db.Column(db.String(160))
    phone = db.Column(db.String(80))

    status = db.Column(db.String(40), default="نشط")

    established_date = db.Column(db.Date)
    notes = db.Column(db.Text)


# =========================
# العاملون
# =========================

class Staff(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    facility_id = db.Column(
        db.Integer,
        db.ForeignKey("facility.id", ondelete="CASCADE")
    )

    name = db.Column(db.String(180), nullable=False)
    job_title = db.Column(db.String(150))
    specialty = db.Column(db.String(150))
    qualification = db.Column(db.String(150))
    phone = db.Column(db.String(80))
    status = db.Column(db.String(50))


# =========================
# الأجهزة
# =========================

class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    facility_id = db.Column(
        db.Integer,
        db.ForeignKey("facility.id", ondelete="CASCADE")
    )

    name = db.Column(db.String(180), nullable=False)
    category = db.Column(db.String(120))
    manufacturer = db.Column(db.String(120))
    model = db.Column(db.String(120))
    serial_no = db.Column(db.String(150))
    status = db.Column(db.String(80))
    purchase_year = db.Column(db.String(20))
    notes = db.Column(db.Text)


# =========================
# الكواشف
# =========================

class Reagent(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    facility_id = db.Column(
        db.Integer,
        db.ForeignKey("facility.id", ondelete="CASCADE")
    )

    name = db.Column(db.String(180), nullable=False)
    manufacturer = db.Column(db.String(120))
    lot_no = db.Column(db.String(100))
    expiry = db.Column(db.Date)
    quantity = db.Column(db.String(60))
    unit = db.Column(db.String(60))
    status = db.Column(db.String(80))


# =========================
# مصارف الدم
# =========================

class BloodBank(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    facility_id = db.Column(
        db.Integer,
        db.ForeignKey("facility.id", ondelete="CASCADE")
    )

    name = db.Column(db.String(180), nullable=False)
    blood_bank_type = db.Column(db.String(120))
    capacity = db.Column(db.String(100))
    manager = db.Column(db.String(160))
    phone = db.Column(db.String(80))
    status = db.Column(db.String(60))
    notes = db.Column(db.Text)


# =========================
# إنشاء التطبيق
# =========================

def create_app():

    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.getenv(
        "SECRET_KEY",
        "change-this-secret-in-production"
    )

    uri = os.getenv(
        "DATABASE_URL",
        "sqlite:///laboratories.db"
    )

    if uri.startswith("postgres://"):
        uri = uri.replace(
            "postgres://",
            "postgresql+psycopg://",
            1
        )

    elif uri.startswith("postgresql://"):
        uri = uri.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1
        )

    app.config["SQLALCHEMY_DATABASE_URI"] = uri
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    # إنشاء الجداول
    with app.app_context():

        db.create_all()

        # إنشاء المدير الافتراضي إذا لم يكن موجودًا
        if not User.query.filter_by(username="admin").first():

            user = User(
                username="admin",
                role="admin"
            )

            user.set_password("admin123")

            db.session.add(user)
            db.session.commit()


    # =========================
    # نظام الصلاحيات
    # =========================

    def login_required(function):

        @wraps(function)
        def wrapper(*args, **kwargs):

            if "user_id" not in session:
                return redirect(url_for("login"))

            return function(*args, **kwargs)

        return wrapper


    def role_required(*roles):

        def decorator(function):

            @wraps(function)
            def wrapper(*args, **kwargs):

                if "user_id" not in session:
                    return redirect(url_for("login"))

                if session.get("role") not in roles:

                    flash(
                        "ليس لديك صلاحية لتنفيذ هذه العملية",
                        "danger"
                    )

                    return redirect(
                        request.referrer or
                        url_for("dashboard")
                    )

                return function(*args, **kwargs)

            return wrapper

        return decorator


    # =========================
    # تسجيل الدخول
    # =========================

    @app.route("/login", methods=["GET", "POST"])
    def login():

        if request.method == "POST":

            username = request.form.get(
                "username",
                ""
            ).strip()

            password = request.form.get(
                "password",
                ""
            )

            user = User.query.filter_by(
                username=username
            ).first()

            if user and user.check(password):

                session["user_id"] = user.id
                session["role"] = user.role
                session["username"] = user.username

                return redirect(
                    url_for("dashboard")
                )

            flash(
                "بيانات الدخول غير صحيحة",
                "danger"
            )

        return render_template("login.html")


    # =========================
    # تسجيل الخروج
    # =========================

    @app.route("/logout")
    def logout():

        session.clear()

        return redirect(
            url_for("login")
        )


    # =========================
    # تعريف الأقسام
    # =========================

    configs = {

        "facilities": (
            Facility,
            "المرافق",
            [
                "name",
                "facility_type",
                "region",
                "municipality",
                "city",
                "phone",
                "manager",
                "status"
            ]
        ),

        "laboratories": (
            Laboratory,
            "المختبرات",
            [
                "name",
                "laboratory_type",
                "level",
                "region",
                "municipality",
                "city",
                "phone",
                "manager",
                "status",
                "established_date"
            ]
        ),

        "staff": (
            Staff,
            "العاملين",
            [
                "name",
                "job_title",
                "specialty",
                "qualification",
                "phone",
                "status"
            ]
        ),

        "devices": (
            Device,
            "الأجهزة",
            [
                "name",
                "category",
                "manufacturer",
                "model",
                "serial_no",
                "status"
            ]
        ),

        "reagents": (
            Reagent,
            "الكواشف",
            [
                "name",
                "manufacturer",
                "lot_no",
                "expiry",
                "quantity",
                "unit",
                "status"
            ]
        ),

        "blood_banks": (
            BloodBank,
            "مصارف الدم",
            [
                "name",
                "blood_bank_type",
                "capacity",
                "manager",
                "phone",
                "status"
            ]
        )
    }


    # =========================
    # أسماء الحقول بالعربي
    # =========================

    labels = {

        "name": "الاسم",
        "facility_type": "نوع المرفق",

        "laboratory_type": "نوع المختبر",
        "level": "مستوى المختبر",

        "region": "المنطقة",
        "municipality": "البلدية",
        "city": "المدينة",
        "address": "العنوان",

        "phone": "الهاتف",
        "manager": "المسؤول / المدير",

        "status": "الحالة",

        "established_date": "تاريخ التأسيس",

        "job_title": "المسمى الوظيفي",
        "specialty": "التخصص",
        "qualification": "المؤهل",

        "category": "الفئة",
        "manufacturer": "الشركة المصنعة",
        "model": "الموديل",
        "serial_no": "الرقم التسلسلي",
        "purchase_year": "سنة الشراء",

        "lot_no": "رقم التشغيلة",
        "expiry": "تاريخ الانتهاء",

        "quantity": "الكمية",
        "unit": "الوحدة",

        "blood_bank_type": "نوع مصرف الدم",
        "capacity": "السعة",

        "notes": "ملاحظات"
    }


    @app.context_processor
    def inject_globals():

        return {
            "field_labels": labels
        }


    # =========================
    # الرئيسية
    # =========================

    @app.route("/")
    @login_required
    def dashboard():

        exp = Reagent.query.filter(
            Reagent.expiry.isnot(None)
        ).all()

        today = date.today()

        exp_count = sum(
            1
            for reagent in exp
            if (reagent.expiry - today).days <= 60
        )

        counts = {

            "facilities":
                Facility.query.count(),

            "laboratories":
                Laboratory.query.count(),

            "staff":
                Staff.query.count(),

            "devices":
                Device.query.count(),

            "reagents":
                Reagent.query.count(),

            "blood_banks":
                BloodBank.query.count()
        }

        return render_template(
            "dashboard.html",
            counts=counts,
            exp_count=exp_count
        )


    # =========================
    # عرض البيانات
    # =========================

    @app.route("/data/<kind>")
    @login_required
    def data_list(kind):

        if kind not in configs:
            return redirect(
                url_for("dashboard")
            )

        model, label, cols = configs[kind]

        q = request.args.get(
            "q",
            ""
        ).strip()

        rows = model.query.order_by(
            model.id.desc()
        ).all()

        if q:

            rows = [

                row for row in rows

                if q.lower()
                in
                " ".join(
                    str(
                        getattr(
                            row,
                            column,
                            ""
                        )
                    )

                    for column in cols
                ).lower()
            ]

        return render_template(
            "list.html",
            kind=kind,
            label=label,
            cols=cols,
            rows=rows
        )


    # =========================
    # ملف المرفق
    # =========================

    @app.route("/facility/<int:fid>")
    @login_required
    def facility(fid):

        facility = Facility.query.get_or_404(fid)

        return render_template(

            "facility.html",

            f=facility,

            laboratories=
                Laboratory.query.filter_by(
                    facility_id=fid
                ).all(),

            staff=
                Staff.query.filter_by(
                    facility_id=fid
                ).all(),

            devices=
                Device.query.filter_by(
                    facility_id=fid
                ).all(),

            reagents=
                Reagent.query.filter_by(
                    facility_id=fid
                ).all(),

            blood_banks=
                BloodBank.query.filter_by(
                    facility_id=fid
                ).all()
        )


    # =========================
    # حفظ الحقول
    # =========================

    def save_fields(obj, cols):

        for column in cols:

            value = request.form.get(
                column,
                ""
            ).strip()

            if column in (
                "expiry",
                "established_date"
            ):

                value = (
                    datetime.strptime(
                        value,
                        "%Y-%m-%d"
                    ).date()
                    if value
                    else None
                )

            setattr(
                obj,
                column,
                value
            )


    # =========================
    # إضافة
    # =========================

 # =========================
    # إضافة سجل جديد
    # =========================

    @app.route(
        "/new/<kind>",
        methods=["GET", "POST"]
    )
    @login_required
    @role_required(
        "admin",
        "editor"
    )
    def new(kind):

        if kind not in configs:
            return redirect(
                url_for("dashboard")
            )

        model, label, cols = configs[kind]

        # المرفق الذي جاء منه المستخدم
        preselected_facility = request.args.get(
            "facility_id",
            type=int
        )

        if request.method == "POST":

            obj = model()

            save_fields(
                obj,
                cols
            )

            # جميع الأقسام ما عدا المرافق مرتبطة بمرفق
            if kind != "facilities":

                facility_id = request.form.get(
                    "facility_id",
                    type=int
                )

                if not facility_id:

                    flash(
                        "يرجى اختيار المرفق",
                        "danger"
                    )

                    return redirect(
                        url_for(
                            "new",
                            kind=kind
                        )
                    )

                # التأكد أن المرفق موجود
                facility = Facility.query.get(
                    facility_id
                )

                if not facility:

                    flash(
                        "المرفق المحدد غير موجود",
                        "danger"
                    )

                    return redirect(
                        url_for(
                            "new",
                            kind=kind
                        )
                    )

                obj.facility_id = facility_id

            db.session.add(obj)

            db.session.commit()

            flash(
                "تم الحفظ بنجاح",
                "success"
            )

            # إذا تمت الإضافة من داخل ملف المرفق
            # نرجع مباشرة إلى ملف المرفق
            if (
                kind != "facilities"
                and preselected_facility
            ):

                return redirect(
                    url_for(
                        "facility",
                        fid=preselected_facility
                    )
                )

            return redirect(
                url_for(
                    "data_list",
                    kind=kind
                )
            )

        return render_template(

            "form.html",

            kind=kind,
            label=label,
            cols=cols,
            obj=None,

            preselected_facility=
                preselected_facility,

            facilities=
                Facility.query.order_by(
                    Facility.name
                ).all()
        )


    # =========================
    # تعديل
    # =========================

    @app.route(
        "/edit/<kind>/<int:rid>",
        methods=["GET", "POST"]
    )
    @login_required
    @role_required(
        "admin",
        "editor"
    )
    def edit(kind, rid):

        if kind not in configs:

            return redirect(
                url_for("dashboard")
            )

        model, label, cols = configs[kind]

        obj = model.query.get_or_404(
            rid
        )

        if request.method == "POST":

            save_fields(
                obj,
                cols
            )

            if kind != "facilities":

                obj.facility_id = int(
                    request.form[
                        "facility_id"
                    ]
                )

            db.session.commit()

            flash(
                "تم التعديل بنجاح",
                "success"
            )

            return redirect(
                url_for(
                    "data_list",
                    kind=kind
                )
            )

        return render_template(

            "form.html",

            kind=kind,
            label=label,
            cols=cols,
            obj=obj,

            facilities=
                Facility.query.order_by(
                    Facility.name
                ).all()
        )


    # =========================
    # حذف
    # =========================

    @app.post(
        "/delete/<kind>/<int:rid>"
    )
    @login_required
    @role_required("admin")
    def delete(kind, rid):

        if kind not in configs:

            return redirect(
                url_for("dashboard")
            )

        model, label, cols = configs[kind]

        obj = model.query.get_or_404(
            rid
        )

        db.session.delete(obj)

        db.session.commit()

        flash(
            "تم الحذف",
            "success"
        )

        return redirect(
            url_for(
                "data_list",
                kind=kind
            )
        )


    # =========================
    # المستخدمون
    # =========================

    @app.route("/users")
    @login_required
    @role_required("admin")
    def users():

        all_users = User.query.order_by(
            User.id.desc()
        ).all()

        return render_template(
            "users.html",
            users=all_users
        )


    # =========================
    # إضافة مستخدم
    # =========================

    @app.route(
        "/users/new",
        methods=["GET", "POST"]
    )
    @login_required
    @role_required("admin")
    def user_new():

        if request.method == "POST":

            username = request.form.get(
                "username",
                ""
            ).strip()

            password = request.form.get(
                "password",
                ""
            )

            role = request.form.get(
                "role",
                "viewer"
            )

            if not username or not password:

                flash(
                    "اسم المستخدم وكلمة المرور مطلوبان",
                    "danger"
                )

            elif User.query.filter_by(
                username=username
            ).first():

                flash(
                    "اسم المستخدم موجود مسبقًا",
                    "danger"
                )

            else:

                user = User(
                    username=username,
                    role=role
                )

                user.set_password(
                    password
                )

                db.session.add(user)

                db.session.commit()

                flash(
                    "تم إنشاء المستخدم بنجاح",
                    "success"
                )

                return redirect(
                    url_for("users")
                )

        return render_template(
            "user_form.html",
            user=None
        )


    # =========================
    # تعديل مستخدم
    # =========================

    @app.route(
        "/users/edit/<int:uid>",
        methods=["GET", "POST"]
    )
    @login_required
    @role_required("admin")
    def user_edit(uid):

        user = User.query.get_or_404(
            uid
        )

        if request.method == "POST":

            username = request.form.get(
                "username",
                ""
            ).strip()

            role = request.form.get(
                "role",
                "viewer"
            )

            password = request.form.get(
                "password",
                ""
            )

            existing = User.query.filter(
                User.username == username,
                User.id != uid
            ).first()

            if existing:

                flash(
                    "اسم المستخدم مستخدم من قبل",
                    "danger"
                )

                return redirect(
                    url_for(
                        "user_edit",
                        uid=uid
                    )
                )

            user.username = username
            user.role = role

            if password:
                user.set_password(
                    password
                )

            db.session.commit()

            flash(
                "تم تعديل المستخدم بنجاح",
                "success"
            )

            return redirect(
                url_for("users")
            )

        return render_template(
            "user_form.html",
            user=user
        )


    # =========================
    # حذف مستخدم
    # =========================

    @app.post(
        "/users/delete/<int:uid>"
    )
    @login_required
    @role_required("admin")
    def user_delete(uid):

        if uid == session.get(
            "user_id"
        ):

            flash(
                "لا يمكن حذف المستخدم الذي سجل الدخول حاليًا",
                "danger"
            )

            return redirect(
                url_for("users")
            )

        user = User.query.get_or_404(
            uid
        )

        db.session.delete(user)

        db.session.commit()

        flash(
            "تم حذف المستخدم",
            "success"
        )

        return redirect(
            url_for("users")
        )
# =========================
    # التقارير
    # =========================

    @app.route("/reports")
    @login_required
    def reports():

        counts = {
            "facilities": Facility.query.count(),
            "laboratories": Laboratory.query.count(),
            "staff": Staff.query.count(),
            "devices": Device.query.count(),
            "reagents": Reagent.query.count(),
            "blood_banks": BloodBank.query.count()
        }

        return render_template(
            "reports.html",
            counts=counts,
            facilities=Facility.query.order_by(
                Facility.name
            ).all(),
            laboratories=Laboratory.query.order_by(
                Laboratory.name
            ).all(),
            staff=Staff.query.order_by(
                Staff.name
            ).all(),
            devices=Device.query.order_by(
                Device.name
            ).all(),
            reagents=Reagent.query.order_by(
                Reagent.name
            ).all(),
            blood_banks=BloodBank.query.order_by(
                BloodBank.name
            ).all()
        )

    # =========================
    # فحص النظام
    # =========================

    @app.route("/health")
    def health():

        return jsonify(
            ok=True
        )


    return app
