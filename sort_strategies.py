import re


def _numeric_suffix_key(serv_name):
    # Ordena por el numero al final del nombre del servidor, sin importar el
    # prefijo (QLYMSPROD01, QBYMSPROD07, QLYMSPROD11 -> 1, 7, 11). Los
    # servidores sin numero al final quedan al final, ordenados entre si
    # alfabeticamente.
    match = re.search(r"(\d+)$", serv_name or "")
    numero = int(match.group(1)) if match else float("inf")
    return (numero, serv_name or "")


def _alphabetical_key(serv_name):
    return (serv_name or "",)


# Registro de estrategias de orden por nombre de servidor. Para agregar una
# estrategia nueva (ej. un cliente con otra convencion de nombres): escribir
# la funcion aqui y agregarla al diccionario — no hace falta tocar nada mas,
# se selecciona con LOG_SORT_STRATEGY en el .env.
SORT_STRATEGIES = {
    "numeric_suffix": _numeric_suffix_key,
    "alphabetical": _alphabetical_key,
}


def get_sort_key(strategy_name):
    """Función de orden para un nombre de estrategia (config.LOG_SORT_STRATEGY).
    Si el nombre no está registrado, cae de vuelta a 'alphabetical' (segura,
    siempre aplicable, no depende de ninguna convención de nombres)."""
    return SORT_STRATEGIES.get(strategy_name, _alphabetical_key)
