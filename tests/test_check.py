import pytest

import config
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
