from file_processor import InfoPlant, InfoCam_url, read_yaml, log_processor
from system_processor import ping, name_host, create_tunnel, close_tunnel
from datetime import datetime
from cameras import Camera
import config


px_loc_port = config.PX_LOC_PORT
ia_loc_port = config.IA_LOC_PORT


def CheckAll():                                 #---------- PROBADO ----------#
    codigo, dat_servers = InfoPlant('ALL', None)

    # Verificar que la lectura fue exitosa
    if codigo != 900:
        log_processor(None,None, codigo, True)
        return

    for _, dat_server in dat_servers.items():
        CheckServer(dat_server)

        
def CheckPlant(plant, server):                  #---------- PROBADO ----------#
    codigo, dat_servers = InfoPlant(plant, server)

    # Verificar que la lectura fue exitosa
    if codigo != 900:
        log_processor(plant, server, codigo, False)
        return

    for _, dat_server in dat_servers.items():
        CheckServer(dat_server)


def CheckServer(dat_server):                    #---------- PROBADO ----------#
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

    # Iniciar el LOG
    log_processor(plant, serv_name, f"{'='*60}", False)

    # Hacer ping al servidor y Enviar el resultado al LOG
    log_processor(plant, serv_name, f"Ping to Server {serv_name} on Plant {plant}", False)
    
    # Determinar qué IP usar según los pings exitosos
    # Ping Zerotier
    result_pingZero = ping(zerotier_ip)

    if result_pingZero == 800:
        log_processor(plant, serv_name, "Zerotier IP", False)
        log_processor(plant, serv_name, result_pingZero, True)
        selected_ip = zerotier_ip

    else:
        # Ping Local
        result_pinglocal = ping(local_ip)
        if result_pinglocal == 800:
            log_processor(plant, serv_name, "Local IP", False)
            log_processor(plant, serv_name, result_pinglocal, True)
            log_processor(plant, serv_name, f"{'='*60}", False)
            selected_ip = local_ip

        else:
            # Ping Cameras
            result_pingcameras = ping(cameras_ip)
            if result_pingcameras == 800:
                log_processor(plant, serv_name, "Cameras IP", False)
                log_processor(plant, serv_name, result_pingcameras, True)
                log_processor(plant, serv_name, f"{'='*60}", False)
                selected_ip = cameras_ip

            else:
                # Ninguna IP disponible
                log_processor(plant, serv_name, "[ERROR] Not IP available", False)
                log_processor(plant, serv_name, f"{'='*60}", False)
                selected_ip = None
                return
   
    
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
        create_tunnel(px_loc_port, proxy_ip, proxy_port, serv_name, True)
        log_processor(plant, serv_name, f"{'='*60}", False)
        tunn_px = True
        proxy_port = px_loc_port
        
    for ia_port in ia_ports:
        if type == "tunnels":
            create_tunnel(ia_loc_port,"localhost",ia_port, serv_name, False)
            log_processor(plant, serv_name, f"{'='*60}", False)
            tunn_ia = True            
            url_yaml = f"http://localhost:{ia_loc_port}/cameras"
            ai_port = ia_loc_port

        else:
            url_yaml = f"http://{selected_ip}:{ia_port}/cameras"
            ai_port = ia_port

        # leer el YAML
        status_code, cameras_data = read_yaml(url_yaml)
        
        # Status - loggear
        log_processor(plant, serv_name, status_code, True)
            
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
            log_processor(plant, serv_name, port_yaml, False)
            log_processor(plant, serv_name, f"{'='*60}", False)
            log_processor(plant, serv_name, "", False)
            
            for alias, cam in active_cam.items():
                video_url = cam.get('videoURL')
                info_cam = InfoCam_url(video_url)

                brand =  info_cam.get('brand')
                cam_ip =  info_cam.get('ip')
                cam_user = info_cam.get('user')
                cam_pass = info_cam.get('password')
                channel = info_cam.get('channel', 1)
                

                # Generar el objeto cámara
                cam_host = Camera(alias, brand, cam_ip, cam_user, cam_pass, 
                                serv_name, plant, ai_port, proxy_ip, proxy_port, channel)
                
                # Verificar el puerto 80 de la cámara
                cam_up = cam_host.Cam_Up()
                log_processor(plant, serv_name, f"Camera: {alias} IP: {cam_ip}", False)
                log_processor(plant, serv_name, cam_up, True)
                
                if cam_up == 100:
                    # Descargar la imagen de la IA
                    ia_image = cam_host.Cam_AI_Image()
                    log_processor(plant, serv_name, ia_image, True)
                    
                    # Descargar la imagen de la cámara
                    cam_image = cam_host.Cam_Image()
                    log_processor(plant, serv_name, cam_image, True)

                    # Descargar la configuración de la cámara
                    cam_conf = cam_host.Cam_Config()
                    log_processor(plant, serv_name, cam_conf, True)
                log_processor(plant, serv_name, f"{'='*60}", False)
            
            # Cerrar tunel IA
            if tunn_ia:
                close_tunnel(ia_loc_port, False)
                tunn_ia = False
        
            log_processor(plant, serv_name, f"{'='*60}", False)
        
        # Cerrar tunel PX
        if tunn_px:
            close_tunnel(px_loc_port, True)
            tunn_px = False
            
        log_processor(plant, serv_name, f"{'='*60}", False)
        log_processor(plant, serv_name, f"", False)
