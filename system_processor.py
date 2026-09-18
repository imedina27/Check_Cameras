import subprocess
import platform
import socket
import psutil
import config
import time
import os
import re

from file_processor import log_processor


def get_os():                   #---------- PROBADO ----------#
    """Devuelve el sistema operativo actual: 'windows', 'linux', 'darwin', etc."""
    return platform.system().lower()


def ping(host, plant=None, server=None):  #---------- PROBADO ----------#
    # Validación inicial
    if not host or host == '':
        return 814

    # Configuración desde variables de entorno
    max_attempts = config.MAX_PING_ATTEMPTS
    timeout = config.PING_TIMEOUT
    delay_between_attempts = config.RETRY_DELAY

    # Configuración según sistema operativo
    is_windows = get_os() == "windows"
    comando_ping = ['ping', '-n' if is_windows else '-c', '1', host]
    
    # Patrones de detección (unificados para ambos SO)
    patron_exito = r'(\d+ bytes from|Respuesta desde) [\d\.:]+'
    patrones_fallo = {
        r'(Destination Host Unreachable|Host de destino inaccesible)': 810,
        r'(Request timed out|Tiempo de espera agotado|100% packet loss|100% perdidos)': 811,
        r'(Unknown host|No se puede encontrar el host)': 812,
        r'(General error|Error general|Network unreachable)': 813
    }
    
    # Realizar reintentos
    for intento in range(max_attempts):
        try:
            resultado = subprocess.run(
                comando_ping,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout
            )
            
            salida_completa = resultado.stdout + resultado.stderr
            
            # Verificar éxito
            if re.search(patron_exito, salida_completa, re.IGNORECASE):
                return 800
            
            # En el último intento, analizar el tipo de error
            if intento == max_attempts - 1:
                for patron, codigo in patrones_fallo.items():
                    if re.search(patron, salida_completa, re.IGNORECASE):
                        return codigo
                return 813  # Error general por defecto
            
            # Esperar antes del siguiente intento
            time.sleep(delay_between_attempts)
                
        except subprocess.TimeoutExpired:
            if intento == max_attempts - 1:
                return 811
            time.sleep(delay_between_attempts)
            
        except Exception as e:
            if intento == max_attempts - 1:
                log_processor(plant, server, f"[ERROR] Fallo inesperado haciendo ping a {host}: {e}")
                return 813
            time.sleep(delay_between_attempts)

    return 813


def name_host():                #---------- PROBADO ----------#
    try:
        nombre_host = socket.gethostname()
        return nombre_host
    except Exception as e:
        return f"Error al obtener el nombre del host: {e}"


#====================================================================================================
# Inicio de creacion de tuneles SSH

# ssh -f -g -N -L 39533:localhost:38533 QLYMSPROD03

