"""
Reinicia una cámara Axis via VAPIX (GET /axis-cgi/restart.cgi).

Uso:
    python tools/restart_axis_camera.py --ip 192.168.1.206 --user admin --password "Quantum18!"

Pensado para correr directo en el servidor que sí tiene alcance de red a la
cámara (no pasa por el proxy/túnel del programa principal). Es una acción
que SÍ escribe en la cámara (a diferencia del resto del proyecto, que solo
lee) — por eso queda aparte, como utilidad de un solo propósito, y pide
confirmación antes de ejecutar salvo que se pase --yes.
"""
import argparse
import sys

import requests


def restart_axis_camera(ip, user, password, timeout=10, proxy=None):
    proxies = {"http": proxy, "https": proxy} if proxy else {}
    auth = requests.auth.HTTPDigestAuth(user, password)

    # Endpoint moderno primero; algunas cámaras muy viejas solo responden
    # en la ruta antigua bajo /admin/.
    for url in (f"http://{ip}/axis-cgi/restart.cgi", f"http://{ip}/axis-cgi/admin/restart.cgi"):
        try:
            response = requests.get(url, auth=auth, proxies=proxies, timeout=timeout)
        except requests.exceptions.Timeout:
            print(f"[ERROR] Timeout al conectar a {url} — la cámara no está respondiendo por HTTP.")
            continue
        except requests.exceptions.ConnectionError as e:
            print(f"[ERROR] No se pudo conectar a {url}: {e}")
            continue

        if response.status_code == 200:
            print(f"[OK] Reinicio enviado correctamente ({url}).")
            return True
        elif response.status_code == 401:
            print(f"[ERROR] Credenciales rechazadas (401) en {url}. Revisa usuario/contraseña.")
            return False
        elif response.status_code == 404:
            continue  # probar la siguiente ruta
        else:
            print(f"[ERROR] Respuesta inesperada de {url}: {response.status_code} {response.text[:200]}")
            return False

    print("[ERROR] Ninguna ruta de reinicio respondió. Si la cámara no contesta nada por HTTP "
          "(ni la interfaz web, ni esto), probablemente necesite un power-cycle físico.")
    return False


def main():
    parser = argparse.ArgumentParser(description="Reinicia una cámara Axis via VAPIX.")
    parser.add_argument("--ip", required=True, help="IP de la cámara")
    parser.add_argument("--user", required=True, help="Usuario con permisos de administrador")
    parser.add_argument("--password", required=True, help="Contraseña de ese usuario")
    parser.add_argument("--proxy", default=None, help="Proxy HTTP opcional (ej. http://localhost:38533)")
    parser.add_argument("--timeout", type=int, default=10, help="Timeout en segundos (default 10)")
    parser.add_argument("--yes", action="store_true", help="No pedir confirmación antes de reiniciar")
    args = parser.parse_args()

    if not args.yes:
        respuesta = input(f"Vas a reiniciar la cámara en {args.ip}. ¿Confirmas? [s/N]: ").strip().lower()
        if respuesta != "s":
            print("Cancelado.")
            sys.exit(0)

    exito = restart_axis_camera(args.ip, args.user, args.password, timeout=args.timeout, proxy=args.proxy)
    sys.exit(0 if exito else 1)


if __name__ == "__main__":
    main()
