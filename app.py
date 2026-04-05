from flask import (Flask, render_template, request, redirect,
                   url_for, flash, session, jsonify)
from pymongo import MongoClient
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "educore_erp_secret_2024_xK9#mP")

# ── MongoDB ────────────────────────────────────────────────────────────────────
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client[os.environ.get("DB_NAME", "college_erp")]

users_col      = db["users"]
students_col   = db["students"]
teachers_col   = db["teachers"]
courses_col    = db["courses"]
attendance_col = db["attendance"]
fees_col       = db["fees"]
results_col    = db["results"]
notices_col    = db["notices"]
library_col    = db["library"]

# ── Bootstrap default admin ────────────────────────────────────────────────────
def seed_admin():
    if not users_col.find_one({"role": "admin"}):
        users_col.insert_one({
            "username":   "admin",
            "password":   generate_password_hash("admin123"),
            "role":       "admin",
            "name":       "Super Administrator",
            "linked_id":  None,
            "active":     True,
            "created_at": datetime.now().strftime("%Y-%m-%d"),
        })
        print("Default admin created  ->  admin / admin123")

seed_admin()

# ═══════════════════════════════════════════════════════════════════════════════
# DECORATORS
# ═══════════════════════════════════════════════════════════════════════════════
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in.", "warning")
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return decorated

def teacher_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") != "teacher":
            flash("Access denied.", "danger")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return decorated

def student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") != "student":
            flash("Access denied.", "danger")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return decorated

# ── Role-based home redirect ───────────────────────────────────────────────────
@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))
    role = session.get("role")
    if role == "admin":   return redirect(url_for("dashboard"))
    if role == "teacher": return redirect(url_for("teacher_dashboard"))
    if role == "student": return redirect(url_for("student_dashboard"))
    return redirect(url_for("login"))

