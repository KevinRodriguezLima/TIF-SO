from flask import Flask, render_template, request, redirect
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import scoped_session, sessionmaker
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

SessionFactory = None

def init_db():
    global SessionFactory
    with app.app_context():
        db.drop_all()
        db.create_all()
        SessionFactory = sessionmaker(bind=db.engine)

init_db()

cpu_activo = False
quantum_por_nucleo = {1: 1, 2: 1, 3: 1, 4: 1}
quantum_unidad_real = 0.5
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

def insertar_procesos_en_bd():
    while True:
        session = SessionFactory()
        try:
            for proc in psutil.process_iter(attrs=["pid", "name"]):
                try:
                    pid = proc.info["pid"]
                    nombre = proc.info["name"]
                    proceso_existente = session.query(Proceso).filter_by(id=pid).first()
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
                            tiempo_restante=tiempo_restante,
                            cpu_asignado=cpu_asignado
                        )
                        session.add(nuevo_proceso)
                        session.commit()
                        subcolas[cpu_asignado].append(nuevo_proceso)
                        socketio.emit('proceso_nuevo', nuevo_proceso.to_dict())
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        finally:
            session.close()
        time.sleep(5)

def ordenar_fcfs(subcola):
    subcola.sort(key=lambda p: datetime.strptime(p.hora_inicio, '%Y-%m-%d %H:%M:%S'))

def ordenar_sjf(subcola):
    subcola.sort(key=lambda p: p.tiempo_restante)

def worker_general(cpu_id):
    while True:
        if cpu_activo and subcolas[cpu_id]:
            session = SessionFactory()
            try:
                with lock:
                    # Reasignar el proceso dentro de una sesión activa
                    proceso = subcolas[cpu_id][0]
                    proceso_db = session.query(Proceso).filter_by(id=proceso.id).first()

                    if not proceso_db:
                        # Si el proceso no existe en la base de datos, eliminarlo de la subcola
                        subcolas[cpu_id].pop(0)
                        continue

                    if algoritmos[cpu_id] == "RR":
                        # Round Robin
                        quantum_lógico = min(quantum_por_nucleo[cpu_id], proceso_db.tiempo_restante)
                        socketio.emit('proceso_ejecutandose', {
                            'cpu_id': cpu_id,
                            'proceso_id': proceso_db.id
                        })

                        for _ in range(quantum_lógico):
                            if proceso_db.tiempo_restante > 0:
                                proceso_db.tiempo_restante -= 1
                                session.commit()
                                socketio.emit('actualizar_tiempo', {
                                    'cpu_id': cpu_id,
                                    'proceso_id': proceso_db.id,
                                    'tiempo_restante': proceso_db.tiempo_restante
                                })
                                time.sleep(quantum_unidad_real)

                        if proceso_db.tiempo_restante > 0:
                            subcolas[cpu_id].append(subcolas[cpu_id].pop(0))
                        else:
                            procesos_terminados.append(proceso_db.to_dict())
                            session.delete(proceso_db)
                            session.commit()
                            subcolas[cpu_id].pop(0)

                    elif algoritmos[cpu_id] == "SJF":
                        # Shortest Job First
                        ordenar_sjf(subcolas[cpu_id])
                        socketio.emit('proceso_ejecutandose', {
                            'cpu_id': cpu_id,
                            'proceso_id': proceso_db.id
                        })

                        while proceso_db.tiempo_restante > 0:
                            proceso_db.tiempo_restante -= 1
                            session.commit()
                            socketio.emit('actualizar_tiempo', {
                                'cpu_id': cpu_id,
                                'proceso_id': proceso_db.id,
                                'tiempo_restante': proceso_db.tiempo_restante
                            })
                            time.sleep(quantum_unidad_real)

                        procesos_terminados.append(proceso_db.to_dict())
                        session.delete(proceso_db)
                        session.commit()
                        subcolas[cpu_id].pop(0)

                    elif algoritmos[cpu_id] == "FCFS":
                        # First Come First Serve
                        ordenar_fcfs(subcolas[cpu_id])
                        socketio.emit('proceso_ejecutandose', {
                            'cpu_id': cpu_id,
                            'proceso_id': proceso_db.id
                        })

                        while proceso_db.tiempo_restante > 0:
                            proceso_db.tiempo_restante -= 1
                            session.commit()
                            socketio.emit('actualizar_tiempo', {
                                'cpu_id': cpu_id,
                                'proceso_id': proceso_db.id,
                                'tiempo_restante': proceso_db.tiempo_restante
                            })
                            time.sleep(quantum_unidad_real)

                        procesos_terminados.append(proceso_db.to_dict())
                        session.delete(proceso_db)
                        session.commit()
                        subcolas[cpu_id].pop(0)

                    # Emitir el estado actualizado de la subcola
                    socketio.emit('estado_actualizado', {
                        'cpu_id': cpu_id,
                        'subcola': [p.to_dict() for p in subcolas[cpu_id]]
                    })

            except Exception as e:
                print(f"Error en worker_general para CPU {cpu_id}: {e}", flush=True)
            finally:
                session.close()
        time.sleep(0.1)

