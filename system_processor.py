import subprocess
import platform
import socket
import signal
import config
import time
import os
import re


def ping(host):                 #---------- PROBADO ----------#
    # Validación inicial
    if not host or host == '':
        return 814
    
    # Configuración desde variables de entorno
    max_attempts = config.MAX_PING_ATTEMPTS
    timeout = config.PING_TIMEOUT
    delay_between_attempts = config.RETRY_DELAY
    
    # Configuración según sistema operativo
    is_windows = platform.system().lower() == "windows"
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
            
        except Exception:
            if intento == max_attempts - 1:
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

def create_tunnel(loc_port,dest_host,ssh_port,remote_server,px:bool):
    if px:
        pid_file = config.PX_PID_FILE
    else:
        pid_file = config.IA_PID_FILE

    # Comando SSH para crear el túnel
    ssh_command = ["ssh", "-f", "-g", "-N", "-L", 
                   f"{loc_port}:{dest_host}:{ssh_port}", 
                   remote_server]
    
    try:
        print(f"Creando túnel a {remote_server} al puerto {ssh_port}")
        
        # Ejecutar el comando SSH directamente con subprocess.run
        # Esto evita problemas con Popen que pueden ocurrir en algunos entornos
        result = subprocess.run(ssh_command, stderr=subprocess.PIPE, text=True)
        
        # Verificar el resultado
        if result.returncode != 0:
            print(f"Error al crear el túnel SSH en {remote_server}. Código de salida: {result.returncode}")
            print(f"Mensaje de error: {result.stderr}")
            
            # Aun así verificamos si el túnel se creó
            if check_tunnel_status(loc_port):
                print(f"A pesar del error, el túnel parece estar activo en puerto {loc_port}")
                # Encontrar y guardar el PID
                tunnel_pid = find_tunnel_pid(loc_port)
                if tunnel_pid:
                    with open(pid_file, 'w') as f:
                        f.write(str(tunnel_pid))
                    print(f"Túnel SSH creado exitosamente (PID: {tunnel_pid})")
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
                print(f"Túnel SSH creado exitosamente (PID: {tunnel_pid})")
                print(f"Túnel activo al puerto {ssh_port}")
                return True
            else:
                print("¡Error! El túnel está activo pero no se pudo encontrar el PID.")
                return True  # Devolvemos True porque el túnel sí se creó
        else:
            print(f"Error al crear el túnel SSH. No se detecta actividad en el puerto {loc_port}")
            return False
    except Exception as e:
        print(f"Error al crear el túnel SSH: {e}")
        # Aun así verificamos si el túnel se creó
        if check_tunnel_status(loc_port):
            print(f"A pesar del error, el túnel parece estar activo en puerto {loc_port}")
            # Intentar encontrar y guardar el PID
            tunnel_pid = find_tunnel_pid(loc_port)
            if tunnel_pid:
                with open(pid_file, 'w') as f:
                    f.write(str(tunnel_pid))
                return True
        return False


