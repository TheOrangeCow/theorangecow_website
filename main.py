import os, secrets, subprocess, psutil
import time, threading, fcntl

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, abort
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash

import db
import sso
from projects import PROJECTS, get_project

app = Flask(__name__)
app.secret_key = os.environ.get("WEBHOOK_SECRET")
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

db.init_db()


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return db.get_user_by_id(uid)


@app.context_processor
def inject_user():
    return {"current_user": current_user()}


def get_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return session["csrf_token"]


@app.context_processor
def inject_csrf():
    return {"csrf_token": get_csrf_token()}


def csrf_ok():
    sent = request.form.get("csrf_token", "")
    return bool(sent) and sent == session.get("csrf_token")


def safe_next(target):
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return "/"


@app.route("/login", methods=["GET", "POST"])
def login():
    next_url = safe_next(request.args.get("next") or request.form.get("next"))

    if request.method == "POST":
        if not csrf_ok():
            flash("That form expired - try again.", "error")
            return redirect(url_for("login", next=next_url))

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = db.get_user_by_username(username)
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            return redirect(next_url)

        flash("Wrong username or password.", "error")
        return render_template("auth.html", mode="login", next=next_url)

    return render_template("auth.html", mode="login", next=next_url)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    next_url = safe_next(request.args.get("next") or request.form.get("next"))

    if request.method == "POST":
        if not csrf_ok():
            flash("That form expired - try again.", "error")
            return redirect(url_for("signup", next=next_url))

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if len(username) < 3:
            flash("Username needs to be at least 3 characters.", "error")
        elif len(password) < 8:
            flash("Password needs to be at least 8 characters.", "error")
        elif password != confirm:
            flash("Passwords don't match.", "error")
        elif db.get_user_by_username(username):
            flash("That username's taken.", "error")
        else:
            user_id = db.create_user(username, generate_password_hash(password))
            session["user_id"] = user_id
            return redirect(next_url)

        return render_template("auth.html", mode="signup", next=next_url)

    return render_template("auth.html", mode="signup", next=next_url)


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.pop("user_id", None)
    return redirect(url_for("index"))

@app.route("/sso/authorize")
def sso_authorize():
    client_id = request.args.get("client_id", "")
    redirect_uri = request.args.get("redirect_uri", "")

    client = sso.CLIENTS.get(client_id)
    if not client or redirect_uri != client["redirect_uri"]:
        return render_template("sso_error.html"), 400

    user = current_user()
    if not user:
        next_url = url_for("sso_authorize", client_id=client_id, redirect_uri=redirect_uri)
        return redirect(url_for("login", next=next_url))

    token = sso.issue_token(app.secret_key, user["id"], user["username"], client_id)
    return redirect(f"{redirect_uri}?token={token}")


@app.route("/sso/verify", methods=["POST"])
def sso_verify():
    data = request.get_json(silent=True) or request.form
    client_id = data.get("client_id", "")
    client_secret = data.get("client_secret", "")
    token = data.get("token", "")

    if not sso.check_client_secret(client_id, client_secret):
        return jsonify({"ok": False, "error": "bad client credentials"}), 401

    try:
        payload = sso.redeem_token(app.secret_key, token, client_id)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    return jsonify({
        "ok": True,
        "username": payload["username"],
        "cow_user_id": payload["uid"],
    })


def login_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapper


@app.route("/features", methods=["GET", "POST"])
@login_required
def features():
    user = current_user()

    if user == "theorangecow":
        admin = True
    else:
        admin = False

    if request.method == "POST":
        if not csrf_ok():
            flash("That form expired - try again.", "error")
            return redirect(url_for("features"))

        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()

        if not title:
            flash("Give it a title.", "error")
        else:
            db.create_feature_request(user["id"], user["username"], title, description)
            flash("Request submitted - thanks!", "success")
        return redirect(url_for("features"))

    requests_list = db.get_all_feature_requests()
    return render_template("features.html", requests=requests_list, admin=admin)


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    user = current_user()
    if request.method == "POST":
        if not csrf_ok():
            flash("That form expired - try again.", "error")
            return redirect(url_for("account"))

        action = request.form.get("action")

        if action == "change_username":
            new_username = request.form.get("new_username", "").strip()
            current_password = request.form.get("current_password_u", "")

            if not check_password_hash(user["password_hash"], current_password):
                flash("Current password is incorrect.", "error")
            elif len(new_username) < 3:
                flash("Username needs to be at least 3 characters.", "error")
            elif db.get_user_by_username(new_username):
                flash("That username's taken.", "error")
            else:
                db.update_username(user["id"], new_username)
                flash("Username updated.", "success")

        elif action == "change_password":
            current_password = request.form.get("current_password_p", "")
            new_password = request.form.get("new_password", "")
            confirm_password = request.form.get("confirm_password", "")

            if not check_password_hash(user["password_hash"], current_password):
                flash("Current password is incorrect.", "error")
            elif len(new_password) < 8:
                flash("New password needs to be at least 8 characters.", "error")
            elif new_password != confirm_password:
                flash("Passwords don't match.", "error")
            else:
                db.update_password(user["id"], generate_password_hash(new_password))
                flash("Password updated.", "success")

        return redirect(url_for("account"))

    return render_template("account.html")

