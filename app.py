from flask import Flask, render_template, request, redirect, session, Response
import sqlite3
from datetime import datetime
import csv
from io import StringIO

app = Flask(__name__)
app.secret_key = "secret123"

# 🔐 CONFIG
ALLOWED_ADMIN_EMAIL = "dl.1415.info@schools.sa.edu.au"
ADMIN_PIN = "admin123"


# ---------------- DB ----------------
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    # USERS
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            mobile TEXT UNIQUE,
            role TEXT,
            signature TEXT,
            accepted_terms INTEGER
        )
    ''')

    # LOGS
    c.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            sign_in TEXT,
            sign_out TEXT,
            note TEXT
        )
    ''')

    # ✅ ADD NOTE COLUMN IF IT DOESN'T EXIST
    try:
        c.execute("ALTER TABLE logs ADD COLUMN note TEXT")
    except:
        pass

    conn.commit()

    # ✅ AUTO CREATE ADMIN USER
    c.execute("SELECT * FROM users WHERE email=?", (ALLOWED_ADMIN_EMAIL,))
    admin = c.fetchone()

    if not admin:
        c.execute('''
            INSERT INTO users (name, email, mobile, role, signature, accepted_terms)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            "Admin",
            ALLOWED_ADMIN_EMAIL,
            "0000000000",
            "admin",
            "Admin",
            1
        ))
        conn.commit()

    conn.close()


init_db()


# ---------------- AUTO LOGOUT ----------------
def auto_signout_expired_users():
    conn = get_db()
    c = conn.cursor()

    now = datetime.now()
    today_7pm = now.replace(hour=19, minute=0, second=0, microsecond=0)

    if now >= today_7pm:
        c.execute('''
            SELECT id FROM logs
            WHERE sign_out IS NULL
        ''')

        active_logs = c.fetchall()

        for log in active_logs:
            c.execute('''
                UPDATE logs
                SET sign_out=?
                WHERE id=?
            ''', ("signed in expired by 19:00", log['id']))

        conn.commit()

    conn.close()


# ---------------- HOME ----------------
@app.route('/')
def home():
    return render_template("index.html")


# ---------------- GET STARTED ----------------
@app.route('/get-started')
def get_started():
    return render_template("get_started.html")


# ---------------- LOGIN PAGE ----------------
@app.route('/returning')
def returning():
    return render_template("login.html")


# ---------------- LOGIN ----------------
@app.route('/login', methods=['POST'])
def login():
    auto_signout_expired_users()

    login_id = request.form['login_id']
    pin = request.form.get('pin')

    conn = get_db()
    c = conn.cursor()

    # 🔐 ADMIN LOGIN
    if login_id.lower() == ALLOWED_ADMIN_EMAIL:
        if pin != ADMIN_PIN:
            conn.close()
            return render_template("login.html", error="Invalid admin PIN")

        c.execute("SELECT * FROM users WHERE email=?", (ALLOWED_ADMIN_EMAIL,))
        user = c.fetchone()
    else:
        c.execute(
            "SELECT * FROM users WHERE email=? OR mobile=?",
            (login_id, login_id)
        )
        user = c.fetchone()

    if not user:
        conn.close()
        return render_template("login.html", error="User not found")

    # 🔥 CHECK ALREADY SIGNED IN
    c.execute('''
        SELECT * FROM logs
        WHERE user_id=? AND sign_out IS NULL
    ''', (user['id'],))

    active_log = c.fetchone()

    if active_log:
        conn.close()
        return render_template(
            "login.html",
            error="You are already signed in. Please click the Back button below and sign out first before continuing."
        )

    # ✅ LOGIN
    session['user_id'] = user['id']
    session['role'] = user['role']

    c.execute(
        "INSERT INTO logs (user_id, sign_in) VALUES (?, ?)",
        (user['id'], datetime.now())
    )

    conn.commit()
    conn.close()

    return redirect('/dashboard')


# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email'].lower().strip()
        mobile = request.form['mobile']
        role = request.form['role'].lower().strip()
        signature = request.form['signature']
        accepted_terms = request.form.get('terms')

        if not accepted_terms:
            return "You must accept terms"

        # 🔐 Restrict admin
        if role == "admin" and email != ALLOWED_ADMIN_EMAIL:
            return "Not allowed to register as admin"

        conn = get_db()
        c = conn.cursor()

        try:
            c.execute('''
                INSERT INTO users (name, email, mobile, role, signature, accepted_terms)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, email, mobile, role, signature, 1))

            conn.commit()

        except sqlite3.IntegrityError:
            conn.close()
            return "User already exists"

        conn.close()
        return redirect('/returning')

    return render_template("register.html")


# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
def dashboard():
    auto_signout_expired_users()

    if 'user_id' not in session:
        return redirect('/returning')

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT name FROM users WHERE id=?", (session['user_id'],))
    user = c.fetchone()

    c.execute('''
        SELECT sign_in FROM logs
        WHERE user_id=?
        ORDER BY id DESC LIMIT 1
    ''', (session['user_id'],))

    log = c.fetchone()
    conn.close()

    signin_time = "N/A"

    if log:
        try:
            dt = datetime.strptime(log['sign_in'], "%Y-%m-%d %H:%M:%S.%f")
            signin_time = dt.strftime("%d/%m/%Y %H:%M")
        except:
            signin_time = log['sign_in']

    return render_template(
        "dashboard.html",
        name=user['name'],
        role=session['role'],
        signin_time=signin_time
    )


# ---------------- LOGOUT ----------------
@app.route('/signout')
def signout_page():
    return render_template("signout.html")


@app.route('/logout', methods=['POST'])
def logout():
    login_id = request.form.get('login_id')

    conn = get_db()
    c = conn.cursor()

    c.execute(
        "SELECT id FROM users WHERE email=? OR mobile=?",
        (login_id, login_id)
    )

    user = c.fetchone()

    if user:
        c.execute('''
            UPDATE logs
            SET sign_out=?
            WHERE user_id=? AND sign_out IS NULL
        ''', (datetime.now(), user['id']))

        conn.commit()
        conn.close()
        return redirect('/next')

    conn.close()
    return "User not found"


# ---------------- TERMS ----------------
@app.route('/terms')
def terms():
    return render_template("terms.html")


# ---------------- NEXT VISITOR ----------------
@app.route('/next')
def next_visitor():
    return render_template("next.html")


# ---------------- SAVE NOTE ----------------
@app.route('/save_note', methods=['POST'])
def save_note():
    if session.get('role') != 'admin':
        return "Access denied"

    mobile = request.form.get('mobile')
    note = request.form.get('note')

    conn = get_db()
    c = conn.cursor()

    c.execute('''
        UPDATE logs
        SET note=?
        WHERE id = (
            SELECT logs.id
            FROM logs
            JOIN users ON users.id = logs.user_id
            WHERE users.mobile=?
            ORDER BY logs.id DESC
            LIMIT 1
        )
    ''', (note, mobile))

    conn.commit()
    conn.close()

    return redirect('/report')


# ---------------- REPORT ----------------
@app.route('/report')
def report():
    auto_signout_expired_users()

    if session.get('role') != 'admin':
        return "Access denied"

    conn = get_db()
    c = conn.cursor()

    c.execute('''
        SELECT users.name,
               users.mobile,
               users.role,
               logs.sign_in,
               logs.sign_out,
               logs.note
        FROM logs
        JOIN users ON users.id = logs.user_id
    ''')

    data = c.fetchall()
    conn.close()

    return render_template("report.html", data=data)


# ---------------- EXPORT CSV ----------------
@app.route('/export/csv')
def export_csv():
    if session.get('role') != 'admin':
        return "Access denied"

    conn = get_db()
    c = conn.cursor()

    c.execute('''
        SELECT users.name,
               users.mobile,
               users.role,
               logs.sign_in,
               logs.sign_out,
               logs.note
        FROM logs
        JOIN users ON users.id = logs.user_id
    ''')

    rows = c.fetchall()
    conn.close()

    si = StringIO()
    writer = csv.writer(si)

    writer.writerow(["Name", "Mobile", "Role", "Sign In", "Sign Out", "Note"])
    writer.writerows(rows)

    return Response(
        si.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=report.csv"}
    )


# ---------------- PRINT LABEL ----------------
@app.route('/print-label')
def print_label():
    if 'user_id' not in session:
        return redirect('/returning')

    if session.get('role') not in ['visitor', 'therapist', 'contractor', 'volunteer']:
        return "Access denied"

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT name, role FROM users WHERE id=?", (session['user_id'],))
    user = c.fetchone()

    c.execute('''
        SELECT sign_in FROM logs
        WHERE user_id=?
        ORDER BY id DESC LIMIT 1
    ''', (session['user_id'],))

    log = c.fetchone()
    conn.close()

    signin_time = "N/A"

    if log:
        try:
            dt = datetime.strptime(log['sign_in'], "%Y-%m-%d %H:%M:%S.%f")
            signin_time = dt.strftime("%d/%m/%Y %H:%M")
        except:
            signin_time = log['sign_in']

    return render_template(
        "label.html",
        name=user['name'],
        role=user['role'],
        signin_time=signin_time
    )


# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)