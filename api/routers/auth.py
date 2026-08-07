"""
routers/auth.py

`POST /auth/signup`, `POST /auth/login` y `POST /auth/refresh`: delegan
la creación de usuario y la autenticación enteramente a Supabase Auth
vía el cliente anon-key (`ClienteAnonDep`) — este router no guarda ni
valida contraseñas, no conoce el service_role key, y nunca lo devuelve
en la respuesta (spec: "the service_role key is never present in the
response" — trivialmente cierto acá porque este router ni siquiera tiene
acceso a él).

`refresh` existe porque `SessionResponse` ya devuelve `refresh_token`
desde signup/login, pero sin este endpoint era un dato muerto que el
cliente recibía y no podía usar para nada — el punto entero de un
refresh token es no tener que volver a pedirle la contraseña al usuario
cuando el access_token corto expira.

Rutas `def` síncronas: el SDK `supabase-py` es sync (usa `httpx` sync por
debajo), así que no hay nada async real que awaitear; FastAPI las corre
en threadpool.
"""

from fastapi import APIRouter, HTTPException, status

from api.deps import ClienteAnonDep
from api.schemas.auth import LoginRequest, RefreshRequest, SessionResponse, SignupRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(datos: SignupRequest, cliente_anon: ClienteAnonDep) -> SessionResponse:
    try:
        respuesta = cliente_anon.auth.sign_up({"email": datos.email, "password": datos.password})
    except Exception as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "No se pudo crear el usuario (¿el email ya está registrado?)."
        ) from error

    usuario = getattr(respuesta, "user", None)
    if usuario is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "No se pudo crear el usuario (¿el email ya está registrado?)."
        )

    sesion = getattr(respuesta, "session", None)
    return SessionResponse(
        user_id=usuario.id,
        email=getattr(usuario, "email", None),
        access_token=getattr(sesion, "access_token", None) if sesion else None,
        refresh_token=getattr(sesion, "refresh_token", None) if sesion else None,
    )


@router.post("/login")
def login(datos: LoginRequest, cliente_anon: ClienteAnonDep) -> SessionResponse:
    try:
        respuesta = cliente_anon.auth.sign_in_with_password({"email": datos.email, "password": datos.password})
    except Exception as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas.") from error

    usuario = getattr(respuesta, "user", None)
    sesion = getattr(respuesta, "session", None)
    if usuario is None or sesion is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas.")

    return SessionResponse(
        user_id=usuario.id,
        email=getattr(usuario, "email", None),
        access_token=sesion.access_token,
        refresh_token=sesion.refresh_token,
    )


@router.post("/refresh")
def refresh(datos: RefreshRequest, cliente_anon: ClienteAnonDep) -> SessionResponse:
    try:
        respuesta = cliente_anon.auth.refresh_session(datos.refresh_token)
    except Exception as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas.") from error

    usuario = getattr(respuesta, "user", None)
    sesion = getattr(respuesta, "session", None)
    if usuario is None or sesion is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas.")

    return SessionResponse(
        user_id=usuario.id,
        email=getattr(usuario, "email", None),
        access_token=sesion.access_token,
        refresh_token=sesion.refresh_token,
    )
