from flask import Flask, render_template, request, redirect
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import psutil
import random

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///procesos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
socketio = SocketIO(app)

# Diccionario global para almacenar las prioridades de los procesos del sistema
prioridades_procesos = {}

# Tabla de la base de datos
class Proceso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    prioridad = db.Column(db.Integer, nullable=False)
    hora_inicio = db.Column(db.String(50), nullable=False)
    activo = db.Column(db.Boolean, default=True)
    cpu_asignado = db.Column(db.Integer, nullable=True)  # CPU 1, 2, 3, o 4

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'prioridad': self.prioridad,
            'hora_inicio': self.hora_inicio,
            'activo': self.activo,
            'cpu_asignado': self.cpu_asignado
        }

# Crear la base de datos
with app.app_context():
    db.create_all()

@app.route('/')
def inicio():
    procesos_nucleo = {1: [], 2: [], 3: [], 4: []}  # Procesos organizados por núcleo

    # Obtener todos los procesos del sistema usando psutil
    for proc in psutil.process_iter(attrs=["pid", "name"]):
        try:
            pid = proc.info["pid"]
            nombre = proc.info["name"]

            # Asignar una prioridad aleatoria si el proceso no está en prioridades_procesos
            if pid not in prioridades_procesos:
                prioridades_procesos[pid] = random.randint(0, 10)

            prioridad = prioridades_procesos[pid]

            proceso = {
                "pid": pid,
                "nombre": nombre,
                "prioridad": prioridad
            }

            # Clasificar los procesos en los núcleos según su prioridad
            if prioridad >= 8:
                procesos_nucleo[1].append(proceso)
            elif 5 < prioridad < 8:
                procesos_nucleo[2].append(proceso)
            elif 2 < prioridad <= 5:
                procesos_nucleo[3].append(proceso)
            else:
                procesos_nucleo[4].append(proceso)

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return render_template('index.html', procesos_nucleo=procesos_nucleo)

@app.route('/crear_proceso', methods=['GET', 'POST'])
def crear_proceso():
    """Formulario para agregar procesos manualmente."""
    if request.method == 'POST':
        nombre = request.form['nombre']
        prioridad = int(request.form['prioridad'])
        hora_inicio = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cpu_asignado = asignar_cpu(prioridad)

        nuevo_proceso = Proceso(
            nombre=nombre,
            prioridad=prioridad,
            hora_inicio=hora_inicio,
            cpu_asignado=cpu_asignado
        )
        db.session.add(nuevo_proceso)
        db.session.commit()

        socketio.emit('proceso_nuevo', nuevo_proceso.to_dict())
        return redirect('/')
    return render_template('crear_proceso.html')

def asignar_cpu(prioridad):
    """Asigna un núcleo CPU según la prioridad."""
    if prioridad >= 8:
        return 1
    elif 5 < prioridad < 8:
        return 2
    elif 2 < prioridad <= 5:
        return 3
    else:
        return 4

@app.route('/nucleo/<int:cpu_id>')
def ver_nucleo(cpu_id):
    """Muestra los detalles de los procesos asignados a un núcleo específico."""
    procesos = Proceso.query.filter_by(cpu_asignado=cpu_id).all()
    return render_template('nucleo.html', cpu_id=cpu_id, procesos=procesos)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
