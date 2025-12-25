# Task Manager

A full-stack task management web application built with Flask.

# Features
- User authentication (register, login, logout)
- Task ownership per user
- Create, edit, delete, and view tasks
- Search, filter, and sort tasks
- Clean, responsive UI

# Tech Stack
- Python
- Flask
- SQLite
- HTML / CSS
- Jinja2 templates

## Screenshots

### Home
![Home](Project/static/images/home.png)

### Login
![Login](Project/static/images/login.png)

### Tasks
![Tasks](Project/static/images/tasks.png)

# Setup

```bash
git clone https://github.com/josephshinkle/task-manager.git
cd task-manager

# Create venv (repo root)
python -m venv .venv

# Activate venv
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Windows (CMD):
.\.venv\Scripts\activate.bat
# Mac/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python Project/app.py
