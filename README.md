# EduCore — College ERP System

Flask · MongoDB Atlas · Role-Based Auth · Railway-Ready

---

## Quick Start (Local)

```bash
cp .env.example .env        # fill in MONGO_URI and SECRET_KEY
pip install -r requirements.txt
python app.py               # runs on http://localhost:5000
```

Default login: **admin / admin123**

---

## Deploy to Railway

1. Push this repo to GitHub
2. Create new project on [railway.app](https://railway.app) → Deploy from GitHub
3. Add environment variables in Railway → Variables:
   - `MONGO_URI` = your MongoDB Atlas connection string
   - `SECRET_KEY` = a long random secret
   - `DB_NAME` = college_erp
4. Go to Settings → Generate Domain → open your live URL

See **DEPLOYMENT_GUIDE.html** for full step-by-step instructions.

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `MONGO_URI` | MongoDB Atlas connection string | ✅ Yes |
| `SECRET_KEY` | Flask session secret | ✅ Yes |
| `DB_NAME` | Database name (default: college_erp) | Optional |

---

## Project Structure

```
college_erp/
├── app.py                 ← Flask app (all routes + auth)
├── Procfile               ← Railway/Gunicorn start command
├── railway.json           ← Railway config
├── runtime.txt            ← Python version
├── requirements.txt       ← Dependencies
├── .env.example           ← Environment variable template
├── .gitignore
├── DEPLOYMENT_GUIDE.html  ← Full deployment walkthrough
├── static/
│   ├── css/style.css
│   └── js/main.js
└── templates/
    ├── auth/login.html
    ├── base.html
    ├── dashboard.html
    ├── admin/             ← User management (3 files)
    ├── student/           ← Student portal (6 files)
    ├── teacher/           ← Teacher portal (3 files)
    ├── students/          ← Admin CRUD (3 files)
    ├── teachers/          ← Admin CRUD (3 files)
    ├── courses/           ← Admin CRUD (3 files)
    ├── attendance/        ← Admin CRUD (2 files)
    ├── fees/              ← Admin CRUD (3 files)
    ├── results/           ← Admin CRUD (3 files)
    ├── notices/           ← Admin CRUD (3 files)
    └── library/           ← Admin CRUD (3 files)
```

---

## Roles

| Role | Access |
|------|--------|
| **Admin** | Full CRUD on all 8 modules + user management |
| **Teacher** | Mark attendance for their subject only |
| **Student** | Read-only: own profile, attendance, results, fees |

---

## Tech Stack

- **Backend**: Python 3.11 + Flask 3
- **Database**: MongoDB Atlas (via PyMongo)
- **Auth**: Werkzeug password hashing + Flask sessions
- **Server**: Gunicorn (production)
- **Hosting**: Railway
- **Frontend**: Jinja2 + vanilla CSS/JS (dark theme)
