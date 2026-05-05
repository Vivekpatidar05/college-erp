from flask import (Flask, render_template, request, redirect, url_for,
                   flash, session, jsonify, make_response)
from pymongo import MongoClient, DESCENDING
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict
import os, csv, io

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dsvv_erp_ultra_secret_2024")

# ── MongoDB Atlas ──────────────────────────────────────────────────────────────
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
client    = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db        = client[os.environ.get("DB_NAME", "dsvv_erp")]

users_col        = db["users"]
students_col     = db["students"]
teachers_col     = db["teachers"]
courses_col      = db["courses"]
attendance_col   = db["attendance"]
fees_col         = db["fees"]
results_col      = db["results"]
notices_col      = db["notices"]
library_col      = db["library"]
timetable_col    = db["timetable"]
assignments_col  = db["assignments"]
submissions_col  = db["submissions"]
events_col       = db["events"]
exam_col         = db["exam_schedule"]
grievances_col   = db["grievances"]
hostel_col       = db["hostel"]

# ── Seed default admin ─────────────────────────────────────────────────────────
def seed_admin():
    if not users_col.find_one({"role": "admin"}):
        users_col.insert_one({
            "username": "admin", "name": "Super Administrator",
            "password": generate_password_hash("admin123"),
            "role": "admin", "linked_id": None, "active": True,
            "created_at": today(),
        })

def today():
    return datetime.now().strftime("%Y-%m-%d")

seed_admin()

# ═══════════════════════════════════════════════════════════════════════════════
# DECORATORS
# ═══════════════════════════════════════════════════════════════════════════════
def login_required(f):
    @wraps(f)
    def d(*a, **kw):
        if "user_id" not in session:
            flash("Please log in.", "warning"); return redirect(url_for("login"))
        return f(*a, **kw)
    return d

def admin_required(f):
    @wraps(f)
    def d(*a, **kw):
        if "user_id" not in session: return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Admin access required.", "danger"); return redirect(url_for("home"))
        return f(*a, **kw)
    return d

def teacher_required(f):
    @wraps(f)
    def d(*a, **kw):
        if "user_id" not in session: return redirect(url_for("login"))
        if session.get("role") != "teacher":
            flash("Teacher access required.", "danger"); return redirect(url_for("home"))
        return f(*a, **kw)
    return d

def student_required(f):
    @wraps(f)
    def d(*a, **kw):
        if "user_id" not in session: return redirect(url_for("login"))
        if session.get("role") != "student":
            flash("Student access required.", "danger"); return redirect(url_for("home"))
        return f(*a, **kw)
    return d

def get_teacher(): 
    lid = session.get("linked_id")
    return teachers_col.find_one({"_id": ObjectId(lid)}) if lid else None

def get_student(): 
    lid = session.get("linked_id")
    return students_col.find_one({"_id": ObjectId(lid)}) if lid else None

# ═══════════════════════════════════════════════════════════════════════════════
# HOME / AUTH
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/")
def home():
    if "user_id" not in session: return redirect(url_for("login"))
    r = session.get("role")
    return redirect(url_for({"admin":"dashboard","teacher":"teacher_dashboard",
                             "student":"student_dashboard"}.get(r,"login")))

@app.route("/login", methods=["GET","POST"])
def login():
    if "user_id" in session: return redirect(url_for("home"))
    if request.method == "POST":
        u = users_col.find_one({"username": request.form["username"].strip()})
        if not u or not check_password_hash(u["password"], request.form["password"]):
            flash("Invalid credentials.", "danger")
            return render_template("auth/login.html")
        if not u.get("active", True):
            flash("Account deactivated. Contact administrator.", "danger")
            return render_template("auth/login.html")
        session.update({
            "user_id":   str(u["_id"]), "username": u["username"],
            "role":      u["role"],     "name":     u["name"],
            "linked_id": str(u["linked_id"]) if u.get("linked_id") else None,
        })
        flash(f"Welcome, {u['name']}!", "success")
        return redirect(url_for("home"))
    return render_template("auth/login.html")

@app.route("/logout")
def logout():
    session.clear(); flash("Logged out.", "success")
    return redirect(url_for("login"))

@app.route("/change-password", methods=["GET","POST"])
@login_required
def change_password():
    if request.method == "POST":
        u = users_col.find_one({"_id": ObjectId(session["user_id"])})
        if not check_password_hash(u["password"], request.form["old_password"]):
            flash("Current password is incorrect.", "danger")
            return render_template("auth/change_password.html")
        if request.form["new_password"] != request.form["confirm_password"]:
            flash("New passwords do not match.", "danger")
            return render_template("auth/change_password.html")
        if len(request.form["new_password"]) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return render_template("auth/change_password.html")
        users_col.update_one({"_id": ObjectId(session["user_id"])},
            {"$set": {"password": generate_password_hash(request.form["new_password"])}})
        flash("Password changed successfully!", "success")
        return redirect(url_for("home"))
    return render_template("auth/change_password.html")

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN – DASHBOARD + ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/dashboard")
@admin_required
def dashboard():
    stats = {
        "students":      students_col.count_documents({}),
        "teachers":      teachers_col.count_documents({}),
        "courses":       courses_col.count_documents({}),
        "fees_pending":  fees_col.count_documents({"status": "Pending"}),
        "library":       library_col.count_documents({}),
        "notices":       notices_col.count_documents({}),
        "events":        events_col.count_documents({}),
        "grievances":    grievances_col.count_documents({"status": "Open"}),
        "assignments":   assignments_col.count_documents({}),
        "hostel":        hostel_col.count_documents({}),
        "users":         users_col.count_documents({}),
        "fees_paid":     fees_col.count_documents({"status": "Paid"}),
    }
    recent_students = list(students_col.find().sort("_id", DESCENDING).limit(5))
    recent_notices  = list(notices_col.find().sort("date", DESCENDING).limit(4))
    recent_events   = list(events_col.find().sort("date", 1).limit(3))
    open_grievances = list(grievances_col.find({"status":"Open"}).sort("_id", DESCENDING).limit(3))
    upcoming_exams  = list(exam_col.find().sort("exam_date", 1).limit(4))
    return render_template("dashboard.html", stats=stats,
        recent_students=recent_students, recent_notices=recent_notices,
        recent_events=recent_events, open_grievances=open_grievances,
        upcoming_exams=upcoming_exams)