def admin_required(f):
    from functools import wraps

    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()

        if not user:
            return redirect(url_for("login", next=request.path))

        if user["username"] != "theorangecow":
            return redirect(url_for("index"))

        return f(*args, **kwargs)

    return wrapper


@app.route("/admin/features", methods=["GET", "POST"])
@admin_required
def admin_features():
    if request.method == "POST":
        if not csrf_ok():
            flash("That form expired - try again.", "error")
            return redirect(url_for("admin_features"))

        feature_id = request.form.get("feature_id")
        new_status = request.form.get("status")

        valid_statuses = {"requested", "planned", "in_progress", "done", "declined"}

        if feature_id and new_status in valid_statuses:
            if new_status == "declined":
                db.delete_feature_request(int(feature_id))
                flash("Feature request declined and deleted.", "success")
            else:
                db.update_feature_status(int(feature_id), new_status)
                flash("Status updated.", "success")
        else:
            flash("Invalid status.", "error")

        return redirect(url_for("admin_features"))

    requests_list = db.get_all_feature_requests()
    return render_template("admin_features.html", requests=requests_list)


@app.route("/")
def index():
    roadmap = db.get_public_roadmap()
    return render_template("index.html", roadmap=roadmap)


@app.route("/library")
def library():
    return render_template("library.html")


@app.route("/projects")
def projects_list():
    return render_template("projects.html", projects=PROJECTS)


@app.route("/projects/<slug>")
def project_detail(slug):
    project = get_project(slug)
    if not project:
        abort(404)
    return render_template("project_detail.html", project=project)

@app.route("/admin")
@admin_required
def admin_page():
    return render_template("admin.html")


APPLICATIONS = {
    "flaskapp": {
        "name": "TheOrangeCow",
        "path": "/var/www/flaskapp",
        "port": 5000
    },
    "brainwave": {
        "name": "Brain Wave",
        "path": "/var/www/brainwave",
        "port": 7000
    },
    "fun": {
        "name": "Cow.fun",
        "path": "/var/www/fun",
        "port": 6002
    },
    "libary": {
        "name": "Library",
        "path": "/var/www/libary",
        "port": 6000
    },
    "sockets": {
        "name": "Cow Servers",
        "path": "/var/www/sockets",
        "port": 6001
    },
    "post": {
        "name": "post",
        "path": "/var/www/post",
        "port": 6500
    },
    "codeforge":{
        "name": "CodeForge",
        "path": "/var/www/codeforge",
        "port": 6600
    }
}

MAIN_APP = "flaskapp"
AUTO_SHUTDOWN_SECONDS = 30 * 60 
_last_start_attempt = {}


