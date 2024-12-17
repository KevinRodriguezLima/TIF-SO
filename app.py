from flask import Flask, render_template, request, redirect
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import psutil
import random
import time
from threading import Thread
import os

app = Flask(__name__)
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance', 'procesos.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app)

prioridades_procesos = {}

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

with app.app_context():
    db.drop_all()
    db.create_all()

def insertar_procesos_en_bd():
    while True:
        with app.app_context():
            for proc in psutil.process_iter(attrs=["pid", "name"]):
                try:
                    pid = proc.info["pid"]
                    nombre = proc.info["name"]
                    proceso_existente = Proceso.query.filter_by(id=pid).first()
                    if not proceso_existente:
                        prioridad = random.randint(0, 10)
                        cpu_asignado = asignar_cpu(prioridad)
                        hora_inicio = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                        nuevo_proceso = Proceso(
                            id=pid,
                            nombre=nombre,
                            prioridad=prioridad,
                            hora_inicio=hora_inicio,
                            cpu_asignado=cpu_asignado
                        )
                        db.session.add(nuevo_proceso)
                        db.session.commit()

                        socketio.emit('proceso_nuevo', nuevo_proceso.to_dict())
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        time.sleep(5)


thread = Thread(target=insertar_procesos_en_bd)
thread.daemon = True
thread.start()

@app.route('/')
def inicio():
    procesos_nucleo = {1: [], 2: [], 3: [], 4: []}
    procesos_db = Proceso.query.all()
    for proceso in procesos_db:
        proceso_dict = {
            "pid": proceso.id,
            "nombre": proceso.nombre,
            "prioridad": proceso.prioridad
        }
        if proceso.cpu_asignado == 1:
            procesos_nucleo[1].append(proceso_dict)
        elif proceso.cpu_asignado == 2:
            procesos_nucleo[2].append(proceso_dict)
        elif proceso.cpu_asignado == 3:
            procesos_nucleo[3].append(proceso_dict)
        else:
            procesos_nucleo[4].append(proceso_dict)

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
