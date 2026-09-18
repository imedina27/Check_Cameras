from file_processor import InfoPlant, InfoCam_url, read_yaml, log_processor
from file_processor import status_text, is_success_code, write_summary, log_camera_time
from system_processor import ping, name_host, create_tunnel, close_tunnel
from datetime import datetime
from cameras import Camera
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


def _new_server_result(dat_server, problem=None):
    return {
        'serv_name': dat_server.get('serv_name', 'DESCONOCIDO'),
        'plant': dat_server.get('plant', 'DESCONOCIDO'),
        'problem': problem,
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


REQUIRED_SERVER_KEYS = ['serv_name', 'plant', 'cam_activate', 'type', 'addresses', 'proxy_port', 'ia_ports']
REQUIRED_ADDRESS_KEYS = ['local', 'cameras', 'zerotier']


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
    cam_activate =dat_server['cam_activate']
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
            
            for alias, cam in active_cam.items():
                video_url = cam.get('videoURL')
                info_cam = InfoCam_url(video_url, plant, serv_name)

                brand =  info_cam.get('brand')
                cam_ip =  info_cam.get('ip')
                cam_user = info_cam.get('user')
                cam_pass = info_cam.get('password')
                channel = info_cam.get('channel', 1)
                

                # Generar el objeto cámara
                cam_host = Camera(alias, brand, cam_ip, cam_user, cam_pass, 
                                serv_name, plant, ai_port, proxy_ip, proxy_port, channel)
                
                # Verificar el puerto 80 de la cámara
                camera_result = {'alias': alias, 'ip': cam_ip, 'failures': []}
                inicio_camara = time.perf_counter()

                cam_up = cam_host.Cam_Up()
                log_processor(plant, serv_name, f"Camera: {alias} IP: {cam_ip}")
                log_processor(plant, serv_name, cam_up)

                if cam_up == 100:
                    # Descargar la imagen de la IA
                    ia_image = cam_host.Cam_AI_Image()
                    log_processor(plant, serv_name, ia_image)
                    if not is_success_code(ia_image):
                        camera_result['failures'].append(f"Imagen IA: {_clean_status(ia_image)}")

                    # Descargar la imagen de la cámara
                    cam_image = cam_host.Cam_Image()
                    log_processor(plant, serv_name, cam_image)
                    if not is_success_code(cam_image):
                        camera_result['failures'].append(f"Imagen cámara: {_clean_status(cam_image)}")

                    # Descargar la configuración de la cámara
                    cam_conf = cam_host.Cam_Config()
                    log_processor(plant, serv_name, cam_conf)
                    if not is_success_code(cam_conf):
                        camera_result['failures'].append(f"Configuración: {_clean_status(cam_conf)}")
                else:
                    camera_result['failures'].append(f"Puerto 80: {_clean_status(cam_up)}")

                camera_result['complete'] = len(camera_result['failures']) == 0
                elapsed = time.perf_counter() - inicio_camara
                log_camera_time(plant, serv_name, alias, elapsed)
                server_result['cameras'].append(camera_result)
                log_processor(plant, serv_name, f"{'='*60}")
            
            # Cerrar tunel IA
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

    return server_result
