#include <fstream>
#include <iostream>
#include <cstdlib>

int main() {
    const std::string ruta_archivo = "/home/kiwi/Documents/garbage/procesos.txt";

    std::ofstream archivo(ruta_archivo);
    if (archivo.is_open()) {
        archivo << "Lista de procesos activos:\n";
        archivo << "==========================\n";

        int resultado = system(("ps aux >> " + ruta_archivo).c_str());
        
        if (resultado == 0) {
            std::cout << "si";
        }

        archivo.close();
    }   

    return 0;
}
