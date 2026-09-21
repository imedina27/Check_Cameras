from file_processor import InfoPlant, InfoCam_url, read_yaml, log_processor
from file_processor import status_text, is_success_code, write_summary, log_camera_time
from file_processor import checkpoint_server_log, replace_camera_section
from system_processor import ping, name_host, create_tunnel, close_tunnel
from datetime import datetime
from cameras import Camera
import concurrent.futures
import config
import time


px_loc_port = config.PX_LOC_PORT
ia_loc_port = config.IA_LOC_PORT


def CheckAll():                                 #---------- PROBADO ----------#
    codigo, dat_servers = InfoPlant('ALL', None)

    # Verificar que la lectura fue exitosa
    if codigo != 900:
        log_processor(None,None, codigo)
        return

    results = [_CheckServerSafe(dat_server) for _, dat_server in dat_servers.items()]
    write_summary(results)


def CheckPlant(plant, server):                  #---------- PROBADO ----------#
    codigo, dat_servers = InfoPlant(plant, server)

    # Verificar que la lectura fue exitosa
    if codigo != 900:
        log_processor(plant, server, codigo)
        return

    results = [_CheckServerSafe(dat_server) for _, dat_server in dat_servers.items()]
    if len(results) > 1:
        write_summary(results)


def _clean_status(status_code):
    """status_text() sin espacios de relleno (esos solo alinean columnas en
    el log principal; embebidos en una frase del resumen se ven raros)."""
    return " ".join(status_text(status_code).split())


def _new_server_result(dat_server, problem=None, problem_type="sin_conexion"):
    return {
        'serv_name': dat_server.get('serv_name', 'DESCONOCIDO'),
        'plant': dat_server.get('plant', 'DESCONOCIDO'),
        'problem': problem,
        'problem_type': problem_type,
        'cameras': [],
    }


def _CheckServerSafe(dat_server):
    """Ejecuta CheckServer aislando errores para que un servidor mal
    configurado no detenga la revisión del resto. Regresa siempre un
    resultado (para el resumen final), incluso si CheckServer truena."""
    try:
        return CheckServer(dat_server)
    except Exception as e:
        serv_name = dat_server.get('serv_name', 'DESCONOCIDO')
        plant = dat_server.get('plant', 'DESCONOCIDO')
        log_processor(plant, serv_name, f"[ERROR] Fallo inesperado revisando el servidor: {e}")
        return _new_server_result(dat_server, problem=f"Fallo inesperado: {e}")


REQUIRED_SERVER_KEYS = ['serv_name', 'plant', 'type', 'addresses', 'proxy_port', 'ia_ports']
REQUIRED_ADDRESS_KEYS = ['local', 'cameras', 'zerotier']


def _process_camera(alias, cam, serv_name, plant, ai_port, proxy_ip, proxy_port):
    """Revisa una sola cámara completa (Cam_Up + Cam_AI_Image + Cam_Image +
    Cam_Config) y regresa su resultado. Cada línea de log lleva el alias de
    la cámara al frente, porque varias cámaras corren en paralelo y sus
    líneas se intercalan en el log del servidor."""
    video_url = cam.get('videoURL')
    info_cam = InfoCam_url(video_url, plant, serv_name)

    brand = info_cam.get('brand')
    cam_ip = info_cam.get('ip')
    cam_user = info_cam.get('user')
    cam_pass = info_cam.get('password')
    channel = info_cam.get('channel', 1)

    # Generar el objeto cámara
    cam_host = Camera(alias, brand, cam_ip, cam_user, cam_pass,
                    serv_name, plant, ai_port, proxy_ip, proxy_port, channel)

    # 'steps' guarda (hora, proceso, status_code) de cada paso que sí corrió —
    # junto con 'hora_ip'/'hora_tiempo'/'elapsed', es lo que necesita
    # replace_camera_section() para reconstruir el bloque de esta cámara
    # ordenado (el log en vivo, más abajo, sigue igual para monitoreo en
    # tiempo real / robustez ante un corte a medio camino).
    camera_result = {'alias': alias, 'ip': cam_ip, 'failures': [], 'steps': []}
    alias_tag = f"{alias}: "
    inicio_camara = time.perf_counter()

    # Verificar el puerto 80 de la cámara
    camera_result['hora_ip'] = datetime.now().strftime('%H:%M:%S')
    cam_up = cam_host.Cam_Up()
    log_processor(plant, serv_name, f"{alias} IP: {cam_ip}")
    log_processor(plant, serv_name, cam_up, alias_tag, proceso="Puerto 80")
    camera_result['steps'].append((datetime.now().strftime('%H:%M:%S'), "Puerto 80", cam_up))

    if cam_up == 100:
        # Descargar la imagen de la IA
        ia_image = cam_host.Cam_AI_Image()
        log_processor(plant, serv_name, ia_image, alias_tag, proceso="Imagen IA")
        camera_result['steps'].append((datetime.now().strftime('%H:%M:%S'), "Imagen IA", ia_image))
        if not is_success_code(ia_image):
            camera_result['failures'].append(f"Imagen IA: {_clean_status(ia_image)}")

        # Descargar la imagen de la cámara
        cam_image = cam_host.Cam_Image()
        log_processor(plant, serv_name, cam_image, alias_tag, proceso="Imagen cámara")
        camera_result['steps'].append((datetime.now().strftime('%H:%M:%S'), "Imagen cámara", cam_image))
        if not is_success_code(cam_image):
            camera_result['failures'].append(f"Imagen cámara: {_clean_status(cam_image)}")

        # Descargar la configuración de la cámara
        cam_conf = cam_host.Cam_Config()
        log_processor(plant, serv_name, cam_conf, alias_tag, proceso="Configuración")
        camera_result['steps'].append((datetime.now().strftime('%H:%M:%S'), "Configuración", cam_conf))
        if not is_success_code(cam_conf):
            camera_result['failures'].append(f"Configuración: {_clean_status(cam_conf)}")
    else:
        camera_result['failures'].append(f"Puerto 80: {_clean_status(cam_up)}")

    camera_result['complete'] = len(camera_result['failures']) == 0
    elapsed = time.perf_counter() - inicio_camara
    log_camera_time(plant, serv_name, alias, elapsed)
    camera_result['elapsed'] = elapsed
    camera_result['hora_tiempo'] = datetime.now().strftime('%H:%M:%S')
    return camera_result


