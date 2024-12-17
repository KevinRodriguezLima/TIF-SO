from flask import Flask, render_template, request, redirect
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import psutil
import random
import time
from threading import Thread, Lock
import os

app = Flask(__name__)
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance', 'procesos.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app)

cpu_activo = False
quantum = 2
algoritmos = {1: "RR", 2: "RR", 3: "RR", 4: "RR"}
subcolas = {1: [], 2: [], 3: [], 4: []}
procesos_terminados = []
lock = Lock()


class Proceso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    prioridad = db.Column(db.Integer, nullable=False)
    hora_inicio = db.Column(db.String(50), nullable=False)
    tiempo_restante = db.Column(db.Integer, nullable=False)
    cpu_asignado = db.Column(db.Integer, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'prioridad': self.prioridad,
            'hora_inicio': self.hora_inicio,
            'tiempo_restante': self.tiempo_restante,
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
                        tiempo_restante = random.randint(5, 15)
                        cpu_asignado = asignar_cpu(prioridad)
                        hora_inicio = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                        nuevo_proceso = Proceso(
                            id=pid,
                            nombre=nombre,
                            prioridad=prioridad,
                            hora_inicio=hora_inicio,
                            tiempo_restante=random.randint(5, 15),
                            cpu_asignado=cpu_asignado
                        )

                        db.session.add(nuevo_proceso)
                        db.session.commit()

                        subcolas[cpu_asignado].append(nuevo_proceso)
                        socketio.emit('proceso_nuevo', nuevo_proceso.to_dict())
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        time.sleep(5)

def worker_rr(cpu_id):
    """Worker para Round Robin"""
    while True:
        if cpu_activo and subcolas[cpu_id]:
            with lock:
                proceso = subcolas[cpu_id].pop(0)
                tiempo_a_usar = min(proceso.tiempo_restante, quantum)
                proceso.tiempo_restante -= tiempo_a_usar

                if proceso.tiempo_restante > 0:
                    subcolas[cpu_id].append(proceso)
                else:
                    procesos_terminados.append(proceso.to_dict())
                    db.session.delete(proceso)
                    db.session.commit()

            socketio.emit('estado_actualizado', {'cpu_id': cpu_id, 'subcola': [p.to_dict() for p in subcolas[cpu_id]]})
        time.sleep(quantum)

def iniciar_workers():
    """Inicia los workers de Round Robin"""
    for cpu_id in range(1, 5):
        t = Thread(target=worker_rr, args=(cpu_id,), daemon=True)
        t.start()

thread = Thread(target=insertar_procesos_en_bd)
thread.daemon = True
thread.start()

@app.route('/')
def inicio():
    procesos_nucleo = {1: [], 2: [], 3: [], 4: []}
    procesos_db = Proceso.query.all()
    for proceso in procesos_db:
        procesos_nucleo[proceso.cpu_asignado].append(proceso.to_dict())

    return render_template('index.html', procesos_nucleo=procesos_nucleo, procesos_terminados=procesos_terminados)

@app.route('/toggle_cpu', methods=['POST'])
def toggle_cpu():
    global cpu_activo
    cpu_activo = not cpu_activo
    socketio.emit('cpu_estado', {'activo': cpu_activo})
    return '', 200

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

@app.route('/descargar_finalizados', methods=['POST'])
def descargar_finalizados():
    global procesos_terminados
    procesos_terminados = []
    socketio.emit('procesos_limpiados')
    return redirect('/')

@app.route('/cambiar_algoritmo', methods=['POST'])
def cambiar_algoritmo():
    cpu_id = int(request.form['cpu_id'])
    nuevo_algoritmo = request.form['algoritmo']
    algoritmos[cpu_id] = nuevo_algoritmo
    socketio.emit('algoritmo_cambiado', {'cpu_id': cpu_id, 'algoritmo': nuevo_algoritmo})
    return redirect('/')

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
    iniciar_workers()
    socketio.run(app, host='0.0.0.0', port=5000)
