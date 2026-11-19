# Cognitive Performance Monitoring System

**Final Year Project — Objective 3**

Web-based system for continuous detection of early cognitive performance changes using interaction patterns (typing speed, response time, memory/concentration, mouse movement, click intervals).

**Key behaviours:** personal baseline from the first 3 cycles, per-metric deviation scores, alerts only when declines persist across consecutive cycles, paste/impossible-time validation, consent + not-a-diagnosis disclaimer, anonymised researcher IDs, in-app email inbox (optional SMTP), and CSV/PDF researcher exports.

---

## Technology Stack

| Layer    | Technology        |
|----------|-------------------|
| Frontend | HTML5, CSS3, JavaScript, Bootstrap 5 |
| Backend  | Python Flask (MVC)  |
| Database | MySQL (XAMPP)       |
| Auth     | Flask-Login + RBAC  |

---

## Project Structure

```
cognitive_monitoring/
├── app/
│   ├── __init__.py              # Flask app factory, extension init
│   ├── config.py                # Environment & database configuration
│   ├── controllers/             # MVC Controllers (Flask blueprints)
│   │   ├── main_controller.py   # Public landing & publications
│   │   ├── auth_controller.py     # Login, register, logout
│   │   ├── user_controller.py     # User dashboard & assessments
│   │   ├── researcher_controller.py
│   │   └── admin_controller.py
│   ├── models/                  # MVC Models (SQLAlchemy ORM)
│   │   ├── role.py              # RBAC roles
│   │   ├── user.py              # All system actors
│   │   ├── session.py           # Login/assessment sessions
│   │   ├── task.py              # Assessment attempts
│   │   ├── interaction_data.py  # Raw interaction metrics
│   │   ├── cognitive_metrics.py # Per-attempt scores
│   │   ├── aggregated_metrics.py
│   │   ├── alert.py
│   │   ├── publication.py
│   │   ├── feedback_request.py
│   │   ├── feedback.py
│   │   ├── analytics_report.py
│   │   ├── system_log.py
│   │   └── system_settings.py
│   ├── templates/               # MVC Views (Jinja2 HTML)
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/
│   └── utils/
│       ├── decorators.py        # RBAC route protection
│       ├── helpers.py           # Logging, session tokens
│       └── metrics.py           # Score calculation (no ML)
├── database/
│   ├── schema.sql               # Full MySQL schema
│   └── seed.sql                 # Optional seed data
├── init_db.py                   # Python DB setup script
├── run.py                       # Start Flask server
├── requirements.txt
└── .env.example
```

---

## Setup Instructions (XAMPP MySQL)

This project uses **XAMPP MySQL only** for the database. The website runs on **Flask (Python, port 5000)** — you do **not** need to start Apache in XAMPP.

| Component | What to use |
|-----------|-------------|
| Database | XAMPP MySQL — port **3306**, user **root**, password **(blank)** |
| Database name | **`cognitive_monitoring_db`** |
| Website | Python Flask — port **5000** (`START_SERVER.bat` or `python run.py`) |
| phpMyAdmin | http://localhost/phpmyadmin (optional, for viewing tables) |

### phpMyAdmin: why you see a *cognitive* folder

phpMyAdmin groups databases that share the same prefix before `_`. If you see:

- *cognitive* (folder icon — not a database, not an emoji)
  - `cognitive_monitoring_db` ← **this project uses this one**
  - `cognitive_performance_db` ← extra/old database; safe to ignore or delete if unused

### 1. Start XAMPP MySQL
- Open XAMPP Control Panel
- Click **Start** on **MySQL** only

### 2. One-time setup
```bash
cd cognitive_monitoring
pip install -r requirements.txt
copy .env.example .env
python init_db.py
```
`init_db.py` creates `cognitive_monitoring_db` automatically if it is missing.

### 3. Run the website
Double-click `START_SERVER.bat`, or:
```bash
python run.py
```
Open http://127.0.0.1:5000

### Optional: import schema via phpMyAdmin
- Open http://localhost/phpmyadmin
- Select `cognitive_monitoring_db` → Import → `database/schema.sql`

### Default Accounts (after init_db.py)
| Role       | Email                              | Password        |
|------------|------------------------------------|-----------------|
| Admin      | admin@cognitivemonitor.com         | Admin@123       |
| Researcher | researcher@cognitivemonitor.com    | Researcher@123  |
| User       | user@cognitivemonitor.com          | User@123        |

### Email verification (Brevo)
New self-registrations must verify a 6-digit OTP before login.

1. Create a free [Brevo](https://www.brevo.com/) account and verify it  
2. **Settings → SMTP & API → API Keys** → create an API v3 key  
3. **Senders** → add/verify your sender email  
4. Put values in `.env` (never in frontend JS):

```
BREVO_API_KEY=your_api_key_here
BREVO_SENDER_EMAIL=noreply@yourdomain.com
BREVO_SENDER_NAME=CogMonitor
```

Security defaults: 6-digit OTP, 10-minute expiry, 60s resend cooldown, max 5 attempts, hashed OTP storage. Seeded/admin-created accounts are pre-verified.

---

## Database ER Relationships

```
ROLE (1) ──────< USER (N)
USER (1) ──────< SESSION (N)
SESSION (1) ───< TASK (N)
TASK (1) ──────< INTERACTION_DATA (N)
USER (1) ──────< COGNITIVE_METRICS (N)
USER (1) ──────< AGGREGATED_METRICS (N)
USER (1) ──────< ALERT (N)
USER (1) ──────< PUBLICATION (N)  [researcher as author]
USER (1) ──────< FEEDBACK_REQUEST (N)
FEEDBACK_REQUEST (1) ── FEEDBACK (1)
USER (1) ──────< ANALYTICS_REPORT (N)
USER (1) ──────< SYSTEM_LOG (N)
```

---

## Module Build Progress

| Module | Status | Description |
|--------|--------|-------------|
| 1 | Complete | Project structure, DB schema, Flask foundation |
| 2 | Complete | Authentication & RBAC (login, register, role redirects) |
| 3 | Complete | Welcome/Landing page & public publications |
| 4 | Complete | User dashboard, profile, settings, notifications |
| 5 | Complete | Cognitive assessments (Typing + Reaction, cycle-based) |
| 6 | Complete | Continuous monitoring, trend detection, alerts |
| 7 | Complete | Researcher module (participants, feedback, analytics) |
| 8 | Complete | Publications module |
| 9 | Complete | Admin module (users, alerts, logs, settings) |

## Continuous Monitoring

The system tracks **assessment cycles** (default 5 attempts per test: typing, reaction, memory). After each cycle:

- Aggregated metrics + deviation scores vs personal baseline (cycles 1–3)
- Cycles outside the baseline band are **flagged** on charts
- Alerts fire only when flags **persist** across consecutive post-baseline cycles
- Invalid attempts (paste, impossible reaction times, too few keystrokes) are rejected
- Device type and practice attempts are recorded (practice does not count)
- Users get in-app notifications + Profile → Email inbox (SMTP optional via `.env`)

Interaction patterns captured per assessment:
- **Typing speed** (WPM)
- **Response time** (ms)
- **Memory / concentration score**
- **Mouse movement distance** and **click intervals**
- **Task completion duration** (ms)
- **Error rate**

---

## File Reference

See inline comments in each `.py` file for detailed explanations.
