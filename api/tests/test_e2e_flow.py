"""
test_e2e_flow.py

Un único test que recorre el flujo completo de onboarding sobre el
`app` compartido de `api.main`, de punta a punta a nivel HTTP:

    signup → login → crear clínica → migrar → respuestas → estado
    → diagnóstico → informe (primera generación) → informe (repeat,
    cacheado) → GET informe

A diferencia de los tests por router (`test_auth_router.py`,
`test_onboarding_router.py`, `test_diagnostico_informe_router.py`), acá
la autenticación de los pasos post-login NO se overridea con
`obtener_usuario_actual` — se usa el `access_token` real que devuelve
`POST /auth/login` como header `Authorization: Bearer`, y pasa por el
`CurrentUserDep` real (`api.deps.obtener_usuario_actual` →
`cliente_anon.auth.get_user(token)`). Sólo el cliente Supabase anon, el
repositorio y el cliente Anthropic quedan fakeados (`ClienteAnonDep`/
`RepositorioDep`/`ClienteAnthropicDep`), igual que en cada test por
router — nunca se toca Supabase/Anthropic real ni el pipeline real de
`parser/` (que necesitaría archivos reales + credenciales de Vision/LLM).

`procesar_migracion`/`escribir_temporales` se monkeypatchean en el
namespace de `api.routers.onboarding`; `procesar_migracion`/
`interpretar_clinica` en el de `api.routers.clinicas` — son dos imports
distintos del mismo nombre (`procesar_migracion`), cada uno en su propio
módulo, así que hace falta monkeypatchear los dos por separado (mismo
criterio ya documentado en `test_onboarding_router.py`/
`test_diagnostico_informe_router.py`).
"""

from contextlib import contextmanager
from types import SimpleNamespace

from fastapi.testclient import TestClient

from api.config import obtener_cliente_anthropic, obtener_cliente_supabase_anon
from api.deps import obtener_repositorio
from api.main import app
from api.routers import clinicas, onboarding
from parser.diagnostico.guia_diagnostico import PreguntaGuia

_PREGUNTAS_FALSAS = {
    "P1": PreguntaGuia(
        id="P1", texto="¿Pregunta uno?", bloque=1, nombre_bloque="Bloque 1", nucleo=True, requerida_diagnostico=True
    ),
}


class _ClienteAnonFalso:
    """Fake en memoria de Supabase Auth con soporte para `get_user`
    además de `sign_up`/`sign_in_with_password` (a diferencia del fake
    de `test_auth_router.py`, que no necesita `get_user` porque ese
    archivo nunca pega a una ruta protegida por `CurrentUserDep` con un
    token real) — acá el flujo sí necesita que
    `obtener_usuario_actual` pueda resolver el `access_token` devuelto
    por `/auth/login` de vuelta al usuario, igual que haría Supabase
    real."""

    def __init__(self):
        self._passwords_por_email: dict[str, str] = {}
        self._usuarios_por_token: dict[str, SimpleNamespace] = {}

    def _sesion_falsa(self, usuario: SimpleNamespace) -> SimpleNamespace:
        access_token = f"access-token-{usuario.email}"
        self._usuarios_por_token[access_token] = usuario
        return SimpleNamespace(access_token=access_token, refresh_token=f"refresh-token-{usuario.email}")

    @property
    def auth(self):
        return SimpleNamespace(
            sign_up=self.sign_up,
            sign_in_with_password=self.sign_in_with_password,
            get_user=self.get_user,
        )

    def sign_up(self, credenciales: dict):
        email = credenciales["email"]
        if email in self._passwords_por_email:
            raise RuntimeError("email ya registrado")
        self._passwords_por_email[email] = credenciales["password"]
        usuario = SimpleNamespace(id=f"user-{email}", email=email)
        return SimpleNamespace(user=usuario, session=self._sesion_falsa(usuario))

    def sign_in_with_password(self, credenciales: dict):
        email = credenciales["email"]
        password = credenciales["password"]
        if self._passwords_por_email.get(email) != password:
            raise RuntimeError("credenciales inválidas")
        usuario = SimpleNamespace(id=f"user-{email}", email=email)
        return SimpleNamespace(user=usuario, session=self._sesion_falsa(usuario))

    def get_user(self, token: str):
        usuario = self._usuarios_por_token.get(token)
        if usuario is None:
            raise RuntimeError("token inválido o expirado")
        return SimpleNamespace(user=usuario)


