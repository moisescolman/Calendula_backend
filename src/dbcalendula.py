# src/dbcalendula.py

import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app, g

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Permite sobreescribir por entorno (p. ej. /var/data/calendula.db en Render Disk)
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "db", "calendula.db"))
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def get_db():
    """
    Devuelve una conexión SQLite almacenada en g.
    """
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON;")
    return db

def close_db(e=None):
    """
    Cierra la conexión SQLite (si existe) al terminar la petición.
    """
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()
        g._database = None

def init_db():
    """
    Crea las tablas si no existen.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre           TEXT NOT NULL,
        correo           TEXT NOT NULL UNIQUE,
        contrasena_hash  TEXT NOT NULL,
        fecha_creacion   DATETIME NOT NULL DEFAULT (datetime('now'))
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS turnos (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id   INTEGER NOT NULL,
        nombre       TEXT NOT NULL,
        abre         TEXT NOT NULL,
        tipo         TEXT NOT NULL CHECK(tipo IN ('suma','resta','nada')),
        todoDia      BOOLEAN NOT NULL DEFAULT 0,
        inicio       TEXT,
        fin          TEXT,
        colorF       TEXT,
        colorT       TEXT,
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS turnos_marcados (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id  INTEGER NOT NULL,
        fecha       TEXT NOT NULL,
        turno_id    INTEGER NOT NULL,
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        FOREIGN KEY(turno_id)   REFERENCES turnos(id)   ON DELETE CASCADE,
        UNIQUE(usuario_id, fecha, turno_id)
    );
    """)
    conn.commit()
    conn.close()

# ------- Funciones CRUD para usuarios -------

def create_user(nombre, correo, contrasena):
    """
    Inserta un nuevo usuario y devuelve su id.
    """
    db = get_db()
    hash_pw = generate_password_hash(contrasena)
    cur = db.execute(
        "INSERT INTO usuarios (nombre, correo, contrasena_hash) VALUES (?, ?, ?)",
        (nombre, correo, hash_pw)
    )
    db.commit()
    user_id = cur.lastrowid


    db.execute(
        "INSERT INTO turnos (usuario_id, nombre, abre, tipo, todoDia, inicio, fin, colorF, colorT) "
        "VALUES (?, 'Mañana', 'M', 'suma', 0, '08:00', '15:00', 'rgb(255,123,172)', 'rgb(0,0,0)')",
        (user_id,)
    )
  
    db.execute(
        "INSERT INTO turnos (usuario_id, nombre, abre, tipo, todoDia, inicio, fin, colorF, colorT) "
        "VALUES (?, 'Tarde', 'T', 'suma', 0, '15:00', '22:00', 'rgb(255,128,73)', 'rgb(0,0,0)')",
        (user_id,)
    )

    db.execute(
        "INSERT INTO turnos (usuario_id, nombre, abre, tipo, todoDia, inicio, fin, colorF, colorT) "
        "VALUES (?, 'Noche', 'N', 'suma', 0, '22:00', '08:00', 'rgb(63,169,245)', 'rgb(0,0,0)')",
        (user_id,)
    )

    db.execute(
        "INSERT INTO turnos (usuario_id, nombre, abre, tipo, todoDia, inicio, fin, colorF, colorT) "
        "VALUES (?, 'Descanso', 'D', 'resta', 1, NULL, NULL, 'rgb(122,201,67)', 'rgb(0,0,0)')",
        (user_id,)
    )

    db.execute(
        "INSERT INTO turnos (usuario_id, nombre, abre, tipo, todoDia, inicio, fin, colorF, colorT) "
        "VALUES (?, 'Vacaciones', 'V', 'nada', 1, NULL, NULL, 'rgb(252,203,49)', 'rgb(0,0,0)')",
        (user_id,)
    )
    db.commit()
    return user_id

def get_user_by_email(correo):
    """
    Devuelve fila de usuario por correo (incluye contrasena_hash).
    """
    row = get_db().execute(
        "SELECT id, nombre, correo, contrasena_hash FROM usuarios WHERE correo = ?",
        (correo,)
    ).fetchone()
    return dict(row) if row else None

def get_user_by_id(user_id):
    """
    Devuelve usuario {id, nombre, correo} sin contrasena.
    """
    row = get_db().execute(
        "SELECT id, nombre, correo FROM usuarios WHERE id = ?",
        (user_id,)
    ).fetchone()
    return dict(row) if row else None