def check_tunnel_status(loc_port):

    try:
        # Usar ss en lugar de netstat para mayor compatibilidad
        result = subprocess.run(
            ["ss", "-tulpn"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        
        return f":{loc_port}" in result.stdout
    except Exception as e:
        print(f"Error al verificar estado del túnel: {e}")
        return False


def find_tunnel_pid(loc_port):

    try:
        # Buscar procesos que usan el puerto específico utilizando ss
        result = subprocess.run(
            ["ss", "-tulpn"], 
            capture_output=True, 
            text=True
        )
        
        if result.returncode != 0:
            return None
        
        # Buscar líneas que contienen el puerto y 'ssh'
        pattern = fr':{loc_port}\s+.*\s+users:\(\("ssh",pid=(\d+),'
        matches = re.findall(pattern, result.stdout)
        
        if matches:
            return int(matches[0])
            
        # Intento alternativo para encontrar cualquier proceso usando el puerto
        pattern = fr':{loc_port}\s+.*\s+users:\(\("([^"]+)",pid=(\d+),'
        matches = re.findall(pattern, result.stdout)
        
        if matches:
            print(f"Encontrado proceso '{matches[0][0]}' con PID {matches[0][1]} usando el puerto {loc_port}")
            return int(matches[0][1])
            
        return None
    except Exception as e:
        print(f"Error al buscar el proceso: {e}")
        return None


def close_tunnel(loc_port, px: bool, _retries: int = 0):
    if px:
        pid_file = config.PX_PID_FILE
    else:
        pid_file = config.IA_PID_FILE

    print("Cerrando túnel SSH...")
    
    # Leer el PID del archivo o buscarlo
    if not os.path.exists(pid_file):
        print(f"Archivo PID {pid_file} no encontrado. Buscando proceso por puerto...")
        pid = find_tunnel_pid(loc_port)
        if not pid:
            print(f"No se encontró ningún túnel SSH en el puerto {loc_port}")
            # Verificar una última vez
            if not check_tunnel_status(loc_port):
                print("No hay ningún túnel activo en el puerto. Nada que cerrar.")
                return True
            else:
                print(f"Hay un túnel activo en el puerto {loc_port}, pero no se pudo determinar su PID.")
                return False
    else:
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            print(f"PID leído del archivo: {pid}")
        except Exception as e:
            print(f"Error al leer el archivo PID: {e}")
            pid = find_tunnel_pid(loc_port)
            if not pid:
                # Si no se encuentra PID pero el túnel está activo
                if check_tunnel_status(loc_port):
                    print(f"Hay un túnel activo en el puerto {loc_port}, pero no se pudo determinar su PID.")
                    return False
                return True
    
    # Cerrar el proceso
    try:
        # Intentar terminar el proceso
        print(f"Enviando señal de terminación al proceso {pid}...")
        os.kill(pid, signal.SIGTERM)
        
        # Esperar un momento
        time.sleep(2)
        
        # Verificar que el proceso haya terminado
        try:
            os.kill(pid, 0)
            print(f"El proceso {pid} sigue activo. Forzando terminación...")
            os.kill(pid, signal.SIGKILL)
            time.sleep(1)
        except OSError:
            print(f"El proceso {pid} ha terminado")
        
        # Verificar que el túnel esté cerrado
        if not check_tunnel_status(loc_port):
            print("Túnel cerrado exitosamente.")
            
            # Eliminar el archivo PID si existe
            if os.path.exists(pid_file):
                os.remove(pid_file)
                
            return True
        else:
            print(f"¡Error! El túnel sigue activo en puerto {loc_port} a pesar de cerrar el proceso.")
            # Intentar cerrar usando un método alternativo
            print("Intentando método alternativo para cerrar el túnel...")
            alternative_close(loc_port)
            
            # Verificar nuevamente
            if not check_tunnel_status(loc_port):
                print("Túnel cerrado exitosamente con método alternativo.")
                if os.path.exists(pid_file):
                    os.remove(pid_file)
                return True
            else:
                print("No se pudo cerrar el túnel. Intente manualmente con 'pkill ssh'")
                return False
            
    except ProcessLookupError:
        print(f"El proceso {pid} no existe.")
        
        # Verificar si aún existe un túnel en el puerto
        if check_tunnel_status(loc_port):
            print(f"Sin embargo, el puerto {loc_port} sigue en uso. Intentando encontrar el proceso correcto...")
            new_pid = find_tunnel_pid(loc_port)
            if new_pid:
                print(f"Encontrado nuevo PID: {new_pid}")
                # Actualizar el PID en el archivo
                with open(pid_file, 'w') as f:
                    f.write(str(new_pid))
                # Intentar de nuevo con el nuevo PID, con límite de reintentos
                if _retries < config.MAX_RETRIES:
                    return close_tunnel(loc_port, px, _retries + 1)
                else:
                    print("Máximo de reintentos alcanzado. No se pudo cerrar el túnel.")
                    return False
            else:
                print("No se pudo encontrar el PID. Intentando método alternativo...")
                alternative_close(loc_port)
                if not check_tunnel_status(loc_port):
                    print("Túnel cerrado exitosamente con método alternativo.")
                    if os.path.exists(pid_file):
                        os.remove(pid_file)
                    return True
                else:
                    print("No se pudo cerrar el túnel con método alternativo.")
                    return False
        
        # Limpiar el archivo PID si existe
        if os.path.exists(pid_file):
            os.remove(pid_file)
            
        return True
        
    except Exception as e:
        print(f"Error al cerrar el túnel: {e}")
        return False


def alternative_close(loc_port):
    
    try:
        # Intentar matar procesos SSH que estén usando el puerto específico
        subprocess.run(["pkill", "-f", f"ssh.*:{loc_port}"])
        time.sleep(1)
    except Exception as e:
        print(f"Error en método alternativo: {e}")


# Fin de creacion de Tuneles
#====================================================================================================