# verProcesos-SO
Implementado una aplicación web para visualizar los procesos creados desde el arranque del computador y tambien ver procesos creados en vivo (LINUX)

serie de comando para que se pueda recuperar los procesos de arranque de la pc/laptop: 

1) sudo nano /usr/local/bin/procesos.sh -> dentro de ese archivo se ejecuta esto : 
#!/bin/bash
/usr/local/bin/procesos

2) hacerlo ejecutable -> sudo chmod +x /usr/local/bin/captura_procesos.sh
3) en la ruta de la carpeta donde esta el archivo cpp que recupera procesos lo compilas y luego con el codigo objeto se ejecuta lo sieguiente -> sudo mv captura_procesos /usr/local/bin/procesos
4) luego esto -> sudo chmod +x /usr/local/bin/procesos
5) luego esto para crear el autoejecutable -> sudo nano /etc/systemd/system/procesos.service
6) dentro del archivo creado va el siguiente codigo :  
    [Unit]
    Description=procesos arranque 
    After=multi-user.target

    [Service]
    ExecStart=/usr/local/bin/procesos.sh
    Type=oneshot

    [Install]
    WantedBy=multi-user.target

7) luego de eso ejecutar esto -> sudo systemctl daemon-reload
8) luego esto -> sudo systemctl enable procesos.service



