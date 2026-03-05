from flask import Flask, render_template, request, redirect, session
import sqlite3, os
from functools import wraps

app = Flask(__name__)
app.secret_key = "secret123"
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ---------- DATABASE ----------
def get_db():
    return sqlite3.connect("database.db")

def login_required(role=None):
    def wrap(fn):
        @wraps(fn)
        def check(*args, **kwargs):
            if "user" not in session:
                return redirect("/")
            if role and session["role"] != role:
                return redirect("/")
            return fn(*args, **kwargs)
        return check
    return wrap

with get_db() as db:
    db.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id TEXT PRIMARY KEY,
        password TEXT,
        role TEXT
    )""")

    db.execute("""
    CREATE TABLE IF NOT EXISTS crops(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        farmer_id TEXT,
        crop TEXT,
        price INTEGER,
        image TEXT
    )""")

    if not db.execute("SELECT * FROM users WHERE role='admin'").fetchone():
        db.execute("INSERT INTO users VALUES('admin','admin123','admin')")
        db.commit()

# ---------- HOME ----------
@app.route("/", methods=["GET","POST"])
def home():
    msg = ""
    if request.method == "POST":
        action = request.form["action"]
        uid = request.form["id"]
        pw = request.form["password"]
        role = request.form["role"]

        db = get_db()

        if action == "signup":
            if role == "admin":
                msg = "Admin signup is locked"
            elif db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone():
                msg = "User already exists"
            else:
                db.execute("INSERT INTO users VALUES(?,?,?)",(uid,pw,role))
                db.commit()
                msg = "Signup successful. Please login."

        else:
            user = db.execute(
                "SELECT * FROM users WHERE id=? AND password=? AND role=?",
                (uid,pw,role)
            ).fetchone()

            if user:
                session["user"] = uid
                session["role"] = role
                return redirect(f"/{role}")
            msg = "Invalid login details"

    return render_template("home.html", msg=msg)

# ---------- FARMER ----------
@app.route("/farmer", methods=["GET","POST"])
@login_required("farmer")
def farmer():
    if request.method == "POST":
        crop = request.form["crop"]
        price = request.form["price"]
        img = request.files["image"]

        img.save(os.path.join(UPLOAD_FOLDER, img.filename))

        with get_db() as db:
            db.execute(
                "INSERT INTO crops (farmer_id,crop,price,image) VALUES (?,?,?,?)",
                (session["user"], crop, price, img.filename)
            )

    with get_db() as db:
        crops = db.execute(
            "SELECT * FROM crops WHERE farmer_id=?",
            (session["user"],)
        ).fetchall()

    return render_template("farmer.html", crops=crops)

# ---------- BUYER ----------
@app.route("/buyer")
@login_required("buyer")
def buyer():
    q = request.args.get("q","")
    price = request.args.get("price","")

    sql = "SELECT * FROM crops WHERE crop LIKE ?"
    params = [f"%{q}%"]

    if price:
        sql += " AND price<=?"
        params.append(price)

    with get_db() as db:
        crops = db.execute(sql, params).fetchall()

    return render_template("buyer.html", crops=crops)

# ---------- PAYMENT ----------
@app.route("/payment/<int:cid>", methods=["GET","POST"])
@login_required("buyer")
def payment(cid):
    with get_db() as db:
        crop = db.execute("SELECT * FROM crops WHERE id=?", (cid,)).fetchone()

    if request.method == "POST":
        return render_template("success.html")

    return render_template("payment.html", crop=crop)

# ---------- ADMIN ----------
@app.route("/admin")
@login_required("admin")
def admin():
    with get_db() as db:
        users = db.execute("SELECT * FROM users").fetchall()
        crops = db.execute("SELECT * FROM crops").fetchall()
    return render_template("admin.html", users=users, crops=crops)

@app.route("/delete_user/<uid>")
@login_required("admin")
def delete_user(uid):
    if uid != "admin":
        with get_db() as db:
            db.execute("DELETE FROM users WHERE id=?", (uid,))
            db.execute("DELETE FROM crops WHERE farmer_id=?", (uid,))
            db.commit()
    return redirect("/admin")

@app.route("/delete_crop/<int:cid>")
@login_required("admin")
def delete_crop(cid):
    with get_db() as db:
        db.execute("DELETE FROM crops WHERE id=?", (cid,))
        db.commit()
    return redirect("/admin")

# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

app.run(debug=True)