@app.route("/analytics")
@admin_required
def analytics():
    # Attendance by subject
    pipeline = [{"$group": {"_id": "$subject",
        "present": {"$sum": {"$cond": [{"$eq":["$status","Present"]},1,0]}},
        "total":   {"$sum": 1}}}]
    att_data = list(attendance_col.aggregate(pipeline))

    # Enrollment by course
    enroll = list(students_col.aggregate([
        {"$group": {"_id": "$course", "count": {"$sum": 1}}}]))

    # Fee collection (monthly, last 6 months)
    fee_monthly = list(fees_col.aggregate([
        {"$match": {"status": "Paid"}},
        {"$group": {"_id": "$paid_date", "total": {"$sum": {"$toInt": "$amount"}}}}]))

    # Gender distribution
    gender = list(students_col.aggregate([
        {"$group": {"_id": "$gender", "count": {"$sum": 1}}}]))

    # Results grade distribution
    grades = list(results_col.aggregate([
        {"$group": {"_id": "$grade", "count": {"$sum": 1}}}]))

    # Library books by category
    lib_cat = list(library_col.aggregate([
        {"$group": {"_id": "$category", "count": {"$sum": 1}}}]))

    total_fee_collected = sum(int(f.get("amount",0)) for f in fees_col.find({"status":"Paid"}))
    total_fee_pending   = sum(int(f.get("amount",0)) for f in fees_col.find({"status":"Pending"}))

    return render_template("admin/analytics.html",
        att_data=att_data, enroll=enroll, fee_monthly=fee_monthly,
        gender=gender, grades=grades, lib_cat=lib_cat,
        total_fee_collected=total_fee_collected,
        total_fee_pending=total_fee_pending)

# ═══════════════════════════════════════════════════════════════════════════════
# USER MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/admin/users")
@admin_required
def admin_users():
    return render_template("admin/users.html",
        users=list(users_col.find().sort("role",1)))

@app.route("/admin/users/add", methods=["GET","POST"])
@admin_required
def admin_add_user():
    students_list = list(students_col.find({},{"name":1,"roll_no":1}))
    teachers_list = list(teachers_col.find({},{"name":1,"emp_id":1,"subject":1}))
    if request.method == "POST":
        username = request.form["username"].strip()
        if users_col.find_one({"username": username}):
            flash("Username already exists.", "danger")
            return render_template("admin/users_add.html",
                students=students_list, teachers=teachers_list)
        role = request.form["role"]
        lid  = request.form.get("linked_id") or None
        name = request.form.get("name","").strip()
        if not name and lid:
            rec = (students_col if role=="student" else teachers_col).find_one({"_id":ObjectId(lid)})
            if rec: name = rec["name"]
        users_col.insert_one({
            "username": username, "name": name or username,
            "password": generate_password_hash(request.form["password"]),
            "role": role, "linked_id": ObjectId(lid) if lid else None,
            "active": True, "created_at": today(),
        })
        flash(f"User '{username}' created!", "success")
        return redirect(url_for("admin_users"))
    return render_template("admin/users_add.html",
        students=students_list, teachers=teachers_list)

@app.route("/admin/users/edit/<id>", methods=["GET","POST"])
@admin_required
def admin_edit_user(id):
    user = users_col.find_one({"_id":ObjectId(id)})
    students_list = list(students_col.find({},{"name":1,"roll_no":1}))
    teachers_list = list(teachers_col.find({},{"name":1,"emp_id":1,"subject":1}))
    if request.method == "POST":
        upd = {"name": request.form["name"], "role": request.form["role"],
               "active": request.form.get("active")=="on",
               "linked_id": ObjectId(request.form["linked_id"]) if request.form.get("linked_id") else None}
        pw = request.form.get("password","").strip()
        if pw: upd["password"] = generate_password_hash(pw)
        users_col.update_one({"_id":ObjectId(id)},{"$set":upd})
        flash("User updated.", "success"); return redirect(url_for("admin_users"))
    return render_template("admin/users_edit.html", user=user,
        students=students_list, teachers=teachers_list)

@app.route("/admin/users/toggle/<id>")
@admin_required
def admin_toggle_user(id):
    u = users_col.find_one({"_id":ObjectId(id)})
    if u:
        if u["role"]=="admin" and u.get("active",True) and \
           users_col.count_documents({"role":"admin","active":True})<=1:
            flash("Cannot deactivate the only active admin.","danger")
            return redirect(url_for("admin_users"))
        users_col.update_one({"_id":ObjectId(id)},{"$set":{"active":not u.get("active",True)}})
        flash(f"User {'deactivated' if u.get('active',True) else 'activated'}.","success")
    return redirect(url_for("admin_users"))

@app.route("/admin/users/delete/<id>")
@admin_required
def admin_delete_user(id):
    u = users_col.find_one({"_id":ObjectId(id)})
    if u and u["role"]=="admin" and users_col.count_documents({"role":"admin"})<=1:
        flash("Cannot delete the only admin.","danger")
        return redirect(url_for("admin_users"))
    users_col.delete_one({"_id":ObjectId(id)})
    flash("User deleted.","danger"); return redirect(url_for("admin_users"))

# ═══════════════════════════════════════════════════════════════════════════════
# STUDENTS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/students")
@admin_required
def students():
    q = request.args.get("q","")
    qr = {"$or":[{"name":{"$regex":q,"$options":"i"}},
                 {"roll_no":{"$regex":q,"$options":"i"}}]} if q else {}
    return render_template("students/index.html",
        students=list(students_col.find(qr).sort("name",1)), q=q)

