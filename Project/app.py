import sqlite3
from functools import wraps
from db import init_db, get_db_connection, migrate_db
from flask import Flask, render_template, request, redirect, url_for, abort, flash, session
from datetime import datetime
from math import ceil
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.secret_key = "dev-change-this-later"

init_db()
migrate_db()

# Auth Helpers
def current_user_id():
    return session.get("user_id")

def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        uid = session.get("user_id")
        if uid is None:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapper

#Auth Routes

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/tasks", methods = ["GET", "POST"])
@login_required
def tasks():

    uid = session.get("user_id")
    conn = get_db_connection()

    filter_val = request.args.get("filter", "all").strip().lower()
    search = request.args.get("search", "").strip()
    sort = request.args.get("sort", "created_desc")
    page = request.args.get("page", 1, type=int)
    per_page = 5

    if page < 1:
        page = 1

    offset = (page - 1) * per_page


    if request.method == "POST":
        title = request.form.get("title", "").strip()
        notes = request.form.get("notes", "").strip()
        uid = current_user_id()
        
        if not title:
            flash("Title cannot be empty.", "error")
            conn.close()
            return redirect(url_for("tasks", filter=filter, search=search, sort=sort, page=page))
            
        conn.execute(
            """
            INSERT INTO tasks (user_id, title, notes, completed, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (uid, title, notes, 0, datetime.now().strftime("%m-%d-%Y %H:%M"))
        )
        conn.commit()
        conn.close()

        flash("Task added.", "success")
        return redirect(url_for("tasks", filter=filter, search=search, sort=sort, page=1))

    where_clauses = []
    params = []

    where_clauses.append("user_id = ?")
    params.append(uid)

    if filter_val == "active":
        where_clauses.append("completed = 0")
    elif filter_val == "completed":
        where_clauses.append("completed = 1")
    else :
        filter_val = "all"

    if search:
        where_clauses.append("(title LIKE ? OR notes LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    
    where_sql = where_sql = "WHERE " + " AND ".join(where_clauses)
    
    order_by_map = {
        "created_desc": "id DESC",
        "created_asc": "id ASC",
        "title_asc": "title ASC",
        "title_desc": "title DESC",
    }
    order_by = order_by_map.get(sort, "id DESC")

    total = conn.execute(
        f"""SELECT COUNT(*) 
        FROM tasks 
        {where_sql}
        """,
        params,
    ).fetchone()[0]

    total_pages = ceil(total / per_page)

    tasks = conn.execute(
        f"""
        SELECT id, user_id, title, notes, completed, created_at
        FROM tasks
        {where_sql}
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
        """,
        (*params, per_page, offset)
    ).fetchall()

    conn.close
    
    return render_template(
        "tasks.html",
        tasks = tasks,
        filter_val = filter_val,
        search = search,
        sort = sort,
        page = page,
        total_pages = total_pages,
        per_page = per_page,
        total = total,
        )

@app.route("/tasks/toggle/<int:task_id>", methods = ["POST"])
@login_required
def toggle_task(task_id):
    """
    Toggles completed status for one task.
    Ownership enforced: WHERE id = ? AND user_id = ?
    """
    uid = current_user_id()

    conn = get_db_connection()
    conn.execute(
        """
        UPDATE tasks
        SET completed = CASE completed WHEN 0 THEN 1 ELSE 0 END
        WHERE id = ? AND user_id = ?
        """,
        (task_id, uid)
    )
    conn.commit()
    conn.close()

    flash("Task updated.", "info")
    return redirect(url_for(
        "tasks",
        filter=request.args.get("filter", "all"),
        search=request.args.get("search", ""),
        sort=request.args.get("sort", "created_desc"),
        page=request.args.get("page", 1)
        ))

@app.route("/tasks/<int:task_id>")
@login_required
def task_detail(task_id):
    """
    Show one task.
    Ownership must be enforced:
        WHERE id = ? AND user_id = ?
    """

    uid = current_user_id()

    conn = get_db_connection()

    task = conn.execute(
        """
        SELECT id, user_id, title, notes, completed, created_at
        FROM tasks 
        WHERE id = ? AND user_id = ?
        """,
        (task_id, uid)
    ).fetchone()
    conn.close()

    if task is None:
        abort(404)
    
    return render_template("task_detail.html", task=task)

@app.route("/tasks/<int:task_id>/edit", methods = ["GET", "POST"])
@login_required
def edit_task(task_id):
    """
    - GET: show edit form with existing data
    - POST: update title/notes
    Ownership enforced on both SELECT and UPDATE.
    """
    uid = current_user_id()
    conn = get_db_connection()

    task = conn.execute(
        "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
        (task_id, uid)
    ).fetchone()

    if task is None:
        conn.close()
        return "Task not found", 404
    
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        notes = request.form.get("notes", "").strip()

        if not title:
            flash("Title cannot be empty.", "error")
            conn.close()
            return redirect(url_for("edit_task", task_id=task_id))
        
            conn.execute(
                """
                UPDATE tasks 
                SET title = ?, notes = ? 
                WHERE id = ?", AND user_id = ?
                """,
                (title, notes, task_id, uid)
            )
            conn.commit()
            conn.close()
            
            flash("Task saved.", "success")
            return redirect(url_for("task_detail", task_id=task_id))
    
    conn.close()
    return render_template("edit_task.html", task=task)

@app.route("/tasks/<int:task_id>/confirm_delete", methods=["GET"])
@login_required
def confirm_delete(task_id):
    """
    Displays a confirmation page before deleting.
    This is GET-only (safe navigation).
    Ownership enforced on SELECT.
    """
    uid = current_user_id()

    conn = get_db_connection()
    task = conn.execute(
        "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
        (task_id, uid)
    ).fetchone()
    conn.close()

    if task is None:
        abort(404)

    return render_template("confirm_delete.html", task=task)

@app.route("/tasks/delete/<int:task_id>", methods = ["POST"])
@login_required
def delete_task(task_id):
    """
    Actually deletes the task (POST).
    Ownership enforced: WHERE id = ? AND user_id = ?
    """
    uid = current_user_id()

    conn = get_db_connection()
    conn.execute(
        "DELETE FROM tasks WHERE id = ? AND user_id = ?",
        (task_id, uid)
    )
    conn.commit()
    conn.close()

    flash("Task deleted.", "success")

    return redirect(url_for(
        "tasks",
        filter=request.args.get("filter", "all"),
        search=request.args.get("search", ""),
        sort=request.args.get("sort", "created_desc"),
        page=request.args.get("page", 1)
        ))
    
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Email and password are required.", "error")
            return redirect(url_for("register"))
        
        pw_hash = generate_password_hash(password)

        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
                (email, pw_hash, datetime.now().strftime("%m-%d-%Y %H:%M"))
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            flash("That email is already registered.", "error")
            return redirect(url_for("register"))
        
        conn.close()
        flash("Account created. Please log in.", "success")
        return redirect(url_for("login"))
    
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "error")
            return redirect(url_for("login"))
        
        session["user_id"] = user["id"]
        flash("Logged in.", "success")
        return redirect(url_for("tasks"))
    
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    flash("Logged out.", "info")
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)