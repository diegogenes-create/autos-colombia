from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'autos_colombia_secret_key'
DB_NAME = 'parqueadero.db'

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    # Tabla de Usuarios (Iteración 2)
    c.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cedula TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            telefono TEXT NOT NULL,
            placa TEXT UNIQUE NOT NULL,
            estado_mensualidad TEXT DEFAULT 'Activa'
        )
    ''')
    # Tabla de Celdas (Iteración 2)
    c.execute('''
        CREATE TABLE IF NOT EXISTS celdas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            tipo TEXT NOT NULL,
            estado TEXT DEFAULT 'Disponible',
            placa_asignada TEXT DEFAULT NULL
        )
    ''')
    # Tabla de Movimientos Entrada/Salida (Iteración 1)
    c.execute('''
        CREATE TABLE IF NOT EXISTS movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            placa TEXT NOT NULL,
            celda_codigo TEXT NOT NULL,
            hora_entrada TEXT NOT NULL,
            hora_salida TEXT DEFAULT NULL
        )
    ''')
    # Inicializar 10 celdas por defecto si está vacía
    c.execute('SELECT COUNT(*) FROM celdas')
    if c.fetchone()[0] == 0:
        celdas_iniciales = [
            ('A-01', 'Automóvil'), ('A-02', 'Automóvil'), ('A-03', 'Automóvil'),
            ('A-04', 'Automóvil'), ('A-05', 'Automóvil'), ('A-06', 'Automóvil'),
            ('M-01', 'Motocicleta'), ('M-02', 'Motocicleta'),
            ('M-03', 'Motocicleta'), ('M-04', 'Motocicleta')
        ]
        c.executemany('INSERT INTO celdas (codigo, tipo) VALUES (?, ?)', celdas_iniciales)
    conn.commit()
    conn.close()

@app.route('/')
def index():
    conn = get_db()
    usuarios = conn.execute('SELECT * FROM usuarios ORDER BY id DESC').fetchall()
    celdas = conn.execute('SELECT * FROM celdas ORDER BY codigo ASC').fetchall()
    movimientos = conn.execute('SELECT * FROM movimientos ORDER BY id DESC LIMIT 10').fetchall()
    conn.close()
    return render_template('index.html', usuarios=usuarios, celdas=celdas, movimientos=movimientos)

# --- ITERACIÓN 2: GESTIÓN DE USUARIOS ---
@app.route('/usuarios/crear', methods=['POST'])
def crear_usuario():
    cedula = request.form['cedula'].strip()
    nombre = request.form['nombre'].strip()
    telefono = request.form['telefono'].strip()
    placa = request.form['placa'].strip().upper()
    try:
        conn = get_db()
        conn.execute('INSERT INTO usuarios (cedula, nombre, telefono, placa) VALUES (?, ?, ?, ?)',
                     (cedula, nombre, telefono, placa))
        conn.commit()
        flash('Usuario registrado exitosamente.', 'success')
    except sqlite3.IntegrityError:
        flash('Error: La cédula o la placa ya se encuentran registradas.', 'danger')
    finally:
        conn.close()
    return redirect(url_for('index'))

@app.route('/usuarios/editar/<int:id>', methods=['POST'])
def editar_usuario(id):
    nombre = request.form['nombre'].strip()
    telefono = request.form['telefono'].strip()
    estado = request.form['estado_mensualidad']
    conn = get_db()
    conn.execute('UPDATE usuarios SET nombre = ?, telefono = ?, estado_mensualidad = ? WHERE id = ?',
                 (nombre, telefono, estado, id))
    conn.commit()
    conn.close()
    flash('Datos del usuario actualizados.', 'success')
    return redirect(url_for('index'))

@app.route('/usuarios/eliminar/<int:id>')
def eliminar_usuario(id):
    conn = get_db()
    conn.execute('DELETE FROM usuarios WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Usuario eliminado del sistema.', 'warning')
    return redirect(url_for('index'))

# --- ITERACIÓN 2: GESTIÓN DE CELDAS ---
@app.route('/celdas/crear', methods=['POST'])
def crear_celda():
    codigo = request.form['codigo'].strip().upper()
    tipo = request.form['tipo']
    try:
        conn = get_db()
        conn.execute('INSERT INTO celdas (codigo, tipo) VALUES (?, ?)', (codigo, tipo))
        conn.commit()
        flash(f'Celda {codigo} creada correctamente.', 'success')
    except sqlite3.IntegrityError:
        flash(f'Error: La celda {codigo} ya existe.', 'danger')
    finally:
        conn.close()
    return redirect(url_for('index'))

@app.route('/celdas/estado/<int:id>/<nuevo_estado>')
def cambiar_estado_celda(id, nuevo_estado):
    conn = get_db()
    celda = conn.execute('SELECT * FROM celdas WHERE id = ?', (id,)).fetchone()
    if celda and celda['estado'] == 'Ocupada':
        flash('No se puede cambiar el estado de una celda ocupada por un vehículo.', 'danger')
    else:
        conn.execute('UPDATE celdas SET estado = ? WHERE id = ?', (nuevo_estado, id))
        conn.commit()
        flash(f'Estado de celda actualizado a {nuevo_estado}.', 'info')
    conn.close()
    return redirect(url_for('index'))

# --- ITERACIÓN 1: ENTRADA Y SALIDA DE VEHÍCULOS ---
@app.route('/vehiculos/entrada', methods=['POST'])
def registrar_entrada():
    placa = request.form['placa'].strip().upper()
    celda_codigo = request.form['celda_codigo']
    conn = get_db()
    usuario = conn.execute('SELECT * FROM usuarios WHERE placa = ?', (placa,)).fetchone()
    if not usuario:
        flash('Acceso denegado: La placa no está asociada a un usuario con mensualidad.', 'danger')
    elif usuario['estado_mensualidad'] != 'Activa':
        flash('Acceso denegado: La mensualidad del usuario está vencida/inactiva.', 'danger')
    else:
        celda = conn.execute('SELECT * FROM celdas WHERE codigo = ? AND estado = "Disponible"', (celda_codigo,)).fetchone()
        if not celda:
            flash('La celda seleccionada no está disponible.', 'danger')
        else:
            ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn.execute('UPDATE celdas SET estado = "Ocupada", placa_asignada = ? WHERE codigo = ?', (placa, celda_codigo))
            conn.execute('INSERT INTO movimientos (placa, celda_codigo, hora_entrada) VALUES (?, ?, ?)',
                         (placa, celda_codigo, ahora))
            conn.commit()
            flash(f'Entrada registrada: Vehículo {placa} asignado a celda {celda_codigo}.', 'success')
    conn.close()
    return redirect(url_for('index'))

@app.route('/vehiculos/salida/<int:celda_id>')
def registrar_salida(celda_id):
    conn = get_db()
    celda = conn.execute('SELECT * FROM celdas WHERE id = ?', (celda_id,)).fetchone()
    if celda and celda['estado'] == 'Ocupada':
        ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('UPDATE movimientos SET hora_salida = ? WHERE placa = ? AND hora_salida IS NULL',
                     (ahora, celda['placa_asignada']))
        conn.execute('UPDATE celdas SET estado = "Disponible", placa_asignada = NULL WHERE id = ?', (celda_id,))
        conn.commit()
        flash(f'Salida registrada: Celda {celda["codigo"]} liberada.', 'success')
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)