@app.route("/students/add", methods=["GET","POST"])
@admin_required
def add_student():
    courses = list(courses_col.find({},{"name":1,"code":1}))
    if request.method == "POST":
        students_col.insert_one({
            "roll_no":    request.form["roll_no"],
            "name":       request.form["name"],
            "email":      request.form["email"],
            "phone":      request.form["phone"],
            "dob":        request.form["dob"],
            "gender":     request.form["gender"],
            "course":     request.form["course"],
            "semester":   request.form["semester"],
            "year":       request.form["year"],
            "address":    request.form["address"],
            "guardian":   request.form.get("guardian",""),
            "guardian_ph":request.form.get("guardian_ph",""),
            "blood_group":request.form.get("blood_group",""),
            "category":   request.form.get("category","General"),
            "created_at": today(),
        })
        flash("Student added!", "success"); return redirect(url_for("students"))
    return render_template("students/add.html", courses=courses)

@app.route("/students/edit/<id>", methods=["GET","POST"])
@admin_required
def edit_student(id):
    student = students_col.find_one({"_id":ObjectId(id)})
    courses = list(courses_col.find({},{"name":1}))
    if request.method == "POST":
        students_col.update_one({"_id":ObjectId(id)},{"$set":{
            "roll_no":    request.form["roll_no"],  "name":       request.form["name"],
            "email":      request.form["email"],     "phone":      request.form["phone"],
            "dob":        request.form["dob"],       "gender":     request.form["gender"],
            "course":     request.form["course"],    "semester":   request.form["semester"],
            "year":       request.form["year"],      "address":    request.form["address"],
            "guardian":   request.form.get("guardian",""),
            "guardian_ph":request.form.get("guardian_ph",""),
            "blood_group":request.form.get("blood_group",""),
            "category":   request.form.get("category","General"),
        }})
        flash("Student updated!", "success"); return redirect(url_for("students"))
    return render_template("students/edit.html", student=student, courses=courses)

@app.route("/students/delete/<id>")
@admin_required
def delete_student(id):
    students_col.delete_one({"_id":ObjectId(id)})
    flash("Student deleted.","danger"); return redirect(url_for("students"))

@app.route("/students/id-card/<id>")
@login_required
def student_id_card(id):
    student = students_col.find_one({"_id":ObjectId(id)})
    if session.get("role")=="student":
        s = get_student()
        if not s or str(s["_id"])!=id:
            flash("Access denied.","danger"); return redirect(url_for("student_dashboard"))
    course = courses_col.find_one({"name":student.get("course","")})
    return render_template("students/id_card.html", student=student, course=course)

# ═══════════════════════════════════════════════════════════════════════════════
# TEACHERS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/teachers")
@admin_required
def teachers():
    q = request.args.get("q","")
    qr = {"$or":[{"name":{"$regex":q,"$options":"i"}},
                 {"subject":{"$regex":q,"$options":"i"}}]} if q else {}
    return render_template("teachers/index.html",
        teachers=list(teachers_col.find(qr).sort("name",1)), q=q)

@app.route("/teachers/add", methods=["GET","POST"])
@admin_required
def add_teacher():
    if request.method == "POST":
        teachers_col.insert_one({k:request.form.get(k,"") for k in
            ["emp_id","name","email","phone","subject","department",
             "qualification","experience","salary","joining_date","specialization"]})
        flash("Teacher added!", "success"); return redirect(url_for("teachers"))
    return render_template("teachers/add.html")

@app.route("/teachers/edit/<id>", methods=["GET","POST"])
@admin_required
def edit_teacher(id):
    teacher = teachers_col.find_one({"_id":ObjectId(id)})
    if request.method == "POST":
        teachers_col.update_one({"_id":ObjectId(id)},{"$set":{k:request.form.get(k,"") for k in
            ["emp_id","name","email","phone","subject","department",
             "qualification","experience","salary","joining_date","specialization"]}})
        flash("Teacher updated!","success"); return redirect(url_for("teachers"))
    return render_template("teachers/edit.html", teacher=teacher)

@app.route("/teachers/delete/<id>")
@admin_required
def delete_teacher(id):
    teachers_col.delete_one({"_id":ObjectId(id)})
    flash("Teacher deleted.","danger"); return redirect(url_for("teachers"))

# ═══════════════════════════════════════════════════════════════════════════════
# COURSES
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/courses")
@admin_required
def courses():
    return render_template("courses/index.html",
        courses=list(courses_col.find().sort("name",1)))

@app.route("/courses/add", methods=["GET","POST"])
@admin_required
def add_course():
    if request.method == "POST":
        courses_col.insert_one({k:request.form.get(k,"") for k in
            ["code","name","duration","semesters","seats","fees","dept","desc","level"]})
        flash("Course added!","success"); return redirect(url_for("courses"))
    return render_template("courses/add.html")

@app.route("/courses/edit/<id>", methods=["GET","POST"])
@admin_required
def edit_course(id):
    course = courses_col.find_one({"_id":ObjectId(id)})
    if request.method == "POST":
        courses_col.update_one({"_id":ObjectId(id)},{"$set":{k:request.form.get(k,"") for k in
            ["code","name","duration","semesters","seats","fees","dept","desc","level"]}})
        flash("Course updated!","success"); return redirect(url_for("courses"))
    return render_template("courses/edit.html", course=course)

@app.route("/courses/delete/<id>")
@admin_required
def delete_course(id):
    courses_col.delete_one({"_id":ObjectId(id)})
    flash("Course deleted.","danger"); return redirect(url_for("courses"))

# ═══════════════════════════════════════════════════════════════════════════════
# ATTENDANCE
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/attendance")
@admin_required
def attendance():
    q = request.args.get("q","")
    sf = request.args.get("subject","")
    qr = {}
    if q: qr["roll_no"] = {"$regex":q,"$options":"i"}
    if sf: qr["subject"] = sf
    subjects = attendance_col.distinct("subject")
    return render_template("attendance/index.html",
        records=list(attendance_col.find(qr).sort("date",DESCENDING).limit(200)),
        subjects=subjects, q=q, sf=sf)

