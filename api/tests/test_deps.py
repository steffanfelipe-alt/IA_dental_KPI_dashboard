"""
test_deps.py

Unit tests de las dos dependencias de seguridad de `api/deps.py`,
llamadas directamente como funciones Python (no vía FastAPI/TestClient
— eso lo cubren `test_auth_router.py`/`test_clinicas_router.py`), con
fakes mínimos sin red:

  obtener_usuario_actual — fake del cliente Supabase anon exponiendo
                            sólo `.auth.get_user(token)`, igual que el
                            fake `.table()` de
                            `parser/persistencia/test_adaptador_supabase.py`
                            pero para el lado de auth.
  owner_de_clinica       — fake mínimo de `PuertoRepositorioClinicas`
                            (sólo `obtener_owner_id`, que es lo único
                            que esta dependencia llama).
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from api.deps import UsuarioActual, obtener_usuario_actual, owner_de_clinica


class _ClienteAnonFalso:
    """Fake mínimo del cliente Supabase anon: sólo `.auth.get_user`,
    que es lo único que `obtener_usuario_actual` llama."""

    def __init__(self, usuario=None, lanzar=False):
        self._usuario = usuario
        self._lanzar = lanzar
        self.auth = SimpleNamespace(get_user=self._get_user)

    def _get_user(self, token):
        if self._lanzar:
            raise RuntimeError("token inválido o expirado")
        return SimpleNamespace(user=self._usuario)


def _credenciales(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


# --- obtener_usuario_actual / CurrentUserDep ---------------------------


def test_obtener_usuario_actual_sin_token_devuelve_401():
    with pytest.raises(HTTPException) as excinfo:
        obtener_usuario_actual(None, _ClienteAnonFalso())

    assert excinfo.value.status_code == 401


def test_obtener_usuario_actual_con_token_invalido_devuelve_401():
    cliente_anon = _ClienteAnonFalso(lanzar=True)

    with pytest.raises(HTTPException) as excinfo:
        obtener_usuario_actual(_credenciales("token-malo"), cliente_anon)

    assert excinfo.value.status_code == 401


def test_obtener_usuario_actual_sin_usuario_en_la_respuesta_devuelve_401():
    cliente_anon = _ClienteAnonFalso(usuario=None)

    with pytest.raises(HTTPException) as excinfo:
        obtener_usuario_actual(_credenciales("token-expirado"), cliente_anon)

    assert excinfo.value.status_code == 401


def test_obtener_usuario_actual_con_token_valido_devuelve_usuario_actual():
    usuario_supabase = SimpleNamespace(id="user-1", email="clinica@ejemplo.com")
    cliente_anon = _ClienteAnonFalso(usuario=usuario_supabase)

    usuario_actual = obtener_usuario_actual(_credenciales("token-bueno"), cliente_anon)

    assert usuario_actual == UsuarioActual(id="user-1", email="clinica@ejemplo.com")


# --- owner_de_clinica / OwnerDeClinicaDep -------------------------------


class _RepoFalso:
    """Fake mínimo de `PuertoRepositorioClinicas`: sólo
    `obtener_owner_id`, que es lo único que `owner_de_clinica` llama."""

    def __init__(self, owners_por_clinica: dict[str, str]):
        self._owners_por_clinica = owners_por_clinica

    def obtener_owner_id(self, clinica_id: str):
        return self._owners_por_clinica.get(clinica_id)


def test_owner_de_clinica_con_owner_que_matchea_devuelve_clinica_id():
    repo = _RepoFalso({"clinica-1": "user-1"})
    usuario_actual = UsuarioActual(id="user-1")

    resultado = owner_de_clinica("clinica-1", usuario_actual, repo)

    assert resultado == "clinica-1"


def test_owner_de_clinica_con_owner_que_no_matchea_devuelve_403():
    repo = _RepoFalso({"clinica-1": "user-1"})
    usuario_actual = UsuarioActual(id="user-2")

    with pytest.raises(HTTPException) as excinfo:
        owner_de_clinica("clinica-1", usuario_actual, repo)

    assert excinfo.value.status_code == 403


def test_owner_de_clinica_inexistente_devuelve_404():
    repo = _RepoFalso({})
    usuario_actual = UsuarioActual(id="user-1")

    with pytest.raises(HTTPException) as excinfo:
        owner_de_clinica("clinica-inexistente", usuario_actual, repo)

    assert excinfo.value.status_code == 404
