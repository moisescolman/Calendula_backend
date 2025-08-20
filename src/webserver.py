from flask import Flask, request, jsonify, session, g
from flask_cors import CORS 
from werkzeug.security import check_password_hash
from datetime import datetime
import os
from src.dbcalendula import (
    
    get_db, close_db, init_db,
    create_user, get_user_by_email, get_user_by_id, update_user_profile,
    update_user_password, delete_user,
    list_turns, create_turn, update_turn, delete_turn,
    list_marked_turns, create_marked_turn, delete_marked_turn
)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))


print("Secret key en uso:", app.secret_key)

# Habilita CORS para todas las rutas /api/*
CORS(app, resources={r"/api/*": {"origins": "http://127.0.0.1:5500"}}, supports_credentials=True)

app.teardown_appcontext(close_db)

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "No autenticado"}), 401
        return f(*args, **kwargs)
    return decorated

# ----------------------------
# RUTAS DE AUTENTICACIÓN/USUARIOS
# ----------------------------

@app.route("/api/usuarios", methods=["POST"])
def api_registrar_usuario():
    datos = request.get_json()
    if not datos:
        return jsonify({"error": "JSON inválido"}), 400

    nombre = datos.get("nombre", "").strip()
    correo = datos.get("correo", "").strip().lower()
    contrasena = datos.get("contrasena", "")

    if not nombre or not correo or not contrasena:
        return jsonify({"error": "Todos los campos son obligatorios."}), 400

    # Validación básica de formato de correo
    if "@" not in correo or "." not in correo:
        return jsonify({"error": "Formato de correo inválido."}), 400

    if get_user_by_email(correo):
        return jsonify({"error": "Ya existe un usuario con ese correo."}), 400

    user_id = create_user(nombre, correo, contrasena)
    return jsonify({"mensaje": "Usuario registrado exitosamente", "user_id": user_id}), 201

@app.route("/api/login", methods=["POST"])
def api_login():
    datos = request.get_json()
    if not datos:
        return jsonify({"error": "JSON inválido"}), 400

    correo = datos.get("correo", "").strip().lower()
    contrasena = datos.get("contrasena", "")

    if not correo or not contrasena:
        return jsonify({"error": "Campos requeridos"}), 400

    usuario = get_user_by_email(correo)
    if not usuario or not check_password_hash(usuario["contrasena_hash"], contrasena):
        return jsonify({"error": "Credenciales incorrectas"}), 401

    session["user_id"] = usuario["id"]
    return jsonify({
        "id": usuario["id"],
        "nombre": usuario["nombre"],
        "correo": usuario["correo"]
    }), 200

@app.route("/api/logout", methods=["POST"])
@login_required
def api_logout():
    session.pop("user_id", None)
    return jsonify({"mensaje": "Sesión cerrada"}), 200

@app.route("/api/usuarios/me", methods=["GET"])
@login_required
def api_obtener_perfil():
    user_id = session["user_id"]
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404
    return jsonify(user), 200

@app.route("/api/usuarios/me", methods=["PUT"])
@login_required
def api_editar_perfil():
    datos = request.get_json()
    if not datos:
        return jsonify({"error": "JSON inválido"}), 400

    nuevo_nombre = datos.get("nombre", "").strip()
    nuevo_correo = datos.get("correo", "").strip().lower()
    if not nuevo_nombre or not nuevo_correo:
        return jsonify({"error": "Campos requeridos"}), 400

    user_id = session["user_id"]
    # Verificar duplicado de correo
    existente = get_user_by_email(nuevo_correo)
    if existente and existente["id"] != user_id:
        return jsonify({"error": "El correo ya está en uso"}), 400

    update_user_profile(user_id, nuevo_nombre, nuevo_correo)
    return jsonify({"mensaje": "Perfil actualizado"}), 200

@app.route("/api/usuarios/me/contrasena", methods=["PUT"])
@login_required
def api_cambiar_contrasena():
    datos = request.get_json()
    if not datos:
        return jsonify({"error": "JSON inválido"}), 400

    actual = datos.get("actual", "")
    nueva = datos.get("nueva", "")
    if not actual or not nueva:
        return jsonify({"error": "Campos requeridos"}), 400

    user_id = session["user_id"]
    usuario = get_user_by_id(user_id)
    # Recuperar hash directamente de la tabla para comparar
    row = get_db().execute("SELECT contrasena_hash FROM usuarios WHERE id = ?", (user_id,)).fetchone()
    if not row or not check_password_hash(row["contrasena_hash"], actual):
        return jsonify({"error": "Contraseña actual incorrecta"}), 400

    update_user_password(user_id, nueva)
    return jsonify({"mensaje": "Contraseña actualizada"}), 200

