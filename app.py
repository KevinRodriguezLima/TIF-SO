from flask import Flask, render_template, request, redirect
from flask_socketio import SocketIO
from round_robin import round_robin_bp, init_app
import psutil
import time
from datetime import datetime

app = Flask(__name__)
socketio = SocketIO(app)
init_app(socketio)
app.register_blueprint(round_robin_bp, url_prefix='/round_robin')

prioridades_procesos = {}
procesos_manuales = {}

class Proceso:
    def __init__(self, pid, nombre, hora_inicio, prioridad):
        self.pid = pid
        self.nombre = nombre
        self.hora_inicio = hora_inicio
        self.prioridad = prioridad

    def add(self):
        return {
            "pid": self.pid,
            "nombre": self.nombre,
            "hora_inicio": self.hora_inicio,
            "prioridad": self.prioridad
        }

@app.route('/')
def inicio():
    procesos = []
    for pid, prioridad in prioridades_procesos.items():
        try:
            proc = psutil.Process(pid)
            procesos.append(Proceso(
                pid=proc.pid,
                nombre=proc.name(),
                hora_inicio=time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(proc.create_time())),
                prioridad=prioridad
            ).add())
        except psutil.NoSuchProcess:
            pass

    for pid, info_proceso in procesos_manuales.items():
        procesos.append(info_proceso.add())
        
    return render_template('index.html', procesos=procesos)

@app.route('/crear_proceso', methods=['GET', 'POST'])
def crear_proceso():
    max_pid = max(prioridades_procesos.keys(), default=0)

    if request.method == 'POST':
        nombre = request.form['nombre']
        pid = max_pid + 1
        prioridad = int(request.form['prioridad'])
        
        hora_inicio = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        nuevo_proceso = Proceso(pid, nombre, hora_inicio, prioridad)
        procesos_manuales[pid] = nuevo_proceso
        socketio.emit('proceso_nuevo', [nuevo_proceso.add()])
        return redirect('/')
    return render_template('crear_proceso.html', max_pid=max_pid)

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
                    nuevo_proceso = Proceso(
                        pid=proc.pid,
                        nombre=proc.name(),
                        hora_inicio=time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(proc.create_time())),
                        prioridad=prioridad_random
                    )
                    procesos_nuevos.append(nuevo_proceso.add())
                except psutil.NoSuchProcess:
                    pass

            if procesos_nuevos:
                socketio.emit('proceso_nuevo', procesos_nuevos)

        pids_anteriores = pids_actuales
        time.sleep(1)

@socketio.on('connect')
def manejar_conexion():
    print("¡Cliente conectado!")

if __name__ == '__main__':
    socketio.start_background_task(vigilar_procesos)
    socketio.run(app, host='0.0.0.0', port=5000)