def _process_camera_safe(alias, cam, serv_name, plant, ai_port, proxy_ip, proxy_port):
    """Aísla errores de una cámara para que no tumbe a las demás que se
    están procesando en paralelo."""
    try:
        return _process_camera(alias, cam, serv_name, plant, ai_port, proxy_ip, proxy_port)
    except Exception as e:
        log_processor(plant, serv_name, f"[ERROR] {alias}: fallo inesperado procesando la cámara: {e}")
        return {'alias': alias, 'ip': '', 'failures': [f"Fallo inesperado: {e}"], 'complete': False, 'steps': []}


def CheckServer(dat_server):                    #---------- PROBADO ----------#
    # Validar que el YAML traiga los campos mínimos antes de usarlos
    missing = [key for key in REQUIRED_SERVER_KEYS if key not in dat_server]
    if missing:
        serv_name = dat_server.get('serv_name', 'DESCONOCIDO')
        plant = dat_server.get('plant', 'DESCONOCIDO')
        log_processor(plant, serv_name, f"[ERROR] Configuración incompleta, faltan campos: {', '.join(missing)}")
        return _new_server_result(dat_server, problem=f"Configuración incompleta, faltan campos: {', '.join(missing)}")

    if isinstance(dat_server['addresses'], dict):
        missing_addr = [key for key in REQUIRED_ADDRESS_KEYS if key not in dat_server['addresses']]
    else:
        missing_addr = REQUIRED_ADDRESS_KEYS
    if missing_addr:
        log_processor(dat_server['plant'], dat_server['serv_name'],
                      f"[ERROR] Configuración incompleta en 'addresses', faltan campos: {', '.join(missing_addr)}")
        return _new_server_result(dat_server, problem=f"Configuración incompleta en 'addresses', faltan campos: {', '.join(missing_addr)}")

    # Datos básicos
    serv_name = dat_server['serv_name']
    plant =  dat_server['plant']
    cam_activate = dat_server.get('cam_activate', False)
    type = dat_server['type']

    # Direcciones
    local_ip = dat_server['addresses']['local']
    cameras_ip = dat_server['addresses']['cameras']
    zerotier_ip = dat_server['addresses']['zerotier']

    # Puertos
    proxy_port = dat_server['proxy_port']
    ia_ports = dat_server['ia_ports']

    server_result = _new_server_result(dat_server)

    # Iniciar el LOG
    log_processor(plant, serv_name, f"{'='*60}")

    # Hacer ping al servidor y Enviar el resultado al LOG
    log_processor(plant, serv_name, f"Ping to Server {serv_name} on Plant {plant}")
    
    # Determinar qué IP usar según los pings exitosos
    # Ping Zerotier
    result_pingZero = ping(zerotier_ip, plant, serv_name)

    if result_pingZero == 800:
        log_processor(plant, serv_name, "Zerotier IP")
        log_processor(plant, serv_name, result_pingZero)
        selected_ip = zerotier_ip

    else:
        # Ping Local
        result_pinglocal = ping(local_ip, plant, serv_name)
        if result_pinglocal == 800:
            log_processor(plant, serv_name, "Local IP")
            log_processor(plant, serv_name, result_pinglocal)
            log_processor(plant, serv_name, f"{'='*60}")
            selected_ip = local_ip

        else:
            # Ping Cameras
            result_pingcameras = ping(cameras_ip, plant, serv_name)
            if result_pingcameras == 800:
                log_processor(plant, serv_name, "Cameras IP")
                log_processor(plant, serv_name, result_pingcameras)
                log_processor(plant, serv_name, f"{'='*60}")
                selected_ip = cameras_ip

            else:
                # Ninguna IP disponible
                log_processor(plant, serv_name, "[ERROR] Not IP available")
                log_processor(plant, serv_name, f"{'='*60}")
                selected_ip = None
                return _new_server_result(dat_server, problem="Sin IP disponible (zerotier/local/cámaras)")
   
    
    this_host = name_host()
    this_host = this_host.upper()
    tunn_ia = False
    tunn_px =False

    # Este Servidor
    if this_host == serv_name:
        selected_ip = "localhost"
        proxy_port = ""
        proxy_ip = ""
        
    # Servidor remoto
    elif type == "remote":
        proxy_ip = selected_ip
    
    # Servidor remoto por tunel
    elif type == "tunnels":
        proxy_ip = "localhost"
        create_tunnel(px_loc_port, proxy_ip, proxy_port, serv_name, True, plant)
        log_processor(plant, serv_name, f"{'='*60}")
        tunn_px = True
        proxy_port = px_loc_port
        
    yaml_failures = []

    for ia_port in ia_ports:
        if type == "tunnels":
            create_tunnel(ia_loc_port,"localhost",ia_port, serv_name, False, plant)
            log_processor(plant, serv_name, f"{'='*60}")
            tunn_ia = True
            url_yaml = f"http://localhost:{ia_loc_port}/cameras"
            ai_port = ia_loc_port

        else:
            url_yaml = f"http://{selected_ip}:{ia_port}/cameras"
            ai_port = ia_port

        # leer el YAML
        status_code, cameras_data = read_yaml(url_yaml, plant, serv_name)

        # Status - loggear
        log_processor(plant, serv_name, status_code)

        if status_code != 400:
            yaml_failures.append(f"puerto {ia_port}: {_clean_status(status_code)}")
            # Cierra el bloque del YAML aunque haya fallado — si no, esta
            # línea de error queda pegada directo con el cierre de túneles
            # de más abajo, sin nada que marque dónde termina un bloque y
            # empieza el otro.
            log_processor(plant, serv_name, f"{'='*60}")

        # Procesar resultado
        if status_code == 400:
            active_cam = {}
            for camera in cameras_data['Cameras']:
                if cam_activate and camera.get('activate', 0) < 1:
                    continue  # saltar cámaras inactivas cuando el filtro está ON
                alias = camera.get('alias')
                active_cam[alias] = camera

            total_cam = len(cameras_data['Cameras'])
            total_act = len(active_cam)
            
            port_yaml = (f"Total de camaras {total_cam}, Camaras Activas {total_act} en el puerto: {ia_port}")
            log_processor(plant, serv_name, port_yaml)
            log_processor(plant, serv_name, f"{'='*60}")
            log_processor(plant, serv_name, "")

            # Punto de corte antes de revisar cámaras: replace_camera_section()
            # recorta de vuelta a aquí y reemplaza lo que se haya escrito desde
            # este momento por el bloque ya ordenado (encabezado/túneles/YAML
            # de arriba no se tocan).
            checkpoint = checkpoint_server_log(plant, serv_name)

            # Revisar las cámaras de este servidor en paralelo (no así los
            # servidores entre sí, por el puerto compartido de los túneles)
            batch_cameras = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=config.MAX_CAMERA_WORKERS) as executor:
                futures = [
                    executor.submit(_process_camera_safe, alias, cam, serv_name, plant, ai_port, proxy_ip, proxy_port)
                    for alias, cam in active_cam.items()
                ]
                for future in concurrent.futures.as_completed(futures):
                    batch_cameras.append(future.result())

            server_result['cameras'].extend(batch_cameras)
            replace_camera_section(plant, serv_name, checkpoint, batch_cameras)

            log_processor(plant, serv_name, f"{'='*60}")

        # Cerrar tunel IA — fuera del "if status_code == 400" a propósito: si
        # el YAML falla, el túnel se abrió igual y debe cerrarse igual. Antes
        # quedaba anidado ahí adentro y, si el YAML fallaba, el túnel IA
        # nunca se cerraba — quedaba huérfano ocupando el puerto compartido
        # y arruinaba la lectura de TODOS los servidores siguientes (bug real
        # encontrado en producción: QBYMSPROD08 -> VALLE -> GUADALAJARA ->
        # ATLANTICO, todos fallando en cascada por el mismo puerto atascado).
        if tunn_ia:
            close_tunnel(ia_loc_port, False, plant, serv_name)
            tunn_ia = False
            log_processor(plant, serv_name, f"{'='*60}")

        # Cerrar tunel PX
        if tunn_px:
            close_tunnel(px_loc_port, True, plant, serv_name)
            tunn_px = False
            log_processor(plant, serv_name, f"{'='*60}")

        log_processor(plant, serv_name, "")

    if not server_result['cameras'] and yaml_failures:
        server_result['problem'] = "No se pudo leer el YAML de cámaras (" + "; ".join(yaml_failures) + ")"
        server_result['problem_type'] = "sin_yaml"

    return server_result
