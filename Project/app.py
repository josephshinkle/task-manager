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

def current_user_id():
    return session.get("user_id")

def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not current_user_id():
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapper

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/tasks", methods = ["GET", "POST"])
def tasks():
    conn = get_db_connection()

    filter_val = request.args.get("filter", "all")
    search = request.args.get("search", "").strip()
    sort = request.args.get("sort", "created_desc")
    page = request.args.get("page", 1, type=int)
    per_page = 5
    offset = (page - 1) * per_page


    if request.method == "POST":
        title = request.form.get("title", "").strip()
        notes = request.form.get("notes", "").strip()
        
        if not title:
            flash("Title cannot be empty.", "error")
            conn.close()
            return redirect(url_for("tasks", filter=filter, search=search, sort=sort, page=page))
            
        conn.execute(
            """
            INSERT INTO tasks (title, notes, completed, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (title, notes, 0, datetime.now().strftime("%m-%d-%Y %H:%M"))
        )
        conn.commit()
        conn.close()

        flash("Task added.", "success")
        return redirect(url_for("tasks", filter=filter, search=search, sort=sort, page=1))

    where_clauses = []
    params = []

    if filter_val == "active":
        where_clauses.append("completed = 0")
    elif filter_val == "completed":
        where_clauses.append("completed = 1")

    if search:
        where_clauses.append("(title LIKE ? OR notes LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    
    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)
    
    order_by_map = {
        "created_desc": "id DESC",
        "created_asc": "id ASC",
        "title_asc": "title ASC",
        "title_desc": "title DESC",
    }
    order_by = order_by_map.get(sort, "id DESC")

    total = conn.execute(
        f"SELECT COUNT(*) FROM tasks {where_sql}",
        params
    ).fetchone()[0]

    total_pages = max(1, ceil(total/ per_page))
    if page > total_pages:
        page = total_pages

    tasks = conn.execute(
        f"""
        SELECT * FROM tasks
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
def toggle_task(task_id):
    conn = get_db_connection()

    conn.execute(
        """
        UPDATE tasks
        SET completed = CASE completed
            WHEN 0 THEN 1
            ELSE 0
        END
        WHERE id = ?
        """,
        (task_id,)
    )

    conn.commit()
    conn.close()

    flash("Task updated.", "info")
    return redirect(url_for("tasks"))

@app.route("/tasks/<int:task_id>")
def task_detail(task_id):
    conn = get_db_connection()

    task = conn.execute(
        "SELECT id, title, notes, completed, created_at FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    conn.close()
    if task is None:
        abort(404)
    
    return render_template("task_detail.html", task=task)

@app.route("/tasks/<int:task_id>/edit", methods = ["GET", "POST"])
def edit_task(task_id):
    conn = get_db_connection()

    task = conn.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    if task is None:
        conn.close()
        return "Task not found", 404
    
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        notes = request.form.get("notes", "").strip()

        if title:
            conn.execute(
                "UPDATE tasks SET title = ?, notes = ? WHERE id = ?",
                (title, notes, task_id)
            )
            conn.commit()
        
        conn.close()
        return redirect(url_for("tasks"))
    
    conn.close()
    return render_template("edit_task.html", task=task)

@app.route("/tasks/<int:task_id>/confirm_delete", methods=["GET"])
def confirm_delete(task_id):
    conn = get_db_connection()
    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    if task is None:
        abort(404)
    return render_template("confirm_delete.html", task=task)

@app.route("/tasks/delete/<int:task_id>", methods = ["POST"])
def delete_task(task_id):
    conn = get_db_connection()

    conn.execute(
        "DELETE FROM tasks WHERE id = ?",
        (task_id,)
    )

    conn.commit()
    conn.close()

    flash("Task deleted.", "success")
    return redirect(url_for("tasks"))

if __name__ == "__main__":
    app.run(debug=True)