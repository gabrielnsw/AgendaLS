# file: blueprints/users_bp.py
import os
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
from functools import wraps

users_bp = Blueprint("users_bp", __name__, template_folder="users_bp/templates", url_prefix="/admin")

DATA_FILE = os.path.join("data", "usuarios.json")

def load_users():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_users(users):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4, ensure_ascii=False)

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Você precisa estar logado.", "danger")
            return redirect(url_for("login"))
        if getattr(current_user, "role", "regular") != "admin":
            flash("Você não tem permissão de administrador.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated

@users_bp.route("/usuarios", methods=["GET"])
@login_required
@admin_required
def listar_usuarios():
    users = load_users()
    return render_template("listar_usuarios.html", usuarios=users)

@users_bp.route("/usuarios/novo", methods=["GET","POST"])
@login_required
@admin_required
def criar_usuario():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        full_name = request.form.get("full_name")
        tipo_usuario = request.form.get("tipo_usuario", "Regular")

        users = load_users()
        if username in users:
            flash("Usuário já existe!", "danger")
            return redirect(url_for("users_bp.listar_usuarios"))

        users[username] = {
            "password": password,
            "nome_completo": full_name,
            "tipo_usuario": tipo_usuario
        }
        save_users(users)
        flash("Usuário criado com sucesso!", "success")
        return redirect(url_for("users_bp.listar_usuarios"))
    return render_template("criar_usuario.html")

@users_bp.route("/usuarios/remover", methods=["POST"])
@login_required
@admin_required
def remover_usuario():
    uname = request.form.get("username")
    if not uname:
        flash("Nome de usuário não informado.", "danger")
        return redirect(url_for("users_bp.listar_usuarios"))

    users = load_users()
    if uname not in users:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for("users_bp.listar_usuarios"))

    del users[uname]
    save_users(users)
    flash("Usuário removido!", "success")
    return redirect(url_for("users_bp.listar_usuarios"))
