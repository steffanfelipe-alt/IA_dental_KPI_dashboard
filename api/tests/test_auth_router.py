"""
test_auth_router.py

`POST /auth/signup` y `POST /auth/login` vía `TestClient`, con
`ClienteAnonDep` (`api.config.obtener_cliente_supabase_anon`)
overrideado por un fake en memoria de `.auth.sign_up`/
`.auth.sign_in_with_password` — nunca toca Supabase real.
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api.config import obtener_cliente_supabase_anon
from api.main import app


class _ClienteAnonFalso:
    """Fake en memoria de Supabase Auth: `sign_up` rechaza emails ya
    registrados (como Supabase), `sign_in_with_password` sólo acepta la
    contraseña con la que se registró el email."""

    def __init__(self):
        self._passwords_por_email: dict[str, str] = {}

    def _sesion_falsa(self):
        return SimpleNamespace(access_token="access-token-falso", refresh_token="refresh-token-falso")

    @property
    def auth(self):
        return SimpleNamespace(sign_up=self.sign_up, sign_in_with_password=self.sign_in_with_password)

    def sign_up(self, credenciales: dict):
        email = credenciales["email"]
        if email in self._passwords_por_email:
            raise RuntimeError("email ya registrado")
        self._passwords_por_email[email] = credenciales["password"]
        usuario = SimpleNamespace(id=f"user-{email}", email=email)
        return SimpleNamespace(user=usuario, session=self._sesion_falsa())

    def sign_in_with_password(self, credenciales: dict):
        email = credenciales["email"]
        password = credenciales["password"]
        if self._passwords_por_email.get(email) != password:
            raise RuntimeError("credenciales inválidas")
        usuario = SimpleNamespace(id=f"user-{email}", email=email)
        return SimpleNamespace(user=usuario, session=self._sesion_falsa())


@pytest.fixture()
def cliente_anon_falso():
    fake = _ClienteAnonFalso()
    app.dependency_overrides[obtener_cliente_supabase_anon] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


@pytest.fixture()
def cliente():
    return TestClient(app)


# --- signup --------------------------------------------------------------


def test_signup_exitoso_devuelve_201_con_tokens_y_sin_service_role_key(cliente, cliente_anon_falso):
    respuesta = cliente.post("/auth/signup", json={"email": "nueva@clinica.com", "password": "secreto123"})

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["email"] == "nueva@clinica.com"
    assert cuerpo["access_token"] == "access-token-falso"
    assert cuerpo["refresh_token"] == "refresh-token-falso"
    assert "service_role" not in respuesta.text


def test_signup_con_email_duplicado_devuelve_error_sin_crear_usuario(cliente, cliente_anon_falso):
    primera = cliente.post("/auth/signup", json={"email": "repetida@clinica.com", "password": "secreto123"})
    assert primera.status_code == 201

    segunda = cliente.post("/auth/signup", json={"email": "repetida@clinica.com", "password": "otraClave1"})

    assert segunda.status_code == 409
    assert len(cliente_anon_falso._passwords_por_email) == 1


# --- login -----------------------------------------------------------------


def test_login_exitoso_devuelve_tokens(cliente, cliente_anon_falso):
    cliente.post("/auth/signup", json={"email": "clinica@ejemplo.com", "password": "secreto123"})

    respuesta = cliente.post("/auth/login", json={"email": "clinica@ejemplo.com", "password": "secreto123"})

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["access_token"] == "access-token-falso"
    assert cuerpo["refresh_token"] == "refresh-token-falso"
    assert "service_role" not in respuesta.text


def test_login_con_credenciales_invalidas_devuelve_401_sin_tokens(cliente, cliente_anon_falso):
    cliente.post("/auth/signup", json={"email": "clinica@ejemplo.com", "password": "secreto123"})

    respuesta = cliente.post("/auth/login", json={"email": "clinica@ejemplo.com", "password": "claveIncorrecta"})

    assert respuesta.status_code == 401
    assert "access_token" not in respuesta.text