@app.route("/api/usuarios/me", methods=["DELETE"])
@login_required
def api_eliminar_cuenta():
    user_id = session["user_id"]
    delete_user(user_id)
    session.pop("user_id", None)
    return jsonify({"mensaje": "Cuenta eliminada"}), 200

# ----------------------------
# RUTAS DE TURNOS
# ----------------------------

@app.route("/api/turnos", methods=["GET"])
@login_required
def api_listar_turnos():
    user_id = session["user_id"]
    turnos = list_turns(user_id)
    return jsonify(turnos), 200

@app.route("/api/turnos", methods=["POST"])
@login_required
def api_crear_turno():
    datos = request.get_json()
    if not datos:
        return jsonify({"error": "JSON inválido"}), 400

    nombre   = datos.get("nombre", "").strip()
    abre     = datos.get("abre", "").strip()
    tipo     = datos.get("tipo", "").strip()
    todoDia  = bool(datos.get("todoDia", False))
    inicio   = datos.get("inicio")
    fin      = datos.get("fin")
    colorF   = datos.get("colorF", "").strip()
    colorT   = datos.get("colorT", "").strip()

    if not nombre or not abre or tipo not in ("suma", "resta", "nada"):
        return jsonify({"error": "Datos de turno inválidos"}), 400

    user_id = session["user_id"]
    nuevo_turno = create_turn(user_id, nombre, abre, tipo, todoDia, inicio, fin, colorF, colorT)
    return jsonify(nuevo_turno), 201

@app.route("/api/turnos/<int:turno_id>", methods=["PUT"])
@login_required
def api_modificar_turno(turno_id):
    datos = request.get_json()
    if not datos:
        return jsonify({"error": "JSON inválido"}), 400

    nombre   = datos.get("nombre", "").strip()
    abre     = datos.get("abre", "").strip()
    tipo     = datos.get("tipo", "").strip()
    todoDia  = bool(datos.get("todoDia", False))
    inicio   = datos.get("inicio")
    fin      = datos.get("fin")
    colorF   = datos.get("colorF", "").strip()
    colorT   = datos.get("colorT", "").strip()

    if not nombre or not abre or tipo not in ("suma", "resta", "nada"):
        return jsonify({"error": "Datos de turno inválidos"}), 400

    user_id = session["user_id"]
    success = update_turn(user_id, turno_id, nombre, abre, tipo, todoDia, inicio, fin, colorF, colorT)
    if not success:
        return jsonify({"error": "Turno no encontrado o sin permiso"}), 404

    actualizado = get_db().execute(
        "SELECT id, nombre, abre, tipo, todoDia, inicio, fin, colorF, colorT FROM turnos WHERE id = ?",
        (turno_id,)
    ).fetchone()
    return jsonify(dict(actualizado)), 200

@app.route("/api/turnos/<int:turno_id>", methods=["DELETE"])
@login_required
def api_eliminar_turno(turno_id):
    user_id = session["user_id"]
    success = delete_turn(user_id, turno_id)
    if not success:
        return jsonify({"error": "Turno no encontrado o sin permiso"}), 404
    return jsonify({"mensaje": "Turno eliminado"}), 200

# ----------------------------
# RUTAS DE TURNOS MARCADOS
# ----------------------------

@app.route("/api/turnos_marcados", methods=["GET"])
@login_required
def api_listar_turnos_marcados():
    user_id = session["user_id"]
    marcados = list_marked_turns(user_id)
    return jsonify(marcados), 200

@app.route("/api/turnos_marcados", methods=["POST"])
@login_required
def api_crear_turno_marcado():
    datos = request.get_json()
    if not datos:
        return jsonify({"error": "JSON inválido"}), 400

    fecha = datos.get("fecha", "").strip()
    turno_id = datos.get("turno_id")
    if not fecha or not turno_id:
        return jsonify({"error": "Campos requeridos"}), 400

    try:
        datetime.strptime(fecha, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Formato de fecha inválido"}), 400

    user_id = session["user_id"]
    marcado = create_marked_turn(user_id, fecha, turno_id)
    if not marcado:
        return jsonify({"error": "Ese turno ya está marcado o inválido"}), 400
    return jsonify(marcado), 201

@app.route("/api/turnos_marcados/<int:marcado_id>", methods=["DELETE"])
@login_required
def api_eliminar_turno_marcado(marcado_id):
    user_id = session["user_id"]
    success = delete_marked_turn(user_id, marcado_id)
    if not success:
        return jsonify({"error": "Marcado no encontrado o sin permiso"}), 404
    return jsonify({"mensaje": "Turno desmarcado"}), 200
