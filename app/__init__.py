import os
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db=SQLAlchemy()

class User(db.Model):
    id=db.Column(db.Integer,primary_key=True); username=db.Column(db.String(80),unique=True,nullable=False)
    password_hash=db.Column(db.String(255),nullable=False); role=db.Column(db.String(30),default="viewer")
    def set_password(self,p): self.password_hash=generate_password_hash(p)
    def check(self,p): return check_password_hash(self.password_hash,p)

class Facility(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(200),nullable=False)
    facility_type=db.Column(db.String(120)); region=db.Column(db.String(120)); municipality=db.Column(db.String(120))
    city=db.Column(db.String(120)); address=db.Column(db.String(255)); phone=db.Column(db.String(80))
    manager=db.Column(db.String(160)); status=db.Column(db.String(40),default="نشط"); notes=db.Column(db.Text)

class Staff(db.Model):
    id=db.Column(db.Integer,primary_key=True); facility_id=db.Column(db.Integer,db.ForeignKey("facility.id",ondelete="CASCADE"))
    name=db.Column(db.String(180),nullable=False); job_title=db.Column(db.String(150)); specialty=db.Column(db.String(150))
    qualification=db.Column(db.String(150)); phone=db.Column(db.String(80)); status=db.Column(db.String(50))

class Device(db.Model):
    id=db.Column(db.Integer,primary_key=True); facility_id=db.Column(db.Integer,db.ForeignKey("facility.id",ondelete="CASCADE"))
    name=db.Column(db.String(180),nullable=False); category=db.Column(db.String(120)); manufacturer=db.Column(db.String(120))
    model=db.Column(db.String(120)); serial_no=db.Column(db.String(150)); status=db.Column(db.String(80))
    purchase_year=db.Column(db.String(20)); notes=db.Column(db.Text)

class Reagent(db.Model):
    id=db.Column(db.Integer,primary_key=True); facility_id=db.Column(db.Integer,db.ForeignKey("facility.id",ondelete="CASCADE"))
    name=db.Column(db.String(180),nullable=False); manufacturer=db.Column(db.String(120)); lot_no=db.Column(db.String(100))
    expiry=db.Column(db.Date); quantity=db.Column(db.String(60)); unit=db.Column(db.String(60)); status=db.Column(db.String(80))

class BloodBank(db.Model):
    id=db.Column(db.Integer,primary_key=True); facility_id=db.Column(db.Integer,db.ForeignKey("facility.id",ondelete="CASCADE"))
    name=db.Column(db.String(180),nullable=False); blood_bank_type=db.Column(db.String(120)); capacity=db.Column(db.String(100))
    manager=db.Column(db.String(160)); phone=db.Column(db.String(80)); status=db.Column(db.String(60)); notes=db.Column(db.Text)

