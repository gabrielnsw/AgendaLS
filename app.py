# app.py

from blueprints.users_bp import users_bp
from blueprints.agenda.agenda import agenda_bp
from blueprints.filtros import formato_datahora
import os
import json
from flask import Flask, render_template, request, redirect, url_for
from flask_login import LoginManager, current_user, login_user, logout_user, login_required, UserMixin
from flask_socketio import SocketIO, emit
from datetime import datetime
import logging

logging.basicConfig(level=logging.DEBUG)

def load_users():
    fpath = os.path.join("data", "usuarios.json")
    if not os.path.exists(fpath):
        return {}
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_users(users):
    fpath = os.path.join("data", "usuarios.json")
    os.makedirs(os.path.dirname(fpath), exist_ok=True)
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4, ensure_ascii=False)


app = Flask(__name__)
app.secret_key = "supersecretkey"

socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = None


class Usuario(UserMixin):
    def __init__(self, user_id, nome, tipo_usuario):
        self.id = user_id
        self.nome_completo = nome
        self.tipo_usuario = tipo_usuario

    @property
    def role(self):
        if self.tipo_usuario.lower() == "administrador":
            return "admin"
        else:
            return "regular"


@login_manager.user_loader
def load_user_func(user_id):
    users_data = load_users()
    if user_id in users_data:
        user_rec = users_data[user_id]
        return Usuario(user_id, user_rec["nome_completo"], user_rec["tipo_usuario"])
    return None


app.jinja_env.filters["formato_datahora"] = formato_datahora


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("agenda_bp.agenda_main"))
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        users_data = load_users()
        if username in users_data:
            if users_data[username]["password"] == password:
                udata = users_data[username]
                user_obj = Usuario(
                    username, udata["nome_completo"], udata["tipo_usuario"])
                login_user(user_obj)
                return redirect(url_for("agenda_bp.agenda_main"))
        return redirect(url_for("login", msg="Usuário ou senha inválidos", status="danger"))
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login", msg="Logout realizado!", status="success"))


app.register_blueprint(agenda_bp, url_prefix="")

app.register_blueprint(users_bp)


@app.route("/")
def index():
    app.logger.debug("Rota '/' acessada")
    return redirect(url_for("agenda_bp.agenda_main"))


@socketio.on("connect")
def on_connect():
    print("Cliente conectado")


@socketio.on("disconnect")
def on_disconnect():
    print("Cliente desconectado")


if __name__ == "__main__":
    socketio.run(app, debug=False, host="0.0.0.0", port=5005)
