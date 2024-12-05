from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import psutil
import time
import random

app = Flask(__name__)
socketio = SocketIO(app)

prioridades_procesos = {}

@app.route('/')
def inicio():
    return render_template('index.html')

def vigilar_procesos():
    pids_anteriores = set(proc.pid for proc in psutil.process_iter())
    while True:
        pids_actuales = set(proc.pid for proc in psutil.process_iter())
        nuevos_pids = pids_actuales - pids_anteriores

        if nuevos_pids:
            procesos_nuevos = []
            for pid in nuevos_pids:
                try:
                    proc = psutil.Process(pid)
                    prioridad_random = random.randint(0, 10)
                    prioridades_procesos[pid] = prioridad_random
                    info_proceso = {
                        "pid": proc.pid,
                        "nombre": proc.name(),
                        "hora_inicio": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(proc.create_time())),
                        "prioridad": prioridad_random
                    }
                    procesos_nuevos.append(info_proceso)
                except psutil.NoSuchProcess:
                    pass

            if procesos_nuevos:
                socketio.emit('proceso_nuevo', procesos_nuevos)

        pids_anteriores = pids_actuales
        time.sleep(1)

@socketio.on('cambiar_prioridad')
def manejar_cambio_prioridad(datos):
    """Maneja cuando alguien quiere cambiar la prioridad de un proceso."""
    pid = datos['pid']
    nueva_prioridad = datos['prioridad']
    
    if pid in prioridades_procesos:
        prioridades_procesos[pid] = nueva_prioridad
        socketio.emit('prioridad_cambiada', {'pid': pid, 'nueva_prioridad': nueva_prioridad})

@socketio.on('connect')
def manejar_conexion():
    print("¡Cliente conectado!")

if __name__ == '__main__':
    socketio.start_background_task(vigilar_procesos)
    socketio.run(app, host='0.0.0.0', port=5000)

