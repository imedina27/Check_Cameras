import psutil
import system_processor as sp


class _FakeProcess:
    def __init__(self, cmdline):
        self._cmdline = cmdline

    def cmdline(self):
        return self._cmdline


class TestTunnelMatchesDestino:
    def test_coincide_con_el_forward_esperado(self, monkeypatch):
        cmdline = ["ssh", "-f", "-g", "-N", "-L", "9045:localhost:8045", "QLYMSPROD02"]
        monkeypatch.setattr(sp.psutil, "Process", lambda pid: _FakeProcess(cmdline))

        assert sp._tunnel_matches_destino(123, 9045, "localhost", 8045, "QLYMSPROD02") is True

    def test_no_coincide_si_es_un_tunel_de_otro_servidor(self, monkeypatch):
        # Caso real encontrado en producción: un túnel huérfano de QLYMSPROD04
        # seguía escuchando en el mismo puerto local compartido cuando se
        # intentó crear el túnel de QLYMSPROD02 — antes del fix, se confundía
        # con el túnel correcto y terminaba leyendo cámaras de otro servidor.
        cmdline = ["ssh", "-f", "-g", "-N", "-L", "9045:localhost:8045", "QLYMSPROD04"]
        monkeypatch.setattr(sp.psutil, "Process", lambda pid: _FakeProcess(cmdline))

        assert sp._tunnel_matches_destino(123, 9045, "localhost", 8045, "QLYMSPROD02") is False

    def test_no_coincide_si_el_puerto_remoto_es_distinto(self, monkeypatch):
        cmdline = ["ssh", "-f", "-g", "-N", "-L", "9045:localhost:8046", "QLYMSPROD02"]
        monkeypatch.setattr(sp.psutil, "Process", lambda pid: _FakeProcess(cmdline))

        assert sp._tunnel_matches_destino(123, 9045, "localhost", 8045, "QLYMSPROD02") is False

    def test_no_existe_el_proceso(self, monkeypatch):
        def _raise(pid):
            raise psutil.NoSuchProcess(pid)

        monkeypatch.setattr(sp.psutil, "Process", _raise)

        assert sp._tunnel_matches_destino(123, 9045, "localhost", 8045, "QLYMSPROD02") is False


class TestFindVerifiedTunnelPid:
    def test_devuelve_el_pid_si_el_tunel_es_el_esperado(self, monkeypatch):
        monkeypatch.setattr(sp, "find_tunnel_pid", lambda loc_port: 123)
        monkeypatch.setattr(sp, "_tunnel_matches_destino", lambda *a, **k: True)

        assert sp._find_verified_tunnel_pid(9045, "localhost", 8045, "QLYMSPROD02") == 123

    def test_devuelve_none_si_el_tunel_no_coincide(self, monkeypatch):
        monkeypatch.setattr(sp, "find_tunnel_pid", lambda loc_port: 123)
        monkeypatch.setattr(sp, "_tunnel_matches_destino", lambda *a, **k: False)

        assert sp._find_verified_tunnel_pid(9045, "localhost", 8045, "QLYMSPROD02") is None

    def test_devuelve_none_si_no_hay_ningun_proceso_en_el_puerto(self, monkeypatch):
        monkeypatch.setattr(sp, "find_tunnel_pid", lambda loc_port: None)

        assert sp._find_verified_tunnel_pid(9045, "localhost", 8045, "QLYMSPROD02") is None


class _FakeIterProcess:
    def __init__(self, name, cmdline):
        self.info = {"pid": 1, "name": name, "cmdline": cmdline}
        self.terminated = False

    def terminate(self):
        self.terminated = True


class TestAlternativeClose:
    # Bug real: el patron anterior (":{loc_port}") nunca coincidia con el
    # puerto LOCAL de un forward SSH real (precedido de un espacio, no de
    # ":"), asi que esta funcion nunca mataba el proceso huerfano que debia.
    def test_mata_el_proceso_que_usa_el_puerto_local(self, monkeypatch):
        proceso = _FakeIterProcess("ssh", ["ssh", "-f", "-g", "-N", "-L", "9045:localhost:8045", "QBYMSPROD08"])
        monkeypatch.setattr(sp.psutil, "process_iter", lambda attrs: [proceso])
        monkeypatch.setattr(sp.time, "sleep", lambda s: None)

        sp.alternative_close(9045)

        assert proceso.terminated is True

    def test_no_mata_un_proceso_cuyo_puerto_remoto_coincide_mas_no_el_local(self, monkeypatch):
        # El puerto 9045 aparece como destino (":9045" existe en la linea),
        # pero no es el puerto LOCAL de este forward — no debe matarse.
        proceso = _FakeIterProcess("ssh", ["ssh", "-f", "-g", "-N", "-L", "39533:localhost:9045", "OTRO-SERVIDOR"])
        monkeypatch.setattr(sp.psutil, "process_iter", lambda attrs: [proceso])
        monkeypatch.setattr(sp.time, "sleep", lambda s: None)

        sp.alternative_close(9045)

        assert proceso.terminated is False

    def test_no_mata_procesos_que_no_son_ssh(self, monkeypatch):
        proceso = _FakeIterProcess("python", ["python", "-L", "9045:localhost:8045"])
        monkeypatch.setattr(sp.psutil, "process_iter", lambda attrs: [proceso])
        monkeypatch.setattr(sp.time, "sleep", lambda s: None)

        sp.alternative_close(9045)

        assert proceso.terminated is False
