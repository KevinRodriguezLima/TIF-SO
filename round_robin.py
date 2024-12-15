from flask import Blueprint, render_template, request, redirect
from flask_socketio import emit
from datetime import datetime
import threading
import time

round_robin_bp = Blueprint('round_robin', __name__)

cola_global = []
cpus = [[], [], [], []]
procesos_terminados = []
quantum = 2
cpu_activo = False

socketio = None

def init_app(sio):
    global socketio
    socketio = sio

class Proceso:
    def __init__(self, pid, nombre, hora_inicio, tiempo_restante):
        self.pid = pid
        self.nombre = nombre
        self.hora_inicio = hora_inicio
        self.tiempo_restante = tiempo_restante

    def add(self):
        return {
            "pid": self.pid,
            "nombre": self.nombre,
            "hora_inicio": self.hora_inicio,
            "tiempo_restante": self.tiempo_restante
        }

@round_robin_bp.route('/')
def round_robin_page():
    return render_template(
        'round_robin.html',
        quantum=quantum,
        procesos=cola_global,
        cpus=cpus,
        terminados=procesos_terminados,
        cpu_activo=cpu_activo
    )

@round_robin_bp.route('/agregar_proceso', methods=['POST'])
def agregar_proceso():
    nombre = request.form.get('nombre', f"Proceso-{len(cola_global) + 1}")
    tiempo_restante = int(request.form.get('tiempo', 5))
    nuevo_proceso = Proceso(
        pid=len(cola_global) + 1,
        nombre=nombre,
        hora_inicio=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        tiempo_restante=tiempo_restante
    )
    cola_global.append(nuevo_proceso)
    emit_estado_actual()
    return redirect('/round_robin')

@round_robin_bp.route('/actualizar_quantum', methods=['POST'])
def actualizar_quantum():
    global quantum
    quantum = int(request.form['quantum'])
    emit_estado_actual()
    return redirect('/round_robin')

@round_robin_bp.route('/toggle_cpu', methods=['POST'])
def toggle_cpu():
    global cpu_activo
    cpu_activo = not cpu_activo
    if cpu_activo:
        threading.Thread(target=round_robin_worker, daemon=True).start()
    emit_estado_actual()
    return redirect('/round_robin')

def round_robin_worker():
    global cpu_activo
    while cpu_activo:
        for i, cpu in enumerate(cpus):
            if cpu:
                proceso_actual = cpu.pop(0)
                tiempo_a_usar = min(proceso_actual.tiempo_restante, quantum)
                proceso_actual.tiempo_restante -= tiempo_a_usar

                if proceso_actual.tiempo_restante > 0:
                    cpu.append(proceso_actual)
                else:
                    procesos_terminados.append(proceso_actual.add())

        while cola_global and any(len(cpu) < 2 for cpu in cpus):
            distribuir_proceso(cola_global.pop(0))

        emit_estado_actual()
        time.sleep(quantum)

def distribuir_proceso(proceso):
    cpu_menos_cargado = min(cpus, key=len)
    cpu_menos_cargado.append(proceso)

def emit_estado_actual():
    try:
        estado = {
            "cola_global": [p.add() for p in cola_global],
            "cpus": [[p.add() for p in cpu] for cpu in cpus],
            "terminados": procesos_terminados
        }
        socketio.emit('estado_actualizado', estado, broadcast=True)
    except Exception as e:
        print(f"Error emitiendo estado: {e}")
