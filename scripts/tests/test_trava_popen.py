"""A trava do Popen (conftest.py) barra qualquer processo que cite adb, inclusive quando o teste chama Popen direto
ou usa o caminho absoluto do adb.exe; comandos sem adb continuam passando."""
import subprocess

import pytest


@pytest.mark.parametrize("comando", [
    ["adb", "devices"],
    [r"C:\Users\x\platform-tools\adb.exe", "shell", "ls"],
    "adb shell ls",
])
def test_popen_de_adb_e_bloqueado(comando):
    with pytest.raises(pytest.fail.Exception):
        subprocess.Popen(comando)


def test_popen_sem_adb_continua_funcionando(tmp_path):
    import sys
    p = subprocess.Popen([sys.executable, "-c", "print(1)"], stdout=subprocess.PIPE)
    saida, _ = p.communicate()
    assert saida.strip() == b"1"