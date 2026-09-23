import pytest

import config
import check
from check import CheckServer, REQUIRED_SERVER_KEYS


@pytest.fixture
def tmp_result_path(tmp_path, monkeypatch):
    """Evita que las pruebas escriban logs en la carpeta real de resultados."""
    monkeypatch.setattr(config, "RESULT_PATH", str(tmp_path))
    return tmp_path


def test_faltan_campos_requeridos(tmp_result_path):
    dat_server = {"serv_name": "SRV_TEST", "plant": "PLANT_TEST"}  # faltan varios campos

    resultado = CheckServer(dat_server)

    assert resultado["problem"] is not None
    assert "type" in resultado["problem"]
    assert resultado["cameras"] == []


def test_cam_activate_no_es_obligatorio():
    # plants_abinbev.yaml real no trae 'cam_activate' en ningun servidor;
    # no debe tratarse como campo obligatorio (antes si lo era, por error).
    assert "cam_activate" not in REQUIRED_SERVER_KEYS


def test_faltan_campos_de_addresses(tmp_result_path):
    dat_server = {
        "serv_name": "SRV_TEST", "plant": "PLANT_TEST", "cam_activate": True,
        "type": "remote", "addresses": {"local": "127.0.0.1"},  # faltan cameras/zerotier
        "proxy_port": 0, "ia_ports": [1234],
    }

    resultado = CheckServer(dat_server)

    assert resultado["problem"] is not None
    assert "addresses" in resultado["problem"]
    assert "cameras" in resultado["problem"]
    assert "zerotier" in resultado["problem"]


def test_addresses_no_es_diccionario(tmp_result_path):
    dat_server = {
        "serv_name": "SRV_TEST", "plant": "PLANT_TEST", "cam_activate": True,
        "type": "remote", "addresses": "no-es-un-diccionario",
        "proxy_port": 0, "ia_ports": [1234],
    }

    resultado = CheckServer(dat_server)

    assert resultado["problem"] is not None
    assert resultado["cameras"] == []


def test_falla_yaml_en_servidor_con_tuneles_cierra_ambos_y_marca_problema(tmp_result_path, monkeypatch):
    # Bug real en producción: si el YAML fallaba, el túnel IA nunca se
    # cerraba (quedaba anidado dentro del "if status_code == 400") y el
    # servidor quedaba marcado como problem=None (se veía como [OK] 0/0 en
    # el resumen) — atascando el puerto compartido para todos los
    # servidores siguientes de la corrida.
    dat_server = {
        "serv_name": "SRV_TEST", "plant": "PLANT_TEST", "cam_activate": False,
        "type": "tunnels",
        "addresses": {"local": "10.0.0.1", "cameras": "10.0.0.2", "zerotier": "10.0.0.3"},
        "proxy_port": 38533, "ia_ports": [8045],
    }

    monkeypatch.setattr(check, "ping", lambda ip, plant, serv, **k: 800)
    monkeypatch.setattr(check, "name_host", lambda: "OTRA-MAQUINA")
    monkeypatch.setattr(check, "create_tunnel", lambda *a, **k: True)
    monkeypatch.setattr(check, "read_yaml", lambda url, plant, serv: (410, {}))

    tuneles_cerrados = []
    monkeypatch.setattr(check, "close_tunnel", lambda loc_port, px, plant, serv, **k: tuneles_cerrados.append(loc_port))

    resultado = CheckServer(dat_server)

    assert config.IA_LOC_PORT in tuneles_cerrados
    assert config.PX_LOC_PORT in tuneles_cerrados
    assert resultado["problem"] is not None
    assert resultado["problem_type"] == "sin_yaml"
    assert resultado["cameras"] == []