@app.route("/attendance/add", methods=["GET","POST"])
@admin_required
def add_attendance():
    students_list = list(students_col.find({},{"name":1,"roll_no":1,"course":1,"semester":1}))
    courses_list  = list(courses_col.find({},{"name":1,"code":1}))
    teachers_list = list(teachers_col.find({},{"name":1,"subject":1}))
    if request.method == "POST":
        roll_nos = request.form.getlist("roll_no")
        statuses = request.form.getlist("status")
        date = request.form["date"]; course = request.form["course"]
        subject = request.form.get("subject","")
        for rn,st in zip(roll_nos,statuses):
            s = students_col.find_one({"roll_no":rn})
            attendance_col.insert_one({
                "roll_no":rn,"name":s["name"] if s else rn,
                "course":course,"subject":subject,"date":date,
                "status":st,"marked_by":session.get("name","Admin"),
            })
        flash(f"Attendance saved for {len(roll_nos)} students!","success")
        return redirect(url_for("attendance"))
    return render_template("attendance/add.html",
        students=students_list, courses=courses_list, teachers=teachers_list)

@app.route("/attendance/delete/<id>")
@admin_required
def delete_attendance(id):
    attendance_col.delete_one({"_id":ObjectId(id)})
    flash("Record deleted.","danger"); return redirect(url_for("attendance"))

@app.route("/attendance/export")
@admin_required
def export_attendance():
    subject = request.args.get("subject","")
    qr = {"subject":subject} if subject else {}
    records = list(attendance_col.find(qr).sort("date",DESCENDING))
    si = io.StringIO()
    w  = csv.writer(si)
    w.writerow(["Roll No","Name","Course","Subject","Date","Status","Marked By"])
    for r in records:
        w.writerow([r.get("roll_no",""),r.get("name",""),r.get("course",""),
                    r.get("subject",""),r.get("date",""),r.get("status",""),r.get("marked_by","")])
    out = make_response(si.getvalue())
    out.headers["Content-Disposition"] = "attachment; filename=attendance.csv"
    out.headers["Content-type"] = "text/csv"
    return out

# ═══════════════════════════════════════════════════════════════════════════════
# FEES
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/fees")
@admin_required
def fees():
    q=request.args.get("q",""); sf=request.args.get("status","")
    qr={}
    if q: qr["$or"]=[{"student_name":{"$regex":q,"$options":"i"}},{"roll_no":{"$regex":q,"$options":"i"}}]
    if sf: qr["status"]=sf
    return render_template("fees/index.html",
        fees=list(fees_col.find(qr).sort("due_date",1)),q=q,status_filter=sf)

@app.route("/fees/add", methods=["GET","POST"])
@admin_required
def add_fee():
    students_list=list(students_col.find({},{"name":1,"roll_no":1,"course":1}))
    if request.method=="POST":
        fees_col.insert_one({k:request.form.get(k,"") for k in
            ["roll_no","student_name","course","fee_type","amount","due_date","paid_date","status","remarks","transaction_id"]})
        flash("Fee record added!","success"); return redirect(url_for("fees"))
    return render_template("fees/add.html", students=students_list)

@app.route("/fees/edit/<id>", methods=["GET","POST"])
@admin_required
def edit_fee(id):
    fee=fees_col.find_one({"_id":ObjectId(id)})
    students_list=list(students_col.find({},{"name":1,"roll_no":1,"course":1}))
    if request.method=="POST":
        fees_col.update_one({"_id":ObjectId(id)},{"$set":{k:request.form.get(k,"") for k in
            ["roll_no","student_name","course","fee_type","amount","due_date","paid_date","status","remarks","transaction_id"]}})
        flash("Fee updated!","success"); return redirect(url_for("fees"))
    return render_template("fees/edit.html", fee=fee, students=students_list)

@app.route("/fees/delete/<id>")
@admin_required
def delete_fee(id):
    fees_col.delete_one({"_id":ObjectId(id)})
    flash("Fee record deleted.","danger"); return redirect(url_for("fees"))

@app.route("/fees/export")
@admin_required
def export_fees():
    records = list(fees_col.find().sort("due_date",1))
    si=io.StringIO(); w=csv.writer(si)
    w.writerow(["Roll No","Student","Course","Fee Type","Amount","Due Date","Paid Date","Status","Transaction ID"])
    for r in records:
        w.writerow([r.get(k,"") for k in ["roll_no","student_name","course","fee_type","amount","due_date","paid_date","status","transaction_id"]])
    out=make_response(si.getvalue())
    out.headers["Content-Disposition"]="attachment; filename=fees.csv"
    out.headers["Content-type"]="text/csv"
    return out

# ═══════════════════════════════════════════════════════════════════════════════
# RESULTS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/results")
@admin_required
def results():
    q=request.args.get("q","")
    qr={"$or":[{"student_name":{"$regex":q,"$options":"i"}},{"roll_no":{"$regex":q,"$options":"i"}}]} if q else {}
    return render_template("results/index.html",
        results=list(results_col.find(qr).sort("roll_no",1)),q=q)

@app.route("/results/add", methods=["GET","POST"])
@admin_required
def add_result():
    students_list=list(students_col.find({},{"name":1,"roll_no":1,"course":1,"semester":1}))
    if request.method=="POST":
        marks={f"subject{i}":{"name":request.form[f"s{i}_name"],
            "marks":request.form[f"s{i}_marks"],"max":request.form[f"s{i}_max"]}
            for i in range(1,7) if request.form.get(f"s{i}_name","")}
        total=sum(int(v["marks"]) for v in marks.values())
        total_max=sum(int(v["max"]) for v in marks.values())
        pct=round((total/total_max)*100,2) if total_max else 0
        grade=("O" if pct>=90 else "A+" if pct>=85 else "A" if pct>=80 else
               "B+" if pct>=75 else "B" if pct>=70 else "C" if pct>=60 else
               "D" if pct>=50 else "F")
        results_col.insert_one({
            "roll_no":request.form["roll_no"],"student_name":request.form["student_name"],
            "course":request.form["course"],"semester":request.form["semester"],
            "exam_type":request.form["exam_type"],"marks":marks,
            "total":total,"total_max":total_max,"percentage":pct,"grade":grade,
            "result":"Pass" if pct>=40 else "Fail","academic_year":request.form.get("academic_year",""),
        })
        flash("Result added!","success"); return redirect(url_for("results"))
    return render_template("results/add.html",students=students_list)