def asignar_cpu(prioridad):
    if prioridad >= 8:
        return 1
    elif 5 < prioridad < 8:
        return 2
    elif 2 < prioridad <= 5:
        return 3
    else:
        return 4

def iniciar_workers():
    for cpu_id in range(1, 5):
        t = Thread(target=worker_general, args=(cpu_id,), daemon=True)
        t.start()

@app.route('/')
def inicio():
    procesos_nucleo = {1: [], 2: [], 3: [], 4: []}
    session = SessionFactory()
    try:
        for proceso in session.query(Proceso).all():
            procesos_nucleo[proceso.cpu_asignado].append(proceso.to_dict())
    finally:
        session.close()
    return render_template('index.html', procesos_nucleo=procesos_nucleo, procesos_terminados=procesos_terminados)

@app.route('/toggle_cpu', methods=['POST'])
def toggle_cpu():
    global cpu_activo
    cpu_activo = not cpu_activo

    if cpu_activo:
        # Sincronizar subcolas antes de iniciar la ejecución
        with lock:
            session = SessionFactory()
            try:
                for cpu_id in range(1, 5):
                    # Cargar procesos desde la base de datos
                    subcolas[cpu_id] = session.query(Proceso).filter_by(cpu_asignado=cpu_id).all()

                    # Ordenar según el algoritmo actual
                    if algoritmos[cpu_id] == "SJF":
                        ordenar_sjf(subcolas[cpu_id])
                    elif algoritmos[cpu_id] == "FCFS":
                        ordenar_fcfs(subcolas[cpu_id])

                    # Emitir el estado actualizado
                    socketio.emit('estado_actualizado', {
                        'cpu_id': cpu_id,
                        'subcola': [p.to_dict() for p in subcolas[cpu_id]]
                    })
            finally:
                session.close()

    # Emitir el estado de la CPU
    socketio.emit('cpu_estado', {'activo': cpu_activo})
    return '', 200

@app.route('/crear_proceso', methods=['GET', 'POST'])
def crear_proceso():
    if request.method == 'POST':
        nombre = request.form['nombre']
        prioridad = int(request.form['prioridad'])
        hora_inicio = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cpu_asignado = asignar_cpu(prioridad)

        nuevo_proceso = Proceso(
            nombre=nombre,
            prioridad=prioridad,
            hora_inicio=hora_inicio,
            tiempo_restante=random.randint(5, 15),
            cpu_asignado=cpu_asignado
        )
        session = SessionFactory()
        try:
            session.add(nuevo_proceso)
            session.commit()
        finally:
            session.close()

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

    # Emitir información del algoritmo cambiado al frontend
    socketio.emit('algoritmo_cambiado', {'cpu_id': cpu_id, 'algoritmo': nuevo_algoritmo})

    # Sincronizar subcola con la base de datos y organizarla
    with lock:
        session = SessionFactory()
        try:
            # Cargar procesos asignados a este núcleo desde la base de datos
            subcolas[cpu_id] = session.query(Proceso).filter_by(cpu_asignado=cpu_id).all()

            # Ordenar según el algoritmo seleccionado
            if nuevo_algoritmo == "SJF":
                ordenar_sjf(subcolas[cpu_id])
            elif nuevo_algoritmo == "FCFS":
                ordenar_fcfs(subcolas[cpu_id])

            # Emitir la subcola actualizada al frontend
            socketio.emit('estado_actualizado', {
                'cpu_id': cpu_id,
                'subcola': [p.to_dict() for p in subcolas[cpu_id]]
            })
        finally:
            session.close()

    return '', 200

@app.route('/cambiar_quantum', methods=['POST'])
def cambiar_quantum():
    global quantum_unidad_real
    cpu_id = int(request.form['cpu_id'])
    nuevo_quantum = int(request.form['quantum'])
    nueva_duracion_real = float(request.form['duracion_real'])

    quantum_por_nucleo[cpu_id] = nuevo_quantum
    quantum_unidad_real = nueva_duracion_real
    return '', 200

@app.route('/nucleo/<int:cpu_id>')
def ver_nucleo(cpu_id):
    session = SessionFactory()
    try:
        procesos = session.query(Proceso).filter_by(cpu_asignado=cpu_id).all()
    finally:
        session.close()
    return render_template('nucleo.html', cpu_id=cpu_id, procesos=procesos)

if __name__ == '__main__':
    thread = Thread(target=insertar_procesos_en_bd, daemon=True)
    thread.start()
    iniciar_workers()
    socketio.run(app, host='0.0.0.0', port=5000)