class _RepoFalso:
    """Fake de `PuertoRepositorioClinicas` para una sola clínica —
    alcanza para este flujo lineal, mismo criterio que los fakes por
    router (no es multi-tenant)."""

    def __init__(self):
        self.owner_id: str | None = None
        self.variables: dict = {}
        self.respuestas: dict[str, str] = {}
        self.migracion_completada = False
        self.informe: str | None = None
        self.llamadas_guardar_informe: list[str] = []

    def crear_clinica(self, nombre: str, owner_id: str) -> str:
        self.owner_id = owner_id
        return "clinica-e2e-1"

    def obtener_owner_id(self, clinica_id: str):
        return self.owner_id

    def cargar_variables(self, clinica_id: str) -> dict:
        return self.variables

    def guardar_variables(self, clinica_id: str, variables: dict) -> None:
        self.variables = variables

    def cargar_respuestas_diagnostico(self, clinica_id: str) -> dict[str, str]:
        return self.respuestas

    def guardar_respuestas_diagnostico(self, clinica_id: str, respuestas: dict[str, str]) -> None:
        self.respuestas.update(respuestas)

    def marcar_migracion_completada(self, clinica_id: str) -> None:
        self.migracion_completada = True

    def esta_migracion_completada(self, clinica_id: str) -> bool:
        return self.migracion_completada

    def cargar_informe(self, clinica_id: str):
        return self.informe

    def guardar_informe(self, clinica_id: str, texto: str) -> None:
        self.llamadas_guardar_informe.append(texto)
        self.informe = texto