@app.route("/results/delete/<id>")
@admin_required
def delete_result(id):
    results_col.delete_one({"_id":ObjectId(id)})
    flash("Result deleted.","danger"); return redirect(url_for("results"))

@app.route("/results/view/<id>")
@login_required
def view_result(id):
    result=results_col.find_one({"_id":ObjectId(id)})
    if session.get("role")=="student":
        s=get_student()
        if not s or result.get("roll_no")!=s.get("roll_no"):
            flash("Access denied.","danger"); return redirect(url_for("student_results"))
    return render_template("results/view.html",result=result)

# ═══════════════════════════════════════════════════════════════════════════════
# NOTICES
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/notices")
@admin_required
def notices():
    return render_template("notices/index.html",
        notices=list(notices_col.find().sort("date",DESCENDING)))

@app.route("/notices/add", methods=["GET","POST"])
@admin_required
def add_notice():
    if request.method=="POST":
        notices_col.insert_one({"title":request.form["title"],"category":request.form["category"],
            "content":request.form["content"],"date":today(),
            "priority":request.form["priority"],"author":request.form["author"],
            "target":request.form.get("target","All")})
        flash("Notice posted!","success"); return redirect(url_for("notices"))
    return render_template("notices/add.html")

@app.route("/notices/edit/<id>", methods=["GET","POST"])
@admin_required
def edit_notice(id):
    notice=notices_col.find_one({"_id":ObjectId(id)})
    if request.method=="POST":
        notices_col.update_one({"_id":ObjectId(id)},{"$set":{
            "title":request.form["title"],"category":request.form["category"],
            "content":request.form["content"],"priority":request.form["priority"],
            "author":request.form["author"],"target":request.form.get("target","All")}})
        flash("Notice updated!","success"); return redirect(url_for("notices"))
    return render_template("notices/edit.html",notice=notice)

@app.route("/notices/delete/<id>")
@admin_required
def delete_notice(id):
    notices_col.delete_one({"_id":ObjectId(id)})
    flash("Notice deleted.","danger"); return redirect(url_for("notices"))

# ═══════════════════════════════════════════════════════════════════════════════
# LIBRARY
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/library")
@admin_required
def library():
    q=request.args.get("q","")
    qr={"$or":[{"title":{"$regex":q,"$options":"i"}},{"author":{"$regex":q,"$options":"i"}},
               {"isbn":{"$regex":q,"$options":"i"}}]} if q else {}
    return render_template("library/index.html",books=list(library_col.find(qr).sort("title",1)),q=q)

@app.route("/library/add", methods=["GET","POST"])
@admin_required
def add_book():
    if request.method=="POST":
        copies=int(request.form.get("copies",1))
        library_col.insert_one({**{k:request.form.get(k,"") for k in
            ["isbn","title","author","publisher","category","rack_no","edition","year_pub"]},
            "copies":copies,"available":copies,"added_date":today()})
        flash("Book added!","success"); return redirect(url_for("library"))
    return render_template("library/add.html")

@app.route("/library/edit/<id>", methods=["GET","POST"])
@admin_required
def edit_book(id):
    book=library_col.find_one({"_id":ObjectId(id)})
    if request.method=="POST":
        library_col.update_one({"_id":ObjectId(id)},{"$set":{
            **{k:request.form.get(k,"") for k in ["isbn","title","author","publisher","category","rack_no","edition","year_pub"]},
            "copies":int(request.form.get("copies",1)),
            "available":int(request.form.get("available",0))}})
        flash("Book updated!","success"); return redirect(url_for("library"))
    return render_template("library/edit.html",book=book)

@app.route("/library/delete/<id>")
@admin_required
def delete_book(id):
    library_col.delete_one({"_id":ObjectId(id)})
    flash("Book removed.","danger"); return redirect(url_for("library"))

# ═══════════════════════════════════════════════════════════════════════════════
# TIMETABLE
# ═══════════════════════════════════════════════════════════════════════════════
DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]

@app.route("/timetable")
@admin_required
def timetable():
    course_filter = request.args.get("course","")
    sem_filter    = request.args.get("sem","")
    qr = {}
    if course_filter: qr["course"] = course_filter
    if sem_filter:    qr["semester"] = sem_filter
    slots = list(timetable_col.find(qr).sort([("day",1),("time_start",1)]))
    courses_list = list(courses_col.find({},{"name":1}))
    # Organise by day
    by_day = defaultdict(list)
    for s in slots: by_day[s["day"]].append(s)
    return render_template("timetable/index.html", by_day=by_day, days=DAYS,
        courses_list=courses_list, course_filter=course_filter, sem_filter=sem_filter)

@app.route("/timetable/add", methods=["GET","POST"])
@admin_required
def add_timetable():
    courses_list  = list(courses_col.find({},{"name":1}))
    teachers_list = list(teachers_col.find({},{"name":1,"subject":1}))
    if request.method=="POST":
        timetable_col.insert_one({k:request.form.get(k,"") for k in
            ["day","time_start","time_end","course","semester","subject","teacher","room"]})
        flash("Timetable slot added!","success"); return redirect(url_for("timetable"))
    return render_template("timetable/add.html",courses=courses_list,teachers=teachers_list,days=DAYS)

@app.route("/timetable/delete/<id>")
@admin_required
def delete_timetable(id):
    timetable_col.delete_one({"_id":ObjectId(id)})
    flash("Slot removed.","danger"); return redirect(url_for("timetable"))

# ═══════════════════════════════════════════════════════════════════════════════
# ASSIGNMENTS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/assignments")
@admin_required
def assignments():
    return render_template("assignments/index.html",
        assignments=list(assignments_col.find().sort("_id",DESCENDING)))