def create_tunnel(loc_port,dest_host,ssh_port,remote_server,px:bool,plant=None):
    if px:
        pid_file = config.PX_PID_FILE
    else:
        pid_file = config.IA_PID_FILE

    # Comando SSH para crear el túnel
    ssh_command = ["ssh", "-f", "-g", "-N", "-L",
                   f"{loc_port}:{dest_host}:{ssh_port}",
                   remote_server]

    try:
        log_processor(plant, remote_server, f"Creando túnel a {remote_server} al puerto {ssh_port}")

        # Ejecutar el comando SSH directamente con subprocess.run
        # Esto evita problemas con Popen que pueden ocurrir en algunos entornos
        result = subprocess.run(ssh_command, stderr=subprocess.PIPE, text=True)

        # Verificar el resultado
        if result.returncode != 0:
            log_processor(plant, remote_server, f"[ERROR] Error al crear el túnel SSH en {remote_server}. Código de salida: {result.returncode}. Mensaje: {result.stderr}")

            # Aun así verificamos si el túnel se creó
            if check_tunnel_status(loc_port):
                log_processor(plant, remote_server, f"A pesar del error, el túnel parece estar activo en puerto {loc_port}")
                # Encontrar y guardar el PID
                tunnel_pid = find_tunnel_pid(loc_port)
                if tunnel_pid:
                    with open(pid_file, 'w') as f:
                        f.write(str(tunnel_pid))
                    log_processor(plant, remote_server, f"Túnel SSH creado exitosamente (PID: {tunnel_pid})")
                    return True
            return False

        # Verificar que el túnel esté activo
        time.sleep(1)  # Dar tiempo para que el túnel se establezca
        if check_tunnel_status(loc_port):
            # Encontrar el PID del proceso SSH
            tunnel_pid = find_tunnel_pid(loc_port)
            if tunnel_pid:
                # Guardar el PID en un archivo
                with open(pid_file, 'w') as f:
                    f.write(str(tunnel_pid))
                log_processor(plant, remote_server, f"Túnel SSH creado exitosamente (PID: {tunnel_pid}). Túnel activo al puerto {ssh_port}")
                return True
            else:
                log_processor(plant, remote_server, "[ERROR] El túnel está activo pero no se pudo encontrar el PID.")
                return True  # Devolvemos True porque el túnel sí se creó
        else:
            log_processor(plant, remote_server, f"[ERROR] Error al crear el túnel SSH. No se detecta actividad en el puerto {loc_port}")
            return False
    except Exception as e:
        log_processor(plant, remote_server, f"[ERROR] Error al crear el túnel SSH: {e}")
        # Aun así verificamos si el túnel se creó
        if check_tunnel_status(loc_port):
            log_processor(plant, remote_server, f"A pesar del error, el túnel parece estar activo en puerto {loc_port}")
            # Intentar encontrar y guardar el PID
            tunnel_pid = find_tunnel_pid(loc_port)
            if tunnel_pid:
                with open(pid_file, 'w') as f:
                    f.write(str(tunnel_pid))
                return True
        return False


def check_tunnel_status(loc_port):
    # Basado en psutil: funciona igual en Windows y Linux, sin depender
    # del formato de salida de comandos como 'ss' o 'netstat'.
    return find_tunnel_pid(loc_port) is not None


def find_tunnel_pid(loc_port):
    try:
        for conn in psutil.net_connections(kind='inet'):
            if (conn.status == psutil.CONN_LISTEN
                    and conn.laddr
                    and conn.laddr.port == loc_port
                    and conn.pid):
                return conn.pid
        return None
    except (psutil.AccessDenied, PermissionError) as e:
        print(f"Error al buscar el proceso (permisos insuficientes): {e}")
        return None
    except Exception as e:
        print(f"Error al buscar el proceso: {e}")
        return None