def update_user_profile(user_id, nombre, correo):
    """
    Actualiza nombre y correo de usuario (sin alterar contraseña).
    """
    db = get_db()
    db.execute(
        "UPDATE usuarios SET nombre = ?, correo = ? WHERE id = ?",
        (nombre, correo, user_id)
    )
    db.commit()

def update_user_password(user_id, nueva_contrasena):
    """
    Actualiza el hash de la contraseña para user_id.
    """
    db = get_db()
    hash_pw = generate_password_hash(nueva_contrasena)
    db.execute(
        "UPDATE usuarios SET contrasena_hash = ? WHERE id = ?",
        (hash_pw, user_id)
    )
    db.commit()

def delete_user(user_id):
    """
    Elimina el usuario y, por cascada, sus turnos y marcados.
    """
    db = get_db()
    db.execute("DELETE FROM usuarios WHERE id = ?", (user_id,))
    db.commit()

# ------- Funciones CRUD para turnos -------

def list_turns(user_id):
    """
    Devuelve todos los turnos del usuario.
    """
    rows = get_db().execute(
        "SELECT id, nombre, abre, tipo, todoDia, inicio, fin, colorF, colorT "
        "FROM turnos WHERE usuario_id = ?",
        (user_id,)
    ).fetchall()
    return [dict(row) for row in rows]

def create_turn(user_id, nombre, abre, tipo, todoDia, inicio, fin, colorF, colorT):
    """
    Crea un turno nuevo y devuelve el objeto creado.
    """
    db = get_db()
    cur = db.execute(
        "INSERT INTO turnos (usuario_id, nombre, abre, tipo, todoDia, inicio, fin, colorF, colorT) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, nombre, abre, tipo, int(todoDia), inicio, fin, colorF, colorT)
    )
    db.commit()
    new_id = cur.lastrowid
    row = db.execute(
        "SELECT id, nombre, abre, tipo, todoDia, inicio, fin, colorF, colorT FROM turnos WHERE id = ?",
        (new_id,)
    ).fetchone()
    return dict(row)

def update_turn(user_id, turno_id, nombre, abre, tipo, todoDia, inicio, fin, colorF, colorT):
    """
    Actualiza un turno, devuelve True si lo encontró y actualizó.
    """
    db = get_db()
    cur = db.execute(
        "UPDATE turnos SET nombre = ?, abre = ?, tipo = ?, todoDia = ?, inicio = ?, fin = ?, colorF = ?, colorT = ? "
        "WHERE id = ? AND usuario_id = ?",
        (nombre, abre, tipo, int(todoDia), inicio, fin, colorF, colorT, turno_id, user_id)
    )
    db.commit()
    return cur.rowcount > 0

def delete_turn(user_id, turno_id):
    """
    Elimina el turno si pertenece al usuario. Devuelve True si eliminado.
    """
    db = get_db()
    cur = db.execute(
        "DELETE FROM turnos WHERE id = ? AND usuario_id = ?",
        (turno_id, user_id)
    )
    db.commit()
    return cur.rowcount > 0

# ------- Funciones CRUD para turnos_marcados -------

def list_marked_turns(user_id):
    """
    Devuelve todos los turnos marcados del usuario.
    """
    rows = get_db().execute(
        "SELECT id, fecha, turno_id FROM turnos_marcados WHERE usuario_id = ?",
        (user_id,)
    ).fetchall()
    return [dict(row) for row in rows]

def create_marked_turn(user_id, fecha, turno_id):
    """
    Marca un turno en una fecha. Devuelve el registro creado.
    """
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO turnos_marcados (usuario_id, fecha, turno_id) VALUES (?, ?, ?)",
            (user_id, fecha, turno_id)
        )
        db.commit()
        new_id = cur.lastrowid
        row = db.execute(
            "SELECT id, fecha, turno_id FROM turnos_marcados WHERE id = ?",
            (new_id,)
        ).fetchone()
        return dict(row)
    except sqlite3.IntegrityError:
        return None  # Ya existe o llave foránea inválida

def delete_marked_turn(user_id, marcado_id):
    """
    Elimina un turno marcado. Devuelve True si se eliminó.
    """
    db = get_db()
    cur = db.execute(
        "DELETE FROM turnos_marcados WHERE id = ? AND usuario_id = ?",
        (marcado_id, user_id)
    )
    db.commit()
    return cur.rowcount > 0
