
import os

from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, jsonify, abort
)

from flask_login import (
    LoginManager, login_user,
    login_required, logout_user, current_user
)

from flask_wtf.csrf import CSRFProtect

from werkzeug.security import (
    generate_password_hash, check_password_hash
)

from dotenv import load_dotenv

from models import db, User, Task


# LOAD ENVIRONMENT VARIABLES
load_dotenv()


# CREATE FLASK APPLICATION
app = Flask(__name__)


# APPLICATION CONFIGURATION
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

database_url = os.getenv("DATABASE_URL", "").strip()

if not database_url:
    raise RuntimeError("DATABASE_URL is missing in .env file")

app.config["SQLALCHEMY_DATABASE_URI"] = database_url

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


# INITIALIZE MYSQL DATABASE
db.init_app(app)


# CSRF PROTECTION
csrf = CSRFProtect(app)


# LOGIN MANAGER
login_manager = LoginManager()

login_manager.login_view = "login"

login_manager.init_app(app)


# LOAD LOGGED-IN USER
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# HOME ROUTE
@app.route("/")
def home():

    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


# USER REGISTRATION
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get("username", "").strip()

        email = request.form.get("email", "").strip().lower()

        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("All fields are required.", "error")
            return redirect(url_for("register"))

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return redirect(url_for("register"))

        existing_user = db.session.execute(
            db.select(User).filter_by(email=email)
        ).scalar_one_or_none()

        if existing_user:
            flash("Email already registered.", "error")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        user = User(
            username=username,
            email=email,
            password=hashed_password
        )

        db.session.add(user)

        db.session.commit()

        flash("Registration successful. Please login.", "success")

        return redirect(url_for("login"))

    return render_template("register.html")


# USER LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()

        password = request.form.get("password", "")

        user = db.session.execute(
            db.select(User).filter_by(email=email)
        ).scalar_one_or_none()

        if user and check_password_hash(user.password, password):

            login_user(user)

            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


# USER LOGOUT
@app.route("/logout", methods=["POST"])
@login_required
def logout():

    logout_user()

    flash("You have been logged out.", "success")

    return redirect(url_for("login"))


# DISPLAY TASKS
@app.route("/dashboard")
@login_required
def dashboard():

    tasks = db.session.execute(
        db.select(Task)
        .filter_by(user_id=current_user.id)
        .order_by(Task.id.desc())
    ).scalars().all()

    return render_template("dashboard.html", tasks=tasks)


# CREATE TASK
@app.route("/add", methods=["POST"])
@login_required
def add_task():

    title = request.form.get("title", "").strip()

    description = request.form.get("description", "").strip()

    if not title or len(title) > 150:

        flash(
            "Enter a valid task title (1-150 characters).",
            "error"
        )

        return redirect(url_for("dashboard"))

    task = Task(
        title=title,
        description=description,
        user_id=current_user.id
    )

    db.session.add(task)

    db.session.commit()

    flash("Task added successfully.", "success")

    return redirect(url_for("dashboard"))


# UPDATE TASK STATUS
@app.route("/complete/<int:task_id>", methods=["POST"])
@login_required
def complete_task(task_id):

    task = db.session.get(Task, task_id)

    if not task or task.user_id != current_user.id:
        abort(404)

    task.completed = not task.completed

    db.session.commit()

    return redirect(url_for("dashboard"))


# DELETE TASK
@app.route("/delete/<int:task_id>", methods=["POST"])
@login_required
def delete_task(task_id):

    task = db.session.get(Task, task_id)

    if not task or task.user_id != current_user.id:
        abort(404)

    db.session.delete(task)

    db.session.commit()

    flash("Task deleted successfully.", "success")

    return redirect(url_for("dashboard"))


# API: GET ALL TASKS
@app.route("/api/tasks", methods=["GET"])
@login_required
def api_tasks():

    tasks = db.session.execute(
        db.select(Task).filter_by(user_id=current_user.id)
    ).scalars().all()

    return jsonify([
        {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "completed": task.completed
        }
        for task in tasks
    ])


# API: CREATE TASK
@app.route("/api/tasks", methods=["POST"])
@login_required
def api_add_task():

    data = request.get_json(silent=True) or {}

    title = data.get("title", "")

    if not isinstance(title, str):
        return jsonify({"error": "Invalid task title"}), 400

    title = title.strip()

    if not title or len(title) > 150:
        return jsonify({"error": "Invalid task title"}), 400

    description = data.get("description", "")

    if not isinstance(description, str):
        return jsonify({"error": "Invalid description"}), 400

    task = Task(
        title=title,
        description=description,
        user_id=current_user.id
    )

    db.session.add(task)

    db.session.commit()

    return jsonify({
        "message": "Task created",
        "id": task.id
    }), 201


# API: UPDATE TASK
@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
@login_required
def api_update_task(task_id):

    task = db.session.get(Task, task_id)

    if not task or task.user_id != current_user.id:
        abort(404)

    data = request.get_json(silent=True) or {}

    if "title" in data:

        title = data["title"]

        if not isinstance(title, str):
            return jsonify({"error": "Invalid title"}), 400

        title = title.strip()

        if not title or len(title) > 150:
            return jsonify({"error": "Invalid title"}), 400

        task.title = title

    if "description" in data:

        if not isinstance(data["description"], str):
            return jsonify({"error": "Invalid description"}), 400

        task.description = data["description"]

    if "completed" in data:

        if not isinstance(data["completed"], bool):
            return jsonify({"error": "completed must be boolean"}), 400

        task.completed = data["completed"]

    db.session.commit()

    return jsonify({"message": "Task updated"})


# API: DELETE TASK
@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
@login_required
def api_delete_task(task_id):

    task = db.session.get(Task, task_id)

    if not task or task.user_id != current_user.id:
        abort(404)

    db.session.delete(task)

    db.session.commit()

    return jsonify({"message": "Task deleted"})


# ERROR HANDLING
@app.errorhandler(404)
def not_found(error):

    return "404 - Page or task not found", 404


@app.errorhandler(500)
def server_error(error):

    db.session.rollback()

    return "500 - Internal Server Error", 500


# CREATE DATABASE TABLES
with app.app_context():

    db.create_all()


# RUN APPLICATION
if __name__ == "__main__":

    app.run(debug=True)