@app.route("/assignments/view/<id>")
@login_required
def view_assignment(id):
    asgn = assignments_col.find_one({"_id":ObjectId(id)})
    subs = list(submissions_col.find({"assignment_id":str(id)}))
    return render_template("assignments/view.html", asgn=asgn, subs=subs)

@app.route("/assignments/delete/<id>")
@admin_required
def delete_assignment(id):
    assignments_col.delete_one({"_id":ObjectId(id)})
    submissions_col.delete_many({"assignment_id":str(id)})
    flash("Assignment deleted.","danger"); return redirect(url_for("assignments"))

# ── Teacher: post assignment ───────────────────────────────────────────────────
@app.route("/teacher/assignments", methods=["GET","POST"])
@teacher_required
def teacher_assignments():
    teacher = get_teacher()
    if not teacher: return redirect(url_for("logout"))
    my_assignments = list(assignments_col.find({"teacher_id":session.get("linked_id")}).sort("_id",DESCENDING))
    courses_list = list(courses_col.find({},{"name":1}))
    if request.method=="POST":
        assignments_col.insert_one({
            "title":       request.form["title"],
            "subject":     teacher.get("subject",""),
            "teacher":     teacher["name"],
            "teacher_id":  session.get("linked_id"),
            "course":      request.form["course"],
            "semester":    request.form["semester"],
            "description": request.form["description"],
            "due_date":    request.form["due_date"],
            "max_marks":   request.form.get("max_marks","100"),
            "posted_on":   today(),
        })
        flash("Assignment posted!","success")
        return redirect(url_for("teacher_assignments"))
    return render_template("teacher/assignments.html",
        teacher=teacher, assignments=my_assignments, courses=courses_list)

# ── Student: view + submit ─────────────────────────────────────────────────────
@app.route("/student/assignments")
@student_required
def student_assignments():
    student = get_student()
    if not student: return redirect(url_for("logout"))
    asgns = list(assignments_col.find({
        "$or":[{"course":student.get("course","")},{"course":"All"}]
    }).sort("due_date",1))
    # Which ones submitted?
    submitted_ids = {s["assignment_id"] for s in
        submissions_col.find({"roll_no":student.get("roll_no","")})}
    return render_template("student/assignments.html",
        student=student, assignments=asgns, submitted_ids=submitted_ids)

@app.route("/student/assignments/submit/<asgn_id>", methods=["POST"])
@student_required
def submit_assignment(asgn_id):
    student = get_student()
    if not student: return redirect(url_for("logout"))
    if submissions_col.find_one({"assignment_id":asgn_id,"roll_no":student.get("roll_no","")}):
        flash("Already submitted.","warning")
        return redirect(url_for("student_assignments"))
    submissions_col.insert_one({
        "assignment_id": asgn_id,
        "roll_no":       student.get("roll_no",""),
        "student_name":  student["name"],
        "answer":        request.form.get("answer",""),
        "submitted_on":  today(),
        "status":        "Submitted",
    })
    flash("Assignment submitted!","success")
    return redirect(url_for("student_assignments"))

# ═══════════════════════════════════════════════════════════════════════════════
# EVENTS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/events")
@admin_required
def events():
    return render_template("events/index.html",
        events=list(events_col.find().sort("date",1)))

@app.route("/events/add", methods=["GET","POST"])
@admin_required
def add_event():
    if request.method=="POST":
        events_col.insert_one({k:request.form.get(k,"") for k in
            ["title","category","date","time","venue","description","organizer","target"]})
        flash("Event added!","success"); return redirect(url_for("events"))
    return render_template("events/add.html")

@app.route("/events/edit/<id>", methods=["GET","POST"])
@admin_required
def edit_event(id):
    event=events_col.find_one({"_id":ObjectId(id)})
    if request.method=="POST":
        events_col.update_one({"_id":ObjectId(id)},{"$set":{k:request.form.get(k,"") for k in
            ["title","category","date","time","venue","description","organizer","target"]}})
        flash("Event updated!","success"); return redirect(url_for("events"))
    return render_template("events/edit.html",event=event)

@app.route("/events/delete/<id>")
@admin_required
def delete_event(id):
    events_col.delete_one({"_id":ObjectId(id)})
    flash("Event deleted.","danger"); return redirect(url_for("events"))

# ═══════════════════════════════════════════════════════════════════════════════
# EXAM SCHEDULE
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/exam-schedule")
@admin_required
def exam_schedule():
    return render_template("exam_schedule/index.html",
        exams=list(exam_col.find().sort("exam_date",1)))

@app.route("/exam-schedule/add", methods=["GET","POST"])
@admin_required
def add_exam():
    courses_list=list(courses_col.find({},{"name":1}))
    if request.method=="POST":
        exam_col.insert_one({k:request.form.get(k,"") for k in
            ["subject","course","semester","exam_date","time_start","time_end","room","exam_type","max_marks","notes"]})
        flash("Exam scheduled!","success"); return redirect(url_for("exam_schedule"))
    return render_template("exam_schedule/add.html",courses=courses_list)

@app.route("/exam-schedule/delete/<id>")
@admin_required
def delete_exam(id):
    exam_col.delete_one({"_id":ObjectId(id)})
    flash("Exam removed.","danger"); return redirect(url_for("exam_schedule"))

# ═══════════════════════════════════════════════════════════════════════════════
# GRIEVANCES
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/grievances")
@admin_required
def grievances():
    status_f = request.args.get("status","")
    qr = {"status":status_f} if status_f else {}
    return render_template("grievances/index.html",
        grievances=list(grievances_col.find(qr).sort("_id",DESCENDING)),
        status_filter=status_f)