# ═══════════════════════════════════════════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("home"))
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        user = users_col.find_one({"username": username})
        if not user or not check_password_hash(user["password"], password):
            flash("Invalid username or password.", "danger")
            return render_template("auth/login.html")
        if not user.get("active", True):
            flash("Account deactivated. Contact administrator.", "danger")
            return render_template("auth/login.html")
        session["user_id"]   = str(user["_id"])
        session["username"]  = user["username"]
        session["role"]      = user["role"]
        session["name"]      = user["name"]
        session["linked_id"] = str(user["linked_id"]) if user.get("linked_id") else None
        flash(f"Welcome, {user['name']}!", "success")
        return redirect(url_for("home"))
    return render_template("auth/login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN – Dashboard
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/dashboard")
@admin_required
def dashboard():
    stats = {
        "students":     students_col.count_documents({}),
        "teachers":     teachers_col.count_documents({}),
        "courses":      courses_col.count_documents({}),
        "notices":      notices_col.count_documents({}),
        "library":      library_col.count_documents({}),
        "fees_pending": fees_col.count_documents({"status": "Pending"}),
        "users":        users_col.count_documents({}),
    }
    recent_students = list(students_col.find().sort("_id", -1).limit(5))
    recent_notices  = list(notices_col.find().sort("date", -1).limit(5))
    return render_template("dashboard.html", stats=stats,
                           recent_students=recent_students,
                           recent_notices=recent_notices)

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN – User Management
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/admin/users")
@admin_required
def admin_users():
    all_users = list(users_col.find().sort("role", 1))
    return render_template("admin/users.html", users=all_users)

@app.route("/admin/users/add", methods=["GET", "POST"])
@admin_required
def admin_add_user():
    students_list = list(students_col.find({}, {"name": 1, "roll_no": 1}))
    teachers_list = list(teachers_col.find({}, {"name": 1, "emp_id": 1, "subject": 1}))
    if request.method == "POST":
        username = request.form["username"].strip()
        if users_col.find_one({"username": username}):
            flash("Username already taken.", "danger")
            return render_template("admin/users_add.html",
                                   students=students_list, teachers=teachers_list)
        role      = request.form["role"]
        linked_id = request.form.get("linked_id") or None
        name      = request.form.get("name", "").strip()
        if not name and linked_id:
            rec = (students_col if role == "student" else teachers_col).find_one(
                {"_id": ObjectId(linked_id)})
            if rec:
                name = rec["name"]
        users_col.insert_one({
            "username":   username,
            "password":   generate_password_hash(request.form["password"]),
            "role":       role,
            "name":       name or username,
            "linked_id":  ObjectId(linked_id) if linked_id else None,
            "active":     True,
            "created_at": datetime.now().strftime("%Y-%m-%d"),
        })
        flash(f"User '{username}' ({role}) created!", "success")
        return redirect(url_for("admin_users"))
    return render_template("admin/users_add.html",
                           students=students_list, teachers=teachers_list)

@app.route("/admin/users/edit/<id>", methods=["GET", "POST"])
@admin_required
def admin_edit_user(id):
    user          = users_col.find_one({"_id": ObjectId(id)})
    students_list = list(students_col.find({}, {"name": 1, "roll_no": 1}))
    teachers_list = list(teachers_col.find({}, {"name": 1, "emp_id": 1, "subject": 1}))
    if request.method == "POST":
        upd = {
            "name":      request.form["name"],
            "role":      request.form["role"],
            "active":    request.form.get("active") == "on",
            "linked_id": ObjectId(request.form["linked_id"])
                         if request.form.get("linked_id") else None,
        }
        new_pw = request.form.get("password", "").strip()
        if new_pw:
            upd["password"] = generate_password_hash(new_pw)
        users_col.update_one({"_id": ObjectId(id)}, {"$set": upd})
        flash("User updated.", "success")
        return redirect(url_for("admin_users"))
    return render_template("admin/users_edit.html", user=user,
                           students=students_list, teachers=teachers_list)

@app.route("/admin/users/toggle/<id>")
@admin_required
def admin_toggle_user(id):
    user = users_col.find_one({"_id": ObjectId(id)})
    if user:
        if (user["role"] == "admin"
                and users_col.count_documents({"role": "admin", "active": True}) <= 1
                and user.get("active", True)):
            flash("Cannot deactivate the only active admin.", "danger")
            return redirect(url_for("admin_users"))
        new_state = not user.get("active", True)
        users_col.update_one({"_id": ObjectId(id)}, {"$set": {"active": new_state}})
        flash(f"'{user['username']}' {'activated' if new_state else 'deactivated'}.", "success")
    return redirect(url_for("admin_users"))

@app.route("/admin/users/delete/<id>")
@admin_required
def admin_delete_user(id):
    user = users_col.find_one({"_id": ObjectId(id)})
    if user and user["role"] == "admin" and users_col.count_documents({"role": "admin"}) <= 1:
        flash("Cannot delete the only admin account.", "danger")
        return redirect(url_for("admin_users"))
    users_col.delete_one({"_id": ObjectId(id)})
    flash("User deleted.", "danger")
    return redirect(url_for("admin_users"))

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN – Students
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/students")
@admin_required
def students():
    q = request.args.get("q", "")
    query = {"$or": [{"name": {"$regex": q, "$options": "i"}},
                     {"roll_no": {"$regex": q, "$options": "i"}}]} if q else {}
    return render_template("students/index.html",
                           students=list(students_col.find(query).sort("name", 1)), q=q)

@app.route("/students/add", methods=["GET", "POST"])
@admin_required
def add_student():
    courses = list(courses_col.find({}, {"name": 1}))
    if request.method == "POST":
        students_col.insert_one({
            "roll_no":    request.form["roll_no"],  "name":    request.form["name"],
            "email":      request.form["email"],     "phone":   request.form["phone"],
            "dob":        request.form["dob"],       "gender":  request.form["gender"],
            "course":     request.form["course"],    "year":    request.form["year"],
            "address":    request.form["address"],
            "created_at": datetime.now().strftime("%Y-%m-%d"),
        })
        flash("Student added!", "success")
        return redirect(url_for("students"))
    return render_template("students/add.html", courses=courses)

@app.route("/students/edit/<id>", methods=["GET", "POST"])
@admin_required
def edit_student(id):
    student = students_col.find_one({"_id": ObjectId(id)})
    courses = list(courses_col.find({}, {"name": 1}))
    if request.method == "POST":
        students_col.update_one({"_id": ObjectId(id)}, {"$set": {
            "roll_no": request.form["roll_no"], "name":   request.form["name"],
            "email":   request.form["email"],   "phone":  request.form["phone"],
            "dob":     request.form["dob"],     "gender": request.form["gender"],
            "course":  request.form["course"],  "year":   request.form["year"],
            "address": request.form["address"],
        }})
        flash("Student updated!", "success")
        return redirect(url_for("students"))
    return render_template("students/edit.html", student=student, courses=courses)

@app.route("/students/delete/<id>")
@admin_required
def delete_student(id):
    students_col.delete_one({"_id": ObjectId(id)})
    flash("Student deleted.", "danger")
    return redirect(url_for("students"))

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN – Teachers
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/teachers")
@admin_required
def teachers():
    q = request.args.get("q", "")
    query = {"$or": [{"name":    {"$regex": q, "$options": "i"}},
                     {"subject": {"$regex": q, "$options": "i"}}]} if q else {}
    return render_template("teachers/index.html",
                           teachers=list(teachers_col.find(query).sort("name", 1)), q=q)

@app.route("/teachers/add", methods=["GET", "POST"])
@admin_required
def add_teacher():
    if request.method == "POST":
        teachers_col.insert_one({
            "emp_id":        request.form["emp_id"],
            "name":          request.form["name"],
            "email":         request.form["email"],
            "phone":         request.form["phone"],
            "subject":       request.form["subject"],
            "department":    request.form["department"],
            "qualification": request.form["qualification"],
            "experience":    request.form["experience"],
            "salary":        request.form["salary"],
            "joining_date":  request.form["joining_date"],
        })
        flash("Teacher added!", "success")
        return redirect(url_for("teachers"))
    return render_template("teachers/add.html")

@app.route("/teachers/edit/<id>", methods=["GET", "POST"])
@admin_required
def edit_teacher(id):
    teacher = teachers_col.find_one({"_id": ObjectId(id)})
    if request.method == "POST":
        teachers_col.update_one({"_id": ObjectId(id)}, {"$set": {
            "emp_id":        request.form["emp_id"],
            "name":          request.form["name"],
            "email":         request.form["email"],
            "phone":         request.form["phone"],
            "subject":       request.form["subject"],
            "department":    request.form["department"],
            "qualification": request.form["qualification"],
            "experience":    request.form["experience"],
            "salary":        request.form["salary"],
            "joining_date":  request.form["joining_date"],
        }})
        flash("Teacher updated!", "success")
        return redirect(url_for("teachers"))
    return render_template("teachers/edit.html", teacher=teacher)

@app.route("/teachers/delete/<id>")
@admin_required
def delete_teacher(id):
    teachers_col.delete_one({"_id": ObjectId(id)})
    flash("Teacher deleted.", "danger")
    return redirect(url_for("teachers"))

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN – Courses
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/courses")
@admin_required
def courses():
    return render_template("courses/index.html",
                           courses=list(courses_col.find().sort("name", 1)))

@app.route("/courses/add", methods=["GET", "POST"])
@admin_required
def add_course():
    if request.method == "POST":
        courses_col.insert_one({
            "code": request.form["code"], "name":     request.form["name"],
            "duration": request.form["duration"],     "seats": request.form["seats"],
            "fees": request.form["fees"], "dept":     request.form["dept"],
            "desc": request.form["desc"],
        })
        flash("Course added!", "success")
        return redirect(url_for("courses"))
    return render_template("courses/add.html")

@app.route("/courses/edit/<id>", methods=["GET", "POST"])
@admin_required
def edit_course(id):
    course = courses_col.find_one({"_id": ObjectId(id)})
    if request.method == "POST":
        courses_col.update_one({"_id": ObjectId(id)}, {"$set": {
            "code": request.form["code"], "name":     request.form["name"],
            "duration": request.form["duration"],     "seats": request.form["seats"],
            "fees": request.form["fees"], "dept":     request.form["dept"],
            "desc": request.form["desc"],
        }})
        flash("Course updated!", "success")
        return redirect(url_for("courses"))
    return render_template("courses/edit.html", course=course)

@app.route("/courses/delete/<id>")
@admin_required
def delete_course(id):
    courses_col.delete_one({"_id": ObjectId(id)})
    flash("Course deleted.", "danger")
    return redirect(url_for("courses"))

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN – Attendance
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/attendance")
@admin_required
def attendance():
    q = request.args.get("q", "")
    query = {"roll_no": {"$regex": q, "$options": "i"}} if q else {}
    records = list(attendance_col.find(query).sort("date", -1))
    return render_template("attendance/index.html", records=records,
                           students=list(students_col.find({}, {"name": 1, "roll_no": 1})),
                           q=q)

@app.route("/attendance/add", methods=["GET", "POST"])
@admin_required
def add_attendance():
    students_list = list(students_col.find({}, {"name": 1, "roll_no": 1, "course": 1}))
    courses_list  = list(courses_col.find({}, {"name": 1, "code": 1}))
    if request.method == "POST":
        roll_nos = request.form.getlist("roll_no")
        statuses = request.form.getlist("status")
        date     = request.form["date"]
        course   = request.form["course"]
        subject  = request.form.get("subject", "")
        for rn, st in zip(roll_nos, statuses):
            s = students_col.find_one({"roll_no": rn})
            attendance_col.insert_one({
                "roll_no": rn, "name":    s["name"] if s else rn,
                "course":  course, "subject": subject, "date": date,
                "status":  st, "marked_by": session.get("name", "Admin"),
            })
        flash(f"Attendance saved for {len(roll_nos)} students!", "success")
        return redirect(url_for("attendance"))
    return render_template("attendance/add.html",
                           students=students_list, courses=courses_list)

@app.route("/attendance/delete/<id>")
@admin_required
def delete_attendance(id):
    attendance_col.delete_one({"_id": ObjectId(id)})
    flash("Record deleted.", "danger")
    return redirect(url_for("attendance"))

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN – Fees
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/fees")
@admin_required
def fees():
    q  = request.args.get("q", "")
    sf = request.args.get("status", "")
    query = {}
    if q:
        query["$or"] = [{"student_name": {"$regex": q, "$options": "i"}},
                        {"roll_no":      {"$regex": q, "$options": "i"}}]
    if sf:
        query["status"] = sf
    return render_template("fees/index.html",
                           fees=list(fees_col.find(query).sort("due_date", 1)),
                           q=q, status_filter=sf)

@app.route("/fees/add", methods=["GET", "POST"])
@admin_required
def add_fee():
    students_list = list(students_col.find({}, {"name": 1, "roll_no": 1, "course": 1}))
    if request.method == "POST":
        fees_col.insert_one({
            "roll_no":      request.form["roll_no"],
            "student_name": request.form["student_name"],
            "course":       request.form["course"],
            "fee_type":     request.form["fee_type"],
            "amount":       request.form["amount"],
            "due_date":     request.form["due_date"],
            "paid_date":    request.form.get("paid_date", ""),
            "status":       request.form["status"],
            "remarks":      request.form.get("remarks", ""),
        })
        flash("Fee record added!", "success")
        return redirect(url_for("fees"))
    return render_template("fees/add.html", students=students_list)

@app.route("/fees/edit/<id>", methods=["GET", "POST"])
@admin_required
def edit_fee(id):
    fee = fees_col.find_one({"_id": ObjectId(id)})
    students_list = list(students_col.find({}, {"name": 1, "roll_no": 1, "course": 1}))
    if request.method == "POST":
        fees_col.update_one({"_id": ObjectId(id)}, {"$set": {
            "roll_no":      request.form["roll_no"],
            "student_name": request.form["student_name"],
            "course":       request.form["course"],
            "fee_type":     request.form["fee_type"],
            "amount":       request.form["amount"],
            "due_date":     request.form["due_date"],
            "paid_date":    request.form.get("paid_date", ""),
            "status":       request.form["status"],
            "remarks":      request.form.get("remarks", ""),
        }})
        flash("Fee record updated!", "success")
        return redirect(url_for("fees"))
    return render_template("fees/edit.html", fee=fee, students=students_list)

@app.route("/fees/delete/<id>")
@admin_required
def delete_fee(id):
    fees_col.delete_one({"_id": ObjectId(id)})
    flash("Fee record deleted.", "danger")
    return redirect(url_for("fees"))

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN – Results
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/results")
@admin_required
def results():
    q = request.args.get("q", "")
    query = {"$or": [{"student_name": {"$regex": q, "$options": "i"}},
                     {"roll_no":      {"$regex": q, "$options": "i"}}]} if q else {}
    return render_template("results/index.html",
                           results=list(results_col.find(query).sort("roll_no", 1)), q=q)

@app.route("/results/add", methods=["GET", "POST"])
@admin_required
def add_result():
    students_list = list(students_col.find({}, {"name": 1, "roll_no": 1, "course": 1}))
    if request.method == "POST":
        marks = {f"subject{i}": {
            "name": request.form[f"s{i}_name"],
            "marks": request.form[f"s{i}_marks"],
            "max":   request.form[f"s{i}_max"],
        } for i in range(1, 6)}
        total     = sum(int(v["marks"]) for v in marks.values())
        total_max = sum(int(v["max"])   for v in marks.values())
        pct       = round((total / total_max) * 100, 2) if total_max else 0
        grade     = ("A+" if pct>=90 else "A" if pct>=80 else "B" if pct>=70
                     else "C" if pct>=60 else "D" if pct>=50 else "F")
        results_col.insert_one({
            "roll_no":      request.form["roll_no"],
            "student_name": request.form["student_name"],
            "course":       request.form["course"],
            "semester":     request.form["semester"],
            "exam_type":    request.form["exam_type"],
            "marks":        marks, "total": total, "total_max": total_max,
            "percentage":   pct,   "grade": grade,
            "result":       "Pass" if pct >= 40 else "Fail",
        })
        flash("Result added!", "success")
        return redirect(url_for("results"))
    return render_template("results/add.html", students=students_list)

@app.route("/results/delete/<id>")
@admin_required
def delete_result(id):
    results_col.delete_one({"_id": ObjectId(id)})
    flash("Result deleted.", "danger")
    return redirect(url_for("results"))

@app.route("/results/view/<id>")
@login_required
def view_result(id):
    result = results_col.find_one({"_id": ObjectId(id)})
    if session.get("role") == "student":
        student = students_col.find_one({"_id": ObjectId(session["linked_id"])})
        if not student or result.get("roll_no") != student.get("roll_no"):
            flash("Access denied.", "danger")
            return redirect(url_for("student_results"))
    return render_template("results/view.html", result=result)

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN – Notices
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/notices")
@admin_required
def notices():
    return render_template("notices/index.html",
                           notices=list(notices_col.find().sort("date", -1)))

@app.route("/notices/add", methods=["GET", "POST"])
@admin_required
def add_notice():
    if request.method == "POST":
        notices_col.insert_one({
            "title":    request.form["title"],
            "category": request.form["category"],
            "content":  request.form["content"],
            "date":     datetime.now().strftime("%Y-%m-%d"),
            "priority": request.form["priority"],
            "author":   request.form["author"],
        })
        flash("Notice posted!", "success")
        return redirect(url_for("notices"))
    return render_template("notices/add.html")

@app.route("/notices/edit/<id>", methods=["GET", "POST"])
@admin_required
def edit_notice(id):
    notice = notices_col.find_one({"_id": ObjectId(id)})
    if request.method == "POST":
        notices_col.update_one({"_id": ObjectId(id)}, {"$set": {
            "title":    request.form["title"],   "category": request.form["category"],
            "content":  request.form["content"], "priority": request.form["priority"],
            "author":   request.form["author"],
        }})
        flash("Notice updated!", "success")
        return redirect(url_for("notices"))
    return render_template("notices/edit.html", notice=notice)

@app.route("/notices/delete/<id>")
@admin_required
def delete_notice(id):
    notices_col.delete_one({"_id": ObjectId(id)})
    flash("Notice deleted.", "danger")
    return redirect(url_for("notices"))

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN – Library
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/library")
@admin_required
def library():
    q = request.args.get("q", "")
    query = {"$or": [{"title":  {"$regex": q, "$options": "i"}},
                     {"author": {"$regex": q, "$options": "i"}},
                     {"isbn":   {"$regex": q, "$options": "i"}}]} if q else {}
    return render_template("library/index.html",
                           books=list(library_col.find(query).sort("title", 1)), q=q)

@app.route("/library/add", methods=["GET", "POST"])
@admin_required
def add_book():
    if request.method == "POST":
        library_col.insert_one({
            "isbn":      request.form["isbn"],      "title":    request.form["title"],
            "author":    request.form["author"],    "publisher":request.form["publisher"],
            "category":  request.form["category"],  "copies":   int(request.form["copies"]),
            "available": int(request.form["copies"]),
            "rack_no":   request.form["rack_no"],
            "added_date":datetime.now().strftime("%Y-%m-%d"),
        })
        flash("Book added!", "success")
        return redirect(url_for("library"))
    return render_template("library/add.html")

@app.route("/library/edit/<id>", methods=["GET", "POST"])
@admin_required
def edit_book(id):
    book = library_col.find_one({"_id": ObjectId(id)})
    if request.method == "POST":
        library_col.update_one({"_id": ObjectId(id)}, {"$set": {
            "isbn":      request.form["isbn"],      "title":    request.form["title"],
            "author":    request.form["author"],    "publisher":request.form["publisher"],
            "category":  request.form["category"],  "copies":   int(request.form["copies"]),
            "available": int(request.form["available"]),
            "rack_no":   request.form["rack_no"],
        }})
        flash("Book updated!", "success")
        return redirect(url_for("library"))
    return render_template("library/edit.html", book=book)

@app.route("/library/delete/<id>")
@admin_required
def delete_book(id):
    library_col.delete_one({"_id": ObjectId(id)})
    flash("Book removed.", "danger")
    return redirect(url_for("library"))

# ═══════════════════════════════════════════════════════════════════════════════
# TEACHER PORTAL
# ═══════════════════════════════════════════════════════════════════════════════
def get_teacher_record():
    lid = session.get("linked_id")
    return teachers_col.find_one({"_id": ObjectId(lid)}) if lid else None

@app.route("/teacher/dashboard")
@teacher_required
def teacher_dashboard():
    teacher = get_teacher_record()
    if not teacher:
        flash("No teacher record linked. Contact admin.", "danger")
        return redirect(url_for("logout"))
    subject      = teacher.get("subject", "")
    today        = datetime.now().strftime("%Y-%m-%d")
    marked_today = attendance_col.count_documents({"subject": subject, "date": today})
    total_marked = attendance_col.count_documents({"subject": subject})
    recent       = list(attendance_col.find({"subject": subject}).sort("date", -1).limit(8))
    notices      = list(notices_col.find().sort("date", -1).limit(3))
    return render_template("teacher/dashboard.html", teacher=teacher,
                           marked_today=marked_today, total_marked=total_marked,
                           recent=recent, notices=notices)

@app.route("/teacher/attendance", methods=["GET", "POST"])
@teacher_required
def teacher_mark_attendance():
    teacher = get_teacher_record()
    if not teacher:
        return redirect(url_for("logout"))
    subject       = teacher.get("subject", "")
    courses_list  = list(courses_col.find({}, {"name": 1}))
    students_list = list(students_col.find({}, {"name": 1, "roll_no": 1, "course": 1}))
    if request.method == "POST":
        roll_nos = request.form.getlist("roll_no")
        statuses = request.form.getlist("status")
        date     = request.form["date"]
        course   = request.form["course"]
        # Duplicate guard per subject+date+course
        if attendance_col.find_one({"subject": subject, "date": date, "course": course}):
            flash(f"Attendance for '{subject}' on {date} already marked for this course.", "warning")
            return redirect(url_for("teacher_attendance_history"))
        for rn, st in zip(roll_nos, statuses):
            s = students_col.find_one({"roll_no": rn})
            attendance_col.insert_one({
                "roll_no":    rn,
                "name":       s["name"] if s else rn,
                "course":     course,
                "subject":    subject,
                "date":       date,
                "status":     st,
                "marked_by":  session.get("name"),
                "teacher_id": session.get("linked_id"),
            })
        flash(f"Attendance saved for {len(roll_nos)} students in '{subject}'.", "success")
        return redirect(url_for("teacher_attendance_history"))
    return render_template("teacher/mark_attendance.html",
                           teacher=teacher, subject=subject,
                           students=students_list, courses=courses_list,
                           now=datetime.now().strftime("%Y-%m-%d"))

@app.route("/teacher/attendance/history")
@teacher_required
def teacher_attendance_history():
    teacher = get_teacher_record()
    subject = teacher.get("subject", "") if teacher else ""
    records = list(attendance_col.find({"subject": subject}).sort("date", -1))
    return render_template("teacher/history.html",
                           records=records, teacher=teacher, subject=subject)

# ═══════════════════════════════════════════════════════════════════════════════
# STUDENT PORTAL
# ═══════════════════════════════════════════════════════════════════════════════
def get_student_record():
    lid = session.get("linked_id")
    return students_col.find_one({"_id": ObjectId(lid)}) if lid else None

@app.route("/student/dashboard")
@student_required
def student_dashboard():
    student = get_student_record()
    if not student:
        flash("No student record linked. Contact admin.", "danger")
        return redirect(url_for("logout"))
    roll_no     = student.get("roll_no", "")
    att_records = list(attendance_col.find({"roll_no": roll_no}))
    total   = len(att_records)
    present = sum(1 for r in att_records if r.get("status") == "Present")
    pct     = round((present / total) * 100, 1) if total else 0
    by_subject = {}
    for r in att_records:
        sub = r.get("subject", "General")
        if sub not in by_subject:
            by_subject[sub] = {"present": 0, "total": 0}
        by_subject[sub]["total"] += 1
        if r.get("status") == "Present":
            by_subject[sub]["present"] += 1
    results_list   = list(results_col.find({"roll_no": roll_no}).sort("_id", -1).limit(3))
    recent_notices = list(notices_col.find().sort("date", -1).limit(4))
    fees_pending   = fees_col.count_documents({"roll_no": roll_no, "status": "Pending"})
    return render_template("student/dashboard.html",
                           student=student, total=total, present=present, pct=pct,
                           by_subject=by_subject, results=results_list,
                           recent_notices=recent_notices, fees_pending=fees_pending)

@app.route("/student/profile")
@student_required
def student_profile():
    student = get_student_record()
    if not student:
        return redirect(url_for("logout"))
    course = courses_col.find_one({"name": student.get("course", "")})
    return render_template("student/profile.html", student=student, course=course)

@app.route("/student/attendance")
@student_required
def student_attendance():
    student = get_student_record()
    if not student:
        return redirect(url_for("logout"))
    roll_no        = student.get("roll_no", "")
    subject_filter = request.args.get("subject", "")
    query = {"roll_no": roll_no}
    if subject_filter:
        query["subject"] = subject_filter
    records  = list(attendance_col.find(query).sort("date", -1))
    subjects = attendance_col.distinct("subject", {"roll_no": roll_no})
    total   = len(records)
    present = sum(1 for r in records if r.get("status") == "Present")
    absent  = sum(1 for r in records if r.get("status") == "Absent")
    late    = sum(1 for r in records if r.get("status") == "Late")
    pct     = round((present / total) * 100, 1) if total else 0
    return render_template("student/attendance.html",
                           student=student, records=records,
                           subjects=subjects, subject_filter=subject_filter,
                           total=total, present=present, absent=absent,
                           late=late, pct=pct)

@app.route("/student/results")
@student_required
def student_results():
    student = get_student_record()
    if not student:
        return redirect(url_for("logout"))
    results_list = list(results_col.find({"roll_no": student.get("roll_no", "")}).sort("_id", -1))
    return render_template("student/results.html", student=student, results=results_list)

@app.route("/student/fees")
@student_required
def student_fees():
    student = get_student_record()
    if not student:
        return redirect(url_for("logout"))
    roll_no   = student.get("roll_no", "")
    fees_list = list(fees_col.find({"roll_no": roll_no}).sort("due_date", 1))
    total_paid    = sum(int(f.get("amount", 0)) for f in fees_list if f.get("status") == "Paid")
    total_pending = sum(int(f.get("amount", 0)) for f in fees_list if f.get("status") == "Pending")
    return render_template("student/fees.html",
                           student=student, fees=fees_list,
                           total_paid=total_paid, total_pending=total_pending)

@app.route("/student/notices")
@student_required
def student_notices():
    return render_template("student/notices.html",
                           notices=list(notices_col.find().sort("date", -1)))

# ── API ────────────────────────────────────────────────────────────────────────
@app.route("/api/student/<roll_no>")
@login_required
def api_student(roll_no):
    s = students_col.find_one({"roll_no": roll_no})
    return jsonify({"name": s["name"], "course": s.get("course", "")}) if s else (jsonify({}), 404)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
