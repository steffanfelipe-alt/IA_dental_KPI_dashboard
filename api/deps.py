"""
deps.py

Las dos dependencias de seguridad que gatean toda ruta clinic-scoped, más
los providers de infraestructura (repositorio, cliente Supabase anon):

  CurrentUserDep    — exige un JWT Supabase válido (`Authorization: Bearer
                       <token>`), lo verifica contra `auth.get_user` del
                       cliente anon (revocation-aware, no valida el JWT a
                       mano — ver design) y devuelve el usuario
                       autenticado. 401 si falta o es inválido.
  OwnerDeClinicaDep — exige además que el usuario autenticado sea el
                       owner de la `clinica_id` de la ruta (guard a nivel
                       aplicación: no hay políticas de RLS todavía, así
                       que si esto no existiera cualquier usuario
                       autenticado podría leer/escribir cualquier
                       clínica). 404 si la clínica no existe, 403 si el
                       owner no matchea.

`RepositorioDep`/`ClienteAnonDep`/`ClienteAnthropicDep` son providers, no
guards: quedan acá para que los routers los puedan pedir vía `Depends`
sin conocer `AdaptadorSupabase`, `create_client` ni
`anthropic.Anthropic` directamente, y para que los tests los puedan
overridear con `app.dependency_overrides` sin tocar Supabase/Anthropic
reales.
"""

from dataclasses import dataclass
from typing import Annotated, Any, Optional

from fastapi import Depends, HTTPException, Path, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.config import obtener_cliente_anthropic, obtener_cliente_supabase_anon
from parser.persistencia.adaptador_supabase import AdaptadorSupabase
from parser.persistencia.puerto_repositorio import PuertoRepositorioClinicas

_esquema_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class UsuarioActual:
    id: str
    email: Optional[str] = None


def obtener_repositorio() -> PuertoRepositorioClinicas:
    return AdaptadorSupabase()


RepositorioDep = Annotated[PuertoRepositorioClinicas, Depends(obtener_repositorio)]

ClienteAnonDep = Annotated[Any, Depends(obtener_cliente_supabase_anon)]

ClienteAnthropicDep = Annotated[Any, Depends(obtener_cliente_anthropic)]


def obtener_usuario_actual(
    credenciales: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_esquema_bearer)],
    cliente_anon: ClienteAnonDep,
) -> UsuarioActual:
    if credenciales is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta el token de autenticación.")

    try:
        respuesta = cliente_anon.auth.get_user(credenciales.credentials)
    except Exception as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado.") from error

    usuario = getattr(respuesta, "user", None)
    if usuario is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado.")

    return UsuarioActual(id=usuario.id, email=getattr(usuario, "email", None))


CurrentUserDep = Annotated[UsuarioActual, Depends(obtener_usuario_actual)]


def owner_de_clinica(
    clinica_id: Annotated[str, Path()],
    usuario_actual: CurrentUserDep,
    repo: RepositorioDep,
) -> str:
    """Guard de ownership: devuelve `clinica_id` si el usuario autenticado
    es su owner, si no 403/404. Trust boundary temporal a nivel
    aplicación — ver nota de RLS en `adaptador_supabase.py` y en el
    design del cambio."""
    owner_id = repo.obtener_owner_id(clinica_id)
    if owner_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clínica no encontrada.")
    if owner_id != usuario_actual.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No sos el owner de esta clínica.")
    return clinica_id


OwnerDeClinicaDep = Annotated[str, Depends(owner_de_clinica)]
