import os
import sqlite3
import uuid
from dotenv import load_dotenv
from functools import wraps
from .db import init_db, get_db_connection, migrate_db
from flask import Flask, render_template, request, redirect, url_for, abort, flash, session
from datetime import datetime
from math import ceil
from werkzeug.security import generate_password_hash, check_password_hash
from dataclasses import dataclass
from functools import wraps

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-fallback-only")

init_db()
migrate_db()

# Auth Owners
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

# Auth Helpers

@dataclass(frozen=True)
# Reperesents "who owns tasks for this request"
class Owner:
    user_id: int | None
    guest_id: str | None

def get_current_owner() -> Owner:
# Returns the current Owner for this request

    uid = session.get("user_id")

    if uid is not None:
        return Owner(user_id=uid, guest_id=None)
    
    gid = session.get("guest_id")
    
    if gid is None:
        gid = str(uuid.uuid4())
        session["guest_id"] = gid

    return Owner(user_id=None, guest_id=gid)

def require_owner(view_func):
# Decorator that gurantees an Owner exists

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        
        get_current_owner()
        return view_func(*args, **kwargs)
    
    return wrapper

def owner_where_clause(owner: Owner) -> tuple[str, list]:
# Enforces either user_id or guest_id
    
    if owner.user_id is not None:
        return "user_id = ?", [owner.user_id]
    
    return "guest_id = ?", [owner.guest_id]

def claim_guest_tasks_for_user(user_id: int):
    # Allows guest user to claim previous tasks

    gid = session.get("guest_id")

    if gid is None:
        return

    conn = get_db_connection()
    conn.execute(
        """
        UPDATE tasks
        SET user_id = ?, guest_id = NULL
        WHERE guest_id = ?
        """,
        (user_id, gid)
    )
    conn.commit()
    conn.close

    session.pop("guest_id", None)

# Auth Routes

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/tasks", methods = ["GET", "POST"])
@require_owner
def tasks():

    # Post create a task owned by current owner
    # Get list tasks owned by current owner with filter/search/sort/pagination

    conn = get_db_connection()

    filter_val = request.args.get("filter", "all").strip().lower()
    search = request.args.get("search", "").strip()
    sort = request.args.get("sort", "created_desc")
    page = request.args.get("page", 1, type=int)
    per_page = 5

    if page < 1:
        page = 1
    offset = (page - 1) * per_page

    owner = get_current_owner()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        notes = request.form.get("notes", "").strip()
        
        if not title:
            flash("Title cannot be empty.", "error")
            conn.close()
            return redirect(url_for("tasks", filter=filter, search=search, sort=sort, page=page))
        
        if owner.user_id is not None:
            # Logged-in insert uses user_id
            conn.execute(
            """
            INSERT INTO tasks (user_id, guest_id, title, notes, completed, created_at)
            VALUES (?, NULL, ?, ?, 0, ?)
            """,
            (owner.user_id, title, notes, 0, datetime.now().strftime("%m-%d-%Y %H:%M"))
        )
        else:
            # Guest insert uses guest_id
            conn.execute(
            """
            INSERT INTO tasks (user_id, guest_id, title, notes, completed, created_at)
            VALUES (NULL, ?, ?, ?,  0, ?)
            """,
            (owner.guest_id, title, notes, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
        conn.commit()
        conn.close()

        flash("Task added.", "success")
        return redirect(url_for("tasks", filter=filter, search=search, sort=sort, page=1))

    where_parts = []
    params = []

    owner_sql, owner_params = owner_where_clause(owner)
    where_parts.append(owner_sql)
    params.extend(owner_params)

    if filter_val == "active":
        where_parts.append("completed = 0")
    elif filter_val == "completed":
        where_parts.append("completed = 1")
    else :
        filter_val = "all"

    if search:
        where_parts.append("(title LIKE ? OR notes LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    
    where_sql = "WHERE " + " AND ".join(where_parts)
    
    order_by_map = {
        "created_desc": "id DESC",
        "created_asc": "id ASC",
        "title_asc": "title ASC",
        "title_desc": "title DESC",
    }
    order_by = order_by_map.get(sort, "id DESC")

    conn = get_db_connection()

    total = conn.execute(
        f"""
        SELECT COUNT(*) 
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
        is_logged_in=(owner.user_id is not None),
        )

@app.route("/tasks/toggle/<int:task_id>", methods = ["POST"])
@require_owner
def toggle_task(task_id):
    """
    Toggles completed status for a task owned by current owner
    """
    owner = get_current_owner()
    owner_sql, owner_params = owner_where_clause(owner)

    conn = get_db_connection()
    conn.execute(
        f"""
        UPDATE tasks
        SET completed = CASE completed WHEN 0 THEN 1 ELSE 0 END
        WHERE id = ? AND {owner_sql}
        """,
        [task_id] + owner_params
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
@require_owner
def task_detail(task_id):
    """
    Show a single task owned by the current owner (user or guest)
    """

    owner = get_current_owner()
    owner_sql, owner_params = owner_where_clause(owner)

    conn = get_db_connection()

    task = conn.execute(
        f"SELECT *  FROM tasks WHERE id = ? AND {owner_sql}",
        [task_id] + owner_params
    ).fetchone()
    conn.close()

    if task is None:
        abort(404)
    
    return render_template("task_detail.html", task=task)

@app.route("/tasks/<int:task_id>/edit", methods = ["GET", "POST"])
@require_owner
def edit_task(task_id): 
    """
    Edit a task owned by current owner
    """
    owner = get_current_owner()
    owner_sql, owner_params = owner_where_clause(owner)
    
    conn = get_db_connection()

    task = conn.execute(
        f"SELECT * FROM tasks WHERE id = ? AND {owner_sql}",
        [task_id] + owner_params
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
            f"""
            UPDATE tasks 
            SET title = ?, notes = ? 
            WHERE id = ? AND {owner_sql}
            """,
            [title, notes, task_id] + owner_params
        )
        conn.commit()
        conn.close()
            
        flash("Task saved.", "success")
        return redirect(url_for("task_detail", task_id=task_id))
    
    conn.close()
    return render_template("edit_task.html", task=task)

@app.route("/tasks/<int:task_id>/confirm_delete", methods=["GET"])
@require_owner
def confirm_delete(task_id):
    """
    Shows confirmation page for deleting a task (owned by current owner)
    """
    owner = get_current_owner()
    owner_sql, owner_params = owner_where_clause(owner)

    conn = get_db_connection()
    task = conn.execute(
        f"SELECT * FROM tasks WHERE id = ? AND {owner_sql}",
        [task_id] + owner_params
    ).fetchone()
    conn.close()

    if task is None:
        abort(404)

    return render_template("confirm_delete.html", task=task)

@app.route("/tasks/delete/<int:task_id>", methods = ["POST"])
@require_owner
def delete_task(task_id):
    """
    Delete a task owned by current owner
    """
    owner = get_current_owner()
    owner_sql, owner_params = owner_where_clause(owner)

    conn = get_db_connection()
    conn.execute(
        f"DELETE FROM tasks WHERE id = ? AND {owner_sql}",
        [task_id] + owner_params
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
        claim_guest_tasks_for_user(user["id"])
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