def test_flujo_completo_signup_a_informe(monkeypatch):
    cliente_anon_falso = _ClienteAnonFalso()
    repo_falso = _RepoFalso()

    monkeypatch.setattr(onboarding, "PREGUNTAS_REQUERIDAS_ONBOARDING", _PREGUNTAS_FALSAS)
    monkeypatch.setattr(clinicas, "PREGUNTAS_REQUERIDAS_ONBOARDING", _PREGUNTAS_FALSAS)

    resultado_migracion_falso = {
        "variables": {"turnos_mensuales": {"valor": 120, "fuente": "migracion_excel", "confianza": 1.0}},
        "archivos_fallidos": [],
        "kpis_calculados": {},
    }

    def _procesar_migracion_onboarding_falso(archivos, variables_previas=None, **kwargs):
        return resultado_migracion_falso

    @contextmanager
    def _escribir_temporales_falso(archivos_subidos):
        yield [f"/tmp/fake/{archivo.name}" for archivo in archivos_subidos]

    monkeypatch.setattr(onboarding, "procesar_migracion", _procesar_migracion_onboarding_falso)
    monkeypatch.setattr(onboarding, "escribir_temporales", _escribir_temporales_falso)

    diagnostico_falso = [{"kpi_id": 3, "problema": "algo anda mal", "estado": "PROBLEM"}]
    resultado_diagnostico_falso = {
        "diagnostico": diagnostico_falso,
        "oportunidades_priorizadas": [],
        "calidad_datos": None,
        "variables_en_cuarentena": {},
        "discrepancias_reconciliacion": [],
        "variables_derivadas": [],
        "conflictos_pendientes": [],
    }

    def _procesar_migracion_clinicas_falso(archivos, variables_previas=None, respuestas_diagnostico=None, **kwargs):
        # archivos=[] confirma el recompute determinista (ver
        # `obtener_diagnostico`/`generar_informe`), nunca una migración nueva.
        assert archivos == []
        return resultado_diagnostico_falso

    monkeypatch.setattr(clinicas, "procesar_migracion", _procesar_migracion_clinicas_falso)

    llamadas_interpretar_clinica: list[dict] = []

    def _interpretar_clinica_falso(**kwargs):
        llamadas_interpretar_clinica.append(kwargs)
        return {"informe": "informe narrativo generado por el LLM falso"}

    monkeypatch.setattr(clinicas, "interpretar_clinica", _interpretar_clinica_falso)

    app.dependency_overrides[obtener_cliente_supabase_anon] = lambda: cliente_anon_falso
    app.dependency_overrides[obtener_repositorio] = lambda: repo_falso
    app.dependency_overrides[obtener_cliente_anthropic] = lambda: object()

    try:
        cliente = TestClient(app)

        # --- signup ----------------------------------------------------
        respuesta_signup = cliente.post(
            "/auth/signup", json={"email": "dueno@clinica-e2e.com", "password": "secreto123"}
        )
        assert respuesta_signup.status_code == 201

        # --- login -------------------------------------------------------
        respuesta_login = cliente.post(
            "/auth/login", json={"email": "dueno@clinica-e2e.com", "password": "secreto123"}
        )
        assert respuesta_login.status_code == 200
        access_token = respuesta_login.json()["access_token"]
        assert access_token
        headers = {"Authorization": f"Bearer {access_token}"}

        # --- crear clínica ------------------------------------------------
        respuesta_clinica = cliente.post("/clinicas", json={"nombre": "Clínica E2E"}, headers=headers)
        assert respuesta_clinica.status_code == 201
        cuerpo_clinica = respuesta_clinica.json()
        clinica_id = cuerpo_clinica["id"]
        assert cuerpo_clinica["owner_id"] == "user-dueno@clinica-e2e.com"

        # --- migrar ------------------------------------------------------
        respuesta_migrar = cliente.post(
            f"/onboarding/{clinica_id}/migrar",
            headers=headers,
            files=[("archivos", ("planilla.xlsx", b"contenido de prueba", "application/vnd.ms-excel"))],
        )
        assert respuesta_migrar.status_code == 200
        assert respuesta_migrar.json() == resultado_migracion_falso
        assert repo_falso.migracion_completada is True

        # --- respuestas ----------------------------------------------------
        respuesta_respuestas = cliente.put(
            f"/onboarding/{clinica_id}/respuestas",
            headers=headers,
            json={"respuestas": {"P1": "Se agenda a mano en una libreta."}},
        )
        assert respuesta_respuestas.status_code == 204

        # --- estado: ahora completo -----------------------------------------
        respuesta_estado = cliente.get(f"/onboarding/{clinica_id}/estado", headers=headers)
        assert respuesta_estado.status_code == 200
        cuerpo_estado = respuesta_estado.json()
        assert cuerpo_estado["completo"] is True
        assert cuerpo_estado["migracion_completada"] is True
        assert cuerpo_estado["preguntas_faltantes"] == []

        # --- diagnóstico: 200 ahora que el onboarding está completo -----------
        respuesta_diagnostico = cliente.get(f"/clinicas/{clinica_id}/diagnostico", headers=headers)
        assert respuesta_diagnostico.status_code == 200
        assert respuesta_diagnostico.json() == {"diagnostico": diagnostico_falso}

        # --- informe: primera generación -> llama al LLM falso una vez -------
        respuesta_informe_1 = cliente.post(f"/clinicas/{clinica_id}/informe", headers=headers)
        assert respuesta_informe_1.status_code == 200
        assert respuesta_informe_1.json() == {"texto": "informe narrativo generado por el LLM falso"}
        assert len(llamadas_interpretar_clinica) == 1

        # --- informe: segunda llamada (repeat) -> cacheado, SIN segunda llamada al LLM
        respuesta_informe_2 = cliente.post(f"/clinicas/{clinica_id}/informe", headers=headers)
        assert respuesta_informe_2.status_code == 200
        assert respuesta_informe_2.json() == {"texto": "informe narrativo generado por el LLM falso"}
        assert len(llamadas_interpretar_clinica) == 1  # sigue en 1: no se volvió a llamar

        # --- GET informe: confirma el mismo texto cacheado -------------------
        respuesta_informe_get = cliente.get(f"/clinicas/{clinica_id}/informe", headers=headers)
        assert respuesta_informe_get.status_code == 200
        assert respuesta_informe_get.json() == {"texto": "informe narrativo generado por el LLM falso"}
    finally:
        app.dependency_overrides.clear()
