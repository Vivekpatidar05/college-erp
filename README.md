# DSVV ERP System
### Dev Sanskriti Vishwavidyalaya, Haridwar

Full-featured College ERP with role-based auth, 15+ modules, analytics, and Render deployment.

---

## Quick Start (Local)
```bash
cp .env.example .env        # fill MONGO_URI + SECRET_KEY
pip install -r requirements.txt
python app.py               # → http://localhost:5000
```
**Default login:** `admin` / `admin123`

---

## Deploy to Render
1. Push repo to GitHub
2. Go to [render.com](https://render.com) → New Web Service → Connect GitHub repo
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
5. Add env vars: `MONGO_URI`, `SECRET_KEY`, `DB_NAME=dsvv_erp`
6. Deploy → open live URL

See **DEPLOYMENT_GUIDE.html** for full visual walkthrough.

---

## Modules (15+)

| Module | Admin | Teacher | Student |
|--------|-------|---------|---------|
| Dashboard + Analytics | ✅ Charts, stats | ✅ Subject overview | ✅ Personal stats |
| Students | ✅ Full CRUD + ID card | — | ✅ View own profile |
| Teachers | ✅ Full CRUD | ✅ View profile | — |
| Courses | ✅ Full CRUD | — | ✅ View enrolled |
| Attendance | ✅ All + CSV export | ✅ Own subject only | ✅ View own |
| Timetable | ✅ Manage slots | — | ✅ View own |
| Assignments | ✅ View submissions | ✅ Post + view | ✅ Submit online |
| Exam Schedule | ✅ Schedule | ✅ View | ✅ View own |
| Results | ✅ Add + auto-grade | — | ✅ Marksheet + print |
| Fees | ✅ CRUD + CSV | — | ✅ View own |
| Notices | ✅ CRUD + targeting | ✅ View | ✅ View |
| Events | ✅ Full CRUD | ✅ View | ✅ View |
| Library | ✅ Full CRUD | — | — |
| Hostel | ✅ Full CRUD | — | ✅ View own |
| Grievances | ✅ Respond | — | ✅ Submit + track |
| User Management | ✅ Full control | — | — |

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `MONGO_URI` | MongoDB Atlas connection string | ✅ |
| `SECRET_KEY` | Flask session secret | ✅ |
| `DB_NAME` | Database name (default: dsvv_erp) | Optional |

---

## Tech Stack
- **Backend:** Python 3.11 + Flask 3
- **Database:** MongoDB Atlas (PyMongo)
- **Auth:** Werkzeug hashing + Flask sessions (3 roles)
- **Server:** Gunicorn
- **Hosting:** Render
- **Frontend:** Jinja2 + custom CSS (dark theme) + Chart.js
- **Export:** CSV via Python csv module