@app.route("/grievances/respond/<id>", methods=["GET","POST"])
@admin_required
def respond_grievance(id):
    g = grievances_col.find_one({"_id":ObjectId(id)})
    if request.method=="POST":
        grievances_col.update_one({"_id":ObjectId(id)},{"$set":{
            "response":    request.form["response"],
            "status":      request.form["status"],
            "resolved_on": today() if request.form["status"]=="Resolved" else "",
        }})
        flash("Response saved!","success"); return redirect(url_for("grievances"))
    return render_template("grievances/respond.html",grievance=g)

@app.route("/grievances/delete/<id>")
@admin_required
def delete_grievance(id):
    grievances_col.delete_one({"_id":ObjectId(id)})
    flash("Grievance deleted.","danger"); return redirect(url_for("grievances"))

# ── Student: submit grievance ──────────────────────────────────────────────────
@app.route("/student/grievances", methods=["GET","POST"])
@student_required
def student_grievances():
    student = get_student()
    if not student: return redirect(url_for("logout"))
    my_g = list(grievances_col.find({"roll_no":student.get("roll_no","")}).sort("_id",DESCENDING))
    if request.method=="POST":
        grievances_col.insert_one({
            "roll_no":     student.get("roll_no",""),
            "student_name":student["name"],
            "course":      student.get("course",""),
            "category":    request.form["category"],
            "subject":     request.form["subject"],
            "description": request.form["description"],
            "status":      "Open",
            "response":    "",
            "submitted_on":today(),
            "resolved_on": "",
        })
        flash("Grievance submitted. Admin will respond shortly.","success")
        return redirect(url_for("student_grievances"))
    return render_template("student/grievances.html",student=student,grievances=my_g)

# ═══════════════════════════════════════════════════════════════════════════════
# HOSTEL
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/hostel")
@admin_required
def hostel():
    q = request.args.get("q","")
    qr = {"$or":[{"student_name":{"$regex":q,"$options":"i"}},
                 {"room_no":{"$regex":q,"$options":"i"}}]} if q else {}
    return render_template("hostel/index.html",
        records=list(hostel_col.find(qr).sort("room_no",1)), q=q)

@app.route("/hostel/add", methods=["GET","POST"])
@admin_required
def add_hostel():
    students_list=list(students_col.find({},{"name":1,"roll_no":1}))
    if request.method=="POST":
        hostel_col.insert_one({k:request.form.get(k,"") for k in
            ["roll_no","student_name","room_no","hostel_name","room_type",
             "joining_date","fees_per_month","status","remarks"]})
        flash("Hostel record added!","success"); return redirect(url_for("hostel"))
    return render_template("hostel/add.html",students=students_list)

@app.route("/hostel/edit/<id>", methods=["GET","POST"])
@admin_required
def edit_hostel(id):
    record = hostel_col.find_one({"_id":ObjectId(id)})
    students_list=list(students_col.find({},{"name":1,"roll_no":1}))
    if request.method=="POST":
        hostel_col.update_one({"_id":ObjectId(id)},{"$set":{k:request.form.get(k,"") for k in
            ["roll_no","student_name","room_no","hostel_name","room_type",
             "joining_date","fees_per_month","status","remarks"]}})
        flash("Hostel record updated!","success"); return redirect(url_for("hostel"))
    return render_template("hostel/edit.html",record=record,students=students_list)

@app.route("/hostel/delete/<id>")
@admin_required
def delete_hostel(id):
    hostel_col.delete_one({"_id":ObjectId(id)})
    flash("Record removed.","danger"); return redirect(url_for("hostel"))

# ═══════════════════════════════════════════════════════════════════════════════
# TEACHER PORTAL
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/teacher/dashboard")
@teacher_required
def teacher_dashboard():
    teacher = get_teacher()
    if not teacher: flash("Teacher record not linked.","danger"); return redirect(url_for("logout"))
    subject      = teacher.get("subject","")
    marked_today = attendance_col.count_documents({"subject":subject,"date":today()})
    total_marked = attendance_col.count_documents({"subject":subject})
    recent       = list(attendance_col.find({"subject":subject}).sort("date",DESCENDING).limit(6))
    my_asgns     = list(assignments_col.find({"teacher_id":session.get("linked_id")}).sort("_id",DESCENDING).limit(5))
    upcoming_exams = list(exam_col.find({"subject":subject}).sort("exam_date",1).limit(3))
    notices      = list(notices_col.find().sort("date",DESCENDING).limit(3))
    return render_template("teacher/dashboard.html",
        teacher=teacher, marked_today=marked_today, total_marked=total_marked,
        recent=recent, my_asgns=my_asgns, upcoming_exams=upcoming_exams, notices=notices)

@app.route("/teacher/attendance", methods=["GET","POST"])
@teacher_required
def teacher_mark_attendance():
    teacher = get_teacher()
    if not teacher: return redirect(url_for("logout"))
    subject = teacher.get("subject","")
    courses_list  = list(courses_col.find({},{"name":1}))
    students_list = list(students_col.find({},{"name":1,"roll_no":1,"course":1,"semester":1}))
    if request.method=="POST":
        roll_nos=request.form.getlist("roll_no"); statuses=request.form.getlist("status")
        date=request.form["date"]; course=request.form["course"]
        if attendance_col.find_one({"subject":subject,"date":date,"course":course}):
            flash(f"Attendance for '{subject}' on {date} already marked.","warning")
            return redirect(url_for("teacher_attendance_history"))
        for rn,st in zip(roll_nos,statuses):
            s=students_col.find_one({"roll_no":rn})
            attendance_col.insert_one({"roll_no":rn,"name":s["name"] if s else rn,
                "course":course,"subject":subject,"date":date,"status":st,
                "marked_by":session.get("name"),"teacher_id":session.get("linked_id")})
        flash(f"Attendance saved for {len(roll_nos)} students.","success")
        return redirect(url_for("teacher_attendance_history"))
    return render_template("teacher/mark_attendance.html",teacher=teacher,subject=subject,
        students=students_list,courses=courses_list,now=today())

@app.route("/teacher/attendance/history")
@teacher_required
def teacher_attendance_history():
    teacher=get_teacher(); subject=teacher.get("subject","") if teacher else ""
    records=list(attendance_col.find({"subject":subject}).sort("date",DESCENDING))
    return render_template("teacher/history.html",records=records,teacher=teacher,subject=subject)

