"""
test_clinicas_router.py

`POST /clinicas` vía `TestClient`, overrideando `CurrentUserDep`
(`api.deps.obtener_usuario_actual`) y `RepositorioDep`
(`api.deps.obtener_repositorio`) con fakes — confirma que `owner_id`
en la respuesta y en la llamada al repositorio sale siempre del usuario
autenticado, nunca del body de la request.
"""

import pytest
from fastapi.testclient import TestClient

from api.config import obtener_cliente_supabase_anon
from api.deps import UsuarioActual, obtener_repositorio, obtener_usuario_actual
from api.main import app


class _RepoFalso:
    def __init__(self):
        self.llamadas_crear_clinica: list[tuple[str, str]] = []

    def crear_clinica(self, nombre: str, owner_id: str) -> str:
        self.llamadas_crear_clinica.append((nombre, owner_id))
        return "clinica-generada-1"


@pytest.fixture()
def repo_falso():
    return _RepoFalso()


@pytest.fixture()
def cliente(repo_falso):
    usuario_actual = UsuarioActual(id="user-autenticado-1", email="owner@clinica.com")
    app.dependency_overrides[obtener_usuario_actual] = lambda: usuario_actual
    app.dependency_overrides[obtener_repositorio] = lambda: repo_falso
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_crear_clinica_setea_owner_id_del_usuario_autenticado(cliente, repo_falso):
    respuesta = cliente.post("/clinicas", json={"nombre": "Clínica Sonrisas"})

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["nombre"] == "Clínica Sonrisas"
    assert cuerpo["owner_id"] == "user-autenticado-1"
    assert repo_falso.llamadas_crear_clinica == [("Clínica Sonrisas", "user-autenticado-1")]


def test_crear_clinica_ignora_owner_id_si_viniera_en_el_body(cliente, repo_falso):
    # CrearClinicaRequest sólo declara `nombre`: un `owner_id` en el body
    # es un campo extra que Pydantic ignora por default, nunca se usa.
    respuesta = cliente.post(
        "/clinicas",
        json={"nombre": "Clínica Sonrisas", "owner_id": "owner-que-no-deberia-usarse"},
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["owner_id"] == "user-autenticado-1"


def test_crear_clinica_sin_usuario_autenticado_devuelve_401():
    # No overrideamos `obtener_usuario_actual`: corre la dependencia real,
    # que devuelve 401 antes de ejecutar el body de la ruta porque no
    # mandamos header `Authorization`. Sólo overrideamos el cliente anon
    # (dependencia hermana que FastAPI igual resuelve) para no requerir
    # SUPABASE_URL/SUPABASE_ANON_KEY reales en este entorno de tests.
    app.dependency_overrides.clear()
    app.dependency_overrides[obtener_cliente_supabase_anon] = lambda: object()
    try:
        cliente_sin_token = TestClient(app)
        respuesta = cliente_sin_token.post("/clinicas", json={"nombre": "Clínica Sonrisas"})
    finally:
        app.dependency_overrides.clear()

    assert respuesta.status_code == 401