def create_app():
    app=Flask(__name__)
    app.config["SECRET_KEY"]=os.getenv("SECRET_KEY","change-this-secret-in-production")
    uri=os.getenv("DATABASE_URL","sqlite:///laboratories.db")
    if uri.startswith("postgres://"): uri=uri.replace("postgres://","postgresql+psycopg://",1)
    elif uri.startswith("postgresql://"): uri=uri.replace("postgresql://","postgresql+psycopg://",1)
    app.config["SQLALCHEMY_DATABASE_URI"]=uri
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"]=False
    db.init_app(app)
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username="admin").first():
            u=User(username="admin",role="admin"); u.set_password("admin123"); db.session.add(u); db.session.commit()

    def login_required(f):
        @wraps(f)
        def w(*a,**kw):
            if "user_id" not in session: return redirect(url_for("login"))
            return f(*a,**kw)
        return w
    app.jinja_env.globals["login_required"]=login_required

    @app.route("/login",methods=["GET","POST"])
    def login():
        if request.method=="POST":
            u=User.query.filter_by(username=request.form.get("username","")).first()
            if u and u.check(request.form.get("password","")):
                session["user_id"]=u.id; session["role"]=u.role; return redirect(url_for("dashboard"))
            flash("بيانات الدخول غير صحيحة","danger")
        return render_template("login.html")

    @app.route("/logout")
    def logout(): session.clear(); return redirect(url_for("login"))

    @app.route("/")
    @login_required
    def dashboard():
        exp=Reagent.query.filter(Reagent.expiry.isnot(None)).all()
        today=date.today(); exp_count=sum(1 for r in exp if (r.expiry-today).days<=60)
        return render_template("dashboard.html",counts={
            "facilities":Facility.query.count(),"staff":Staff.query.count(),"devices":Device.query.count(),
            "reagents":Reagent.query.count(),"blood_banks":BloodBank.query.count()},exp_count=exp_count)

    configs={
      "facilities":(Facility,"المرافق",["name","facility_type","region","municipality","city","phone","manager","status"]),
      "staff":(Staff,"العاملين",["name","job_title","specialty","qualification","phone","status"]),
      "devices":(Device,"الأجهزة",["name","category","manufacturer","model","serial_no","status"]),
      "reagents":(Reagent,"الكواشف",["name","manufacturer","lot_no","expiry","quantity","unit","status"]),
      "blood_banks":(BloodBank,"مصارف الدم",["name","blood_bank_type","capacity","manager","phone","status"])
    }
    @app.route("/data/<kind>")
    @login_required
    def data_list(kind):
        if kind not in configs: return redirect(url_for("dashboard"))
        model,label,cols=configs[kind]; q=request.args.get("q","").strip()
        rows=model.query.order_by(model.id.desc()).all()
        if q: rows=[r for r in rows if q.lower() in " ".join(str(getattr(r,c,"")) for c in cols).lower()]
        return render_template("list.html",kind=kind,label=label,cols=cols,rows=rows)

    @app.route("/facility/<int:fid>")
    @login_required
    def facility(fid):
        f=Facility.query.get_or_404(fid)
        return render_template("facility.html",f=f,staff=Staff.query.filter_by(facility_id=fid).all(),
          devices=Device.query.filter_by(facility_id=fid).all(),reagents=Reagent.query.filter_by(facility_id=fid).all(),
          blood_banks=BloodBank.query.filter_by(facility_id=fid).all())

    @app.route("/new/<kind>",methods=["GET","POST"])
    @login_required
    def new(kind):
        if kind not in configs:return redirect(url_for("dashboard"))
        model,label,cols=configs[kind]; rid=None
        if request.method=="POST":
            obj=model()
            for c in cols:
                val=request.form.get(c,"").strip()
                if c=="expiry": val=datetime.strptime(val,"%Y-%m-%d").date() if val else None
                setattr(obj,c,val)
            if kind!="facilities":
                obj.facility_id=int(request.form["facility_id"])
            db.session.add(obj); db.session.commit()
            flash("تم الحفظ بنجاح","success")
            return redirect(url_for("data_list",kind=kind))
        return render_template("form.html",kind=kind,label=label,cols=cols,obj=None,facilities=Facility.query.all())

    @app.route("/edit/<kind>/<int:rid>",methods=["GET","POST"])
    @login_required
    def edit(kind,rid):
        model,label,cols=configs[kind]; obj=model.query.get_or_404(rid)
        if request.method=="POST":
            for c in cols:
                val=request.form.get(c,"").strip()
                if c=="expiry": val=datetime.strptime(val,"%Y-%m-%d").date() if val else None
                setattr(obj,c,val)
            if kind!="facilities": obj.facility_id=int(request.form["facility_id"])
            db.session.commit(); flash("تم التعديل","success"); return redirect(url_for("data_list",kind=kind))
        return render_template("form.html",kind=kind,label=label,cols=cols,obj=obj,facilities=Facility.query.all())

    @app.post("/delete/<kind>/<int:rid>")
    @login_required
    def delete(kind,rid):
        if session.get("role")!="admin": flash("الحذف متاح لمدير النظام فقط","danger"); return redirect(url_for("data_list",kind=kind))
        model,label,cols=configs[kind]; obj=model.query.get_or_404(rid); db.session.delete(obj); db.session.commit()
        flash("تم الحذف","success"); return redirect(url_for("data_list",kind=kind))

    @app.route("/health")
    def health(): return jsonify(ok=True)

    return app