def get_port_pids(port):
    result = subprocess.run(
        ["sudo", "fuser", f"{port}/tcp"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return []
    return [int(p) for p in result.stdout.split() if p.isdigit()]


def get_uptime_seconds(pids):
    started = []
    for pid in pids:
        try:
            started.append(psutil.Process(pid).create_time())
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return time.time() - min(started) if started else 0


def auto_shutdown_loop():
    while True:
        time.sleep(60)
        for key, application in APPLICATIONS.items():
            if key == MAIN_APP:
                continue
            pids = get_port_pids(application["port"])
            if pids and get_uptime_seconds(pids) > AUTO_SHUTDOWN_SECONDS:
                subprocess.run(["sudo", "fuser", "-k", f"{application['port']}/tcp"])


def start_auto_shutdown():
    lock = open("/tmp/orangecow_autoshutdown.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return
    app._autoshutdown_lock = lock
    threading.Thread(target=auto_shutdown_loop, daemon=True).start()


start_auto_shutdown()


def get_application_stats(port):
    result = subprocess.run(
        ["sudo", "fuser", f"{port}/tcp"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        return {
            "running": False,
            "cpu": 0,
            "memory": 0,
            "memory_mb": 0
        }

    pids = []

    for part in result.stdout.split():
        if part.isdigit():
            pids.append(int(part))

    total_cpu = 0
    total_memory = 0
    total_memory_mb = 0

    for pid in pids:
        try:
            process = psutil.Process(pid)

            total_cpu += process.cpu_percent(interval=0.1)

            memory = process.memory_info().rss

            total_memory += process.memory_percent()
            total_memory_mb += memory / (1024 * 1024)

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return {
        "running": True,
        "cpu": round(total_cpu, 1),
        "memory": round(total_memory, 1),
        "memory_mb": round(total_memory_mb, 1)
    }

@app.route("/control")
@admin_required
def control():
    applications = {}

    for key, application in APPLICATIONS.items():
        stats = get_application_stats(application["port"])

        applications[key] = {
            **application,
            **stats
        }

    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    server = {
        "cpu": psutil.cpu_percent(interval=0.5),
        "memory": memory.percent,
        "memory_used": round(memory.used / (1024 ** 3), 2),
        "memory_total": round(memory.total / (1024 ** 3), 2),
        "disk": disk.percent,
        "disk_used": round(disk.used / (1024 ** 3), 2),
        "disk_total": round(disk.total / (1024 ** 3), 2)
    }

    return render_template(
        "control.html",
        applications=applications,
        server=server
    )


@app.route("/control/<name>/start", methods=["POST"])
@admin_required
def control_start(name):
    if not csrf_ok():
        flash("That form expired - try again.", "error")
        return redirect(url_for("control"))

    application = APPLICATIONS.get(name)

    if not application:
        abort(404)

    subprocess.Popen(
        ["bash", os.path.join(application["path"], "update_app.sh")],
        cwd=application["path"]
    )

    flash(f"{application['name']} update started.", "success")

    return redirect(url_for("control"))


@app.route("/control/<name>/stop", methods=["POST"])
@admin_required
def control_stop(name):
    if not csrf_ok():
        flash("That form expired - try again.", "error")
        return redirect(url_for("control"))

    application = APPLICATIONS.get(name)

    if not application:
        abort(404)

    subprocess.run(
        ["sudo", "fuser", "-k", f"{application['port']}/tcp"]
    )

    flash(f"{application['name']} stopped.", "success")

    return redirect(url_for("control"))


@app.route("/control/<name>/restart", methods=["POST"])
@admin_required
def control_restart(name):
    if not csrf_ok():
        flash("That form expired - try again.", "error")
        return redirect(url_for("control"))

    application = APPLICATIONS.get(name)

    if not application:
        abort(404)

    subprocess.run(
        ["sudo", "fuser", "-k", f"{application['port']}/tcp"]
    )

    subprocess.Popen(
        ["bash", os.path.join(application["path"], "update_app.sh")],
        cwd=application["path"]
    )

    flash(f"{application['name']} restarted.", "success")

    return redirect(url_for("control"))

@app.route("/server-down")
def server_down():
    key = request.args.get("app", "")
    application = APPLICATIONS.get(key)
    if not application or key == MAIN_APP:
        abort(404)
    return render_template(
        "server_down.html",
        key=key,
        application=application,
        starting=request.args.get("starting") == "1",
    )


@app.route("/server-down/<name>/start", methods=["POST"])
def server_down_start(name):
    application = APPLICATIONS.get(name)
    if not application or name == MAIN_APP:
        abort(404)

    if not csrf_ok():
        flash("That form expired - try again.", "error")
        return redirect(url_for("server_down", app=name))

    if not current_user():
        flash("Log in to start the server.", "error")
        return redirect(url_for("login", next=url_for("server_down", app=name)))

    already_running = bool(get_port_pids(application["port"]))
    recently_tried = time.time() - _last_start_attempt.get(name, 0) < 60

    if not already_running and not recently_tried:
        _last_start_attempt[name] = time.time()
        subprocess.Popen(
            ["bash", os.path.join(application["path"], "update_app.sh")],
            cwd=application["path"]
        )

    return redirect(url_for("server_down", app=name, starting=1))


@app.route("/server-down/<name>/status")
def server_down_status(name):
    application = APPLICATIONS.get(name)
    if not application or name == MAIN_APP:
        abort(404)
    return jsonify({"running": bool(get_port_pids(application["port"]))})

if __name__ == "__main__":
    app.run(debug=True)