def close_tunnel(loc_port, px: bool, plant=None, serv_name=None, _retries: int = 0):
    if px:
        pid_file = config.PX_PID_FILE
    else:
        pid_file = config.IA_PID_FILE

    log_processor(plant, serv_name, "Cerrando túnel SSH...")

    # Leer el PID del archivo o buscarlo
    if not os.path.exists(pid_file):
        log_processor(plant, serv_name, f"Archivo PID {pid_file} no encontrado. Buscando proceso por puerto...")
        pid = find_tunnel_pid(loc_port)
        if not pid:
            log_processor(plant, serv_name, f"No se encontró ningún túnel SSH en el puerto {loc_port}")
            # Verificar una última vez
            if not check_tunnel_status(loc_port):
                log_processor(plant, serv_name, "No hay ningún túnel activo en el puerto. Nada que cerrar.")
                return True
            else:
                log_processor(plant, serv_name, f"[ERROR] Hay un túnel activo en el puerto {loc_port}, pero no se pudo determinar su PID.")
                return False
    else:
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            log_processor(plant, serv_name, f"PID leído del archivo: {pid}")
        except Exception as e:
            log_processor(plant, serv_name, f"[ERROR] Error al leer el archivo PID: {e}")
            pid = find_tunnel_pid(loc_port)
            if not pid:
                # Si no se encuentra PID pero el túnel está activo
                if check_tunnel_status(loc_port):
                    log_processor(plant, serv_name, f"[ERROR] Hay un túnel activo en el puerto {loc_port}, pero no se pudo determinar su PID.")
                    return False
                return True

    # Cerrar el proceso
    try:
        # Intentar terminar el proceso (psutil.terminate/kill funcionan igual en Windows y Linux)
        log_processor(plant, serv_name, f"Enviando señal de terminación al proceso {pid}...")
        proceso = psutil.Process(pid)
        proceso.terminate()

        try:
            proceso.wait(timeout=2)
            log_processor(plant, serv_name, f"El proceso {pid} ha terminado")
        except psutil.TimeoutExpired:
            log_processor(plant, serv_name, f"El proceso {pid} sigue activo. Forzando terminación...")
            proceso.kill()
            try:
                proceso.wait(timeout=1)
            except psutil.TimeoutExpired:
                pass

        # Verificar que el túnel esté cerrado
        if not check_tunnel_status(loc_port):
            log_processor(plant, serv_name, "Túnel cerrado exitosamente.")

            # Eliminar el archivo PID si existe
            if os.path.exists(pid_file):
                os.remove(pid_file)

            return True
        else:
            log_processor(plant, serv_name, f"[ERROR] El túnel sigue activo en puerto {loc_port} a pesar de cerrar el proceso. Intentando método alternativo...")
            alternative_close(loc_port)

            # Verificar nuevamente
            if not check_tunnel_status(loc_port):
                log_processor(plant, serv_name, "Túnel cerrado exitosamente con método alternativo.")
                if os.path.exists(pid_file):
                    os.remove(pid_file)
                return True
            else:
                log_processor(plant, serv_name, "[ERROR] No se pudo cerrar el túnel. Intente terminar el proceso ssh manualmente.")
                return False

    except psutil.NoSuchProcess:
        log_processor(plant, serv_name, f"El proceso {pid} no existe.")

        # Verificar si aún existe un túnel en el puerto
        if check_tunnel_status(loc_port):
            log_processor(plant, serv_name, f"Sin embargo, el puerto {loc_port} sigue en uso. Intentando encontrar el proceso correcto...")
            new_pid = find_tunnel_pid(loc_port)
            if new_pid:
                log_processor(plant, serv_name, f"Encontrado nuevo PID: {new_pid}")
                # Actualizar el PID en el archivo
                with open(pid_file, 'w') as f:
                    f.write(str(new_pid))
                # Intentar de nuevo con el nuevo PID, con límite de reintentos
                if _retries < config.MAX_RETRIES:
                    return close_tunnel(loc_port, px, plant, serv_name, _retries + 1)
                else:
                    log_processor(plant, serv_name, "[ERROR] Máximo de reintentos alcanzado. No se pudo cerrar el túnel.")
                    return False
            else:
                log_processor(plant, serv_name, "No se pudo encontrar el PID. Intentando método alternativo...")
                alternative_close(loc_port)
                if not check_tunnel_status(loc_port):
                    log_processor(plant, serv_name, "Túnel cerrado exitosamente con método alternativo.")
                    if os.path.exists(pid_file):
                        os.remove(pid_file)
                    return True
                else:
                    log_processor(plant, serv_name, "[ERROR] No se pudo cerrar el túnel con método alternativo.")
                    return False

        # Limpiar el archivo PID si existe
        if os.path.exists(pid_file):
            os.remove(pid_file)

        return True

    except Exception as e:
        log_processor(plant, serv_name, f"[ERROR] Error al cerrar el túnel: {e}")
        return False


def alternative_close(loc_port):
    # Busca procesos ssh cuya línea de comando referencie el puerto local
    # y los termina. Funciona igual en Windows y Linux (antes usaba 'pkill',
    # exclusivo de Unix).
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            cmdline = ' '.join(proc.info.get('cmdline') or [])
            if 'ssh' in (proc.info.get('name') or '').lower() and f":{loc_port}" in cmdline:
                try:
                    proc.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        time.sleep(1)
    except Exception as e:
        print(f"Error en método alternativo: {e}")


# Fin de creacion de Tuneles
#====================================================================================================