# ═══════════════════════════════════════════════════════════════════════════════
# STUDENT PORTAL
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/student/dashboard")
@student_required
def student_dashboard():
    student=get_student()
    if not student: flash("Student record not linked.","danger"); return redirect(url_for("logout"))
    rn=student.get("roll_no",""); course=student.get("course","")
    att=list(attendance_col.find({"roll_no":rn}))
    total=len(att); present=sum(1 for r in att if r.get("status")=="Present")
    pct=round((present/total)*100,1) if total else 0
    by_subject=defaultdict(lambda:{"present":0,"total":0})
    for r in att:
        sub=r.get("subject","General")
        by_subject[sub]["total"]+=1
        if r.get("status")=="Present": by_subject[sub]["present"]+=1
    results_list=list(results_col.find({"roll_no":rn}).sort("_id",DESCENDING).limit(3))
    recent_notices=list(notices_col.find({"$or":[{"target":"All"},{"target":"Students"}]}).sort("date",DESCENDING).limit(4))
    fees_pending=fees_col.count_documents({"roll_no":rn,"status":"Pending"})
    upcoming_exams=list(exam_col.find({"course":course}).sort("exam_date",1).limit(4))
    pending_asgns=assignments_col.count_documents({"$or":[{"course":course},{"course":"All"}]})
    upcoming_events=list(events_col.find().sort("date",1).limit(3))
    hostel_info=hostel_col.find_one({"roll_no":rn})
    return render_template("student/dashboard.html",
        student=student,total=total,present=present,pct=pct,by_subject=dict(by_subject),
        results=results_list,recent_notices=recent_notices,fees_pending=fees_pending,
        upcoming_exams=upcoming_exams,pending_asgns=pending_asgns,
        upcoming_events=upcoming_events,hostel_info=hostel_info)

@app.route("/student/profile")
@student_required
def student_profile():
    student=get_student()
    if not student: return redirect(url_for("logout"))
    course=courses_col.find_one({"name":student.get("course","")})
    hostel=hostel_col.find_one({"roll_no":student.get("roll_no","")})
    return render_template("student/profile.html",student=student,course=course,hostel=hostel)

@app.route("/student/attendance")
@student_required
def student_attendance():
    student=get_student()
    if not student: return redirect(url_for("logout"))
    rn=student.get("roll_no",""); sf=request.args.get("subject","")
    qr={"roll_no":rn}
    if sf: qr["subject"]=sf
    records=list(attendance_col.find(qr).sort("date",DESCENDING))
    subjects=attendance_col.distinct("subject",{"roll_no":rn})
    total=len(records); present=sum(1 for r in records if r.get("status")=="Present")
    absent=sum(1 for r in records if r.get("status")=="Absent")
    late=sum(1 for r in records if r.get("status")=="Late")
    pct=round((present/total)*100,1) if total else 0
    return render_template("student/attendance.html",student=student,records=records,
        subjects=subjects,subject_filter=sf,total=total,present=present,absent=absent,late=late,pct=pct)

@app.route("/student/results")
@student_required
def student_results():
    student=get_student()
    if not student: return redirect(url_for("logout"))
    return render_template("student/results.html",student=student,
        results=list(results_col.find({"roll_no":student.get("roll_no","")}).sort("_id",DESCENDING)))

@app.route("/student/fees")
@student_required
def student_fees():
    student=get_student()
    if not student: return redirect(url_for("logout"))
    rn=student.get("roll_no","")
    fees_list=list(fees_col.find({"roll_no":rn}).sort("due_date",1))
    total_paid=sum(int(f.get("amount",0)) for f in fees_list if f.get("status")=="Paid")
    total_pending=sum(int(f.get("amount",0)) for f in fees_list if f.get("status")=="Pending")
    return render_template("student/fees.html",student=student,fees=fees_list,
        total_paid=total_paid,total_pending=total_pending)

@app.route("/student/notices")
@student_required
def student_notices():
    return render_template("student/notices.html",
        notices=list(notices_col.find({"$or":[{"target":"All"},{"target":"Students"}]}).sort("date",DESCENDING)))

@app.route("/student/timetable")
@student_required
def student_timetable():
    student=get_student()
    if not student: return redirect(url_for("logout"))
    slots=list(timetable_col.find({"course":student.get("course","")}).sort([("day",1),("time_start",1)]))
    by_day=defaultdict(list)
    for s in slots: by_day[s["day"]].append(s)
    return render_template("student/timetable.html",student=student,by_day=dict(by_day),days=DAYS)

@app.route("/student/exam-schedule")
@student_required
def student_exam_schedule():
    student=get_student()
    if not student: return redirect(url_for("logout"))
    exams=list(exam_col.find({"course":student.get("course","")}).sort("exam_date",1))
    return render_template("student/exam_schedule.html",student=student,exams=exams)

@app.route("/student/events")
@student_required
def student_events():
    return render_template("student/events.html",
        events=list(events_col.find().sort("date",1)))

@app.route("/student/id-card")
@student_required
def student_my_id_card():
    student=get_student()
    if not student: return redirect(url_for("logout"))
    course=courses_col.find_one({"name":student.get("course","")})
    return render_template("students/id_card.html",student=student,course=course)

# ── API ────────────────────────────────────────────────────────────────────────
@app.route("/api/student/<roll_no>")
@login_required
def api_student(roll_no):
    s=students_col.find_one({"roll_no":roll_no})
    return jsonify({"name":s["name"],"course":s.get("course",""),"semester":s.get("semester","")}) if s else (jsonify({}),404)

@app.route("/api/stats")
@admin_required
def api_stats():
    return jsonify({
        "students":students_col.count_documents({}),
        "teachers":teachers_col.count_documents({}),
        "attendance_today":attendance_col.count_documents({"date":today()}),
        "open_grievances":grievances_col.count_documents({"status":"Open"}),
    })

if __name__=="__main__":
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
