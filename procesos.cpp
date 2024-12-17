#include <fstream>
#include <iostream>
#include <cstdlib>

int main() {
    const std::string ruta_archivo = "/var/log/procesos_inicio.txt";
    std::ofstream archivo(ruta_archivo);

    archivo << "Lista de procesos activos al arranque:\n";
    archivo << "======================================\n";

    FILE* pipe = popen("ps aux", "r");

    char buffer[256];
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        archivo << buffer; 
    }

    pclose(pipe);
    archivo.close();

    return 0;
}