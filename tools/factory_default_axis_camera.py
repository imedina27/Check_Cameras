"""
Restaura una cámara Axis a valores de fábrica via VAPIX, PRESERVANDO la
configuración de IP/máscara/gateway (GET /axis-cgi/factorydefault.cgi).

No confundir con /axis-cgi/hardfactorydefault.cgi, que sí borra la IP —
este script llama únicamente al endpoint que la preserva.

Uso:
    python tools/factory_default_axis_camera.py --ip 192.168.1.206 --user admin --password "Quantum18!"

Pensado para correr directo en el servidor que sí tiene alcance de red a la
cámara (no pasa por el proxy/túnel del programa principal). Es una acción
que SÍ escribe en la cámara y no se puede deshacer — por eso queda aparte,
como utilidad de un solo propósito, y pide confirmación antes de ejecutar
salvo que se pase --yes.
"""
import argparse
import sys

import requests


def factory_default_axis_camera(ip, user, password, timeout=15, proxy=None):
    proxies = {"http": proxy, "https": proxy} if proxy else {}
    auth = requests.auth.HTTPDigestAuth(user, password)
    url = f"http://{ip}/axis-cgi/factorydefault.cgi"

    try:
        response = requests.get(url, auth=auth, proxies=proxies, timeout=timeout)
    except requests.exceptions.Timeout:
        print(f"[ERROR] Timeout al conectar a {url} — la cámara no está respondiendo por HTTP. "
              "Si ni el reinicio simple ni esto responden, probablemente necesite un power-cycle físico.")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"[ERROR] No se pudo conectar a {url}: {e}")
        return False

    if response.status_code == 200:
        print(f"[OK] Reset de fábrica (con IP preservada) enviado correctamente ({url}). "
              "La cámara va a reiniciarse sola — espera unos minutos antes de volver a intentar contactarla.")
        return True
    elif response.status_code == 401:
        print(f"[ERROR] Credenciales rechazadas (401) en {url}. Revisa usuario/contraseña.")
        return False
    elif response.status_code == 404:
        print(f"[ERROR] {url} no existe en este firmware (404). Revisa el modelo/versión de la cámara "
              "antes de intentar con otra ruta.")
        return False
    else:
        print(f"[ERROR] Respuesta inesperada de {url}: {response.status_code} {response.text[:200]}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Restaura una cámara Axis a valores de fábrica via VAPIX, preservando IP/máscara/gateway."
    )
    parser.add_argument("--ip", required=True, help="IP de la cámara")
    parser.add_argument("--user", required=True, help="Usuario con permisos de administrador")
    parser.add_argument("--password", required=True, help="Contraseña de ese usuario")
    parser.add_argument("--proxy", default=None, help="Proxy HTTP opcional (ej. http://localhost:38533)")
    parser.add_argument("--timeout", type=int, default=15, help="Timeout en segundos (default 15)")
    parser.add_argument("--yes", action="store_true", help="No pedir confirmación antes de ejecutar")
    args = parser.parse_args()

    if not args.yes:
        print("Esto va a restaurar TODA la configuración de la cámara a valores de fábrica")
        print("(la IP, máscara y gateway se preservan — todo lo demás NO).")
        print("Esta acción no se puede deshacer.")
        respuesta = input(f"¿Confirmas el reset de fábrica de la cámara en {args.ip}? [s/N]: ").strip().lower()
        if respuesta != "s":
            print("Cancelado.")
            sys.exit(0)

    exito = factory_default_axis_camera(args.ip, args.user, args.password, timeout=args.timeout, proxy=args.proxy)
    sys.exit(0 if exito else 1)


if __name__ == "__main__":
    main()
