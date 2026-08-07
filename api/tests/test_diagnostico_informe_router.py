"""
test_diagnostico_informe_router.py

Las 3 rutas de diagnóstico/informe de `api/routers/clinicas.py`, vía
`TestClient`, overrideando `obtener_usuario_actual`/`obtener_repositorio`
(mismo patrón que `test_onboarding_router.py`) y monkeypatcheando
`procesar_migracion`/`interpretar_clinica` directo en el módulo del
router (`api.routers.clinicas.*`) — igual criterio que
`onboarding.py`: son funciones de dominio, no infraestructura
inyectable, así que un `app.dependency_overrides` no las alcanza.

`ClienteAnthropicDep` (`api.config.obtener_cliente_anthropic`) SIEMPRE
se overridea con un objeto fake, incluso en los tests que nunca llegan
a usarlo (ej. el 409 de `POST /informe` con onboarding incompleto):
FastAPI resuelve TODAS las dependencias declaradas de una ruta antes de
ejecutar su cuerpo, así que sin este override cualquier test que pegue
a `POST /informe` revienta con el `RuntimeError` fail-closed de
`obtener_cliente_anthropic` (falta `ANTHROPIC_API_KEY`) en vez de
llegar al comportamiento que el test quiere probar — mismo gotcha ya
documentado para `ClienteAnonDep` en `test_clinicas_router.py`/PR2.

Nunca se invoca el pipeline real ni la API de Anthropic real.
"""

import pytest
from fastapi.testclient import TestClient

from api.config import obtener_cliente_anthropic
from api.deps import UsuarioActual, obtener_repositorio, obtener_usuario_actual
from api.main import app
from api.routers import clinicas
from parser.diagnostico.guia_diagnostico import PreguntaGuia


class _RepoFalso:
    """Fake mínimo de `PuertoRepositorioClinicas`: sólo los métodos que
    este router llama (más `obtener_owner_id`, que llama `owner_de_clinica`)."""

    def __init__(self, owner_id: str = "user-1"):
        self._owner_id = owner_id
        self.migracion_completada = False
        self.respuestas: dict[str, str] = {}
        self.variables: dict = {}
        self.informe: str | None = None
        self.llamadas_guardar_informe: list[str] = []

    def obtener_owner_id(self, clinica_id: str):
        return self._owner_id

    def esta_migracion_completada(self, clinica_id: str) -> bool:
        return self.migracion_completada

    def cargar_respuestas_diagnostico(self, clinica_id: str) -> dict[str, str]:
        return self.respuestas

    def cargar_variables(self, clinica_id: str) -> dict:
        return self.variables

    def cargar_informe(self, clinica_id: str):
        return self.informe

    def guardar_informe(self, clinica_id: str, texto: str) -> None:
        self.llamadas_guardar_informe.append(texto)
        self.informe = texto


_PREGUNTAS_FALSAS = {
    "P1": PreguntaGuia(id="P1", texto="¿Pregunta uno?", bloque=1, nombre_bloque="Bloque 1", nucleo=True, requerida_diagnostico=True),
}


@pytest.fixture()
def repo_falso():
    return _RepoFalso()


@pytest.fixture()
def cliente(repo_falso, monkeypatch):
    monkeypatch.setattr(clinicas, "PREGUNTAS_REQUERIDAS_ONBOARDING", _PREGUNTAS_FALSAS)
    usuario_actual = UsuarioActual(id="user-1", email="owner@clinica.com")
    app.dependency_overrides[obtener_usuario_actual] = lambda: usuario_actual
    app.dependency_overrides[obtener_repositorio] = lambda: repo_falso
    app.dependency_overrides[obtener_cliente_anthropic] = lambda: object()
    yield TestClient(app)
    app.dependency_overrides.clear()


def _completar_onboarding(repo: _RepoFalso) -> None:
    repo.migracion_completada = True
    repo.respuestas = {"P1": "ya contestada"}


# --- GET /diagnostico -------------------------------------------------------


def test_diagnostico_onboarding_incompleto_devuelve_409_sin_procesar(cliente, repo_falso, monkeypatch):
    llamado = {"veces": 0}

    def _procesar_migracion_no_deberia_llamarse(*args, **kwargs):
        llamado["veces"] += 1
        raise AssertionError("procesar_migracion no debería llamarse con onboarding incompleto")

    monkeypatch.setattr(clinicas, "procesar_migracion", _procesar_migracion_no_deberia_llamarse)

    respuesta = cliente.get("/clinicas/clinica-1/diagnostico")

    assert respuesta.status_code == 409
    assert llamado["veces"] == 0


def test_diagnostico_onboarding_completo_recomputa_deterministicamente(cliente, repo_falso, monkeypatch):
    _completar_onboarding(repo_falso)
    repo_falso.variables = {"turnos_mensuales": {"valor": 120}}
    diagnostico_falso = [{"kpi_id": 3, "problema": "algo", "estado": "PROBLEM"}]
    llamadas = []

    def _procesar_migracion_falso(archivos, variables_previas=None, respuestas_diagnostico=None, **kwargs):
        llamadas.append({"archivos": archivos, "variables_previas": variables_previas, "respuestas_diagnostico": respuestas_diagnostico})
        return {"diagnostico": diagnostico_falso}

    monkeypatch.setattr(clinicas, "procesar_migracion", _procesar_migracion_falso)

    respuesta = cliente.get("/clinicas/clinica-1/diagnostico")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"diagnostico": diagnostico_falso}
    assert len(llamadas) == 1
    # archivos=[] fuerza el recompute determinista, sin volver a leer archivos.
    assert llamadas[0]["archivos"] == []
    assert llamadas[0]["variables_previas"] == repo_falso.variables
    assert llamadas[0]["respuestas_diagnostico"] == repo_falso.respuestas


# --- POST /informe -----------------------------------------------------------


def test_informe_onboarding_incompleto_devuelve_409_sin_llamar_llm(cliente, repo_falso, monkeypatch):
    llamado = {"veces": 0}

    def _interpretar_clinica_no_deberia_llamarse(*args, **kwargs):
        llamado["veces"] += 1
        raise AssertionError("interpretar_clinica no debería llamarse con onboarding incompleto")

    monkeypatch.setattr(clinicas, "interpretar_clinica", _interpretar_clinica_no_deberia_llamarse)

    respuesta = cliente.post("/clinicas/clinica-1/informe")

    assert respuesta.status_code == 409
    assert llamado["veces"] == 0


def test_informe_primera_generacion_llama_llm_una_vez_y_persiste(cliente, repo_falso, monkeypatch):
    _completar_onboarding(repo_falso)
    resultado_falso = {
        "diagnostico": [{"kpi_id": 3}],
        "oportunidades_priorizadas": [],
        "calidad_datos": None,
        "variables_en_cuarentena": {},
        "discrepancias_reconciliacion": [],
        "variables_derivadas": [],
        "conflictos_pendientes": [],
    }
    llamadas_interpretar = []

    monkeypatch.setattr(clinicas, "procesar_migracion", lambda **kwargs: resultado_falso)

    def _interpretar_clinica_falso(**kwargs):
        llamadas_interpretar.append(kwargs)
        return {"informe": "texto del informe generado"}

    monkeypatch.setattr(clinicas, "interpretar_clinica", _interpretar_clinica_falso)

    respuesta = cliente.post("/clinicas/clinica-1/informe")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"texto": "texto del informe generado"}
    assert len(llamadas_interpretar) == 1
    assert llamadas_interpretar[0]["diagnosticos"] == resultado_falso["diagnostico"]
    assert repo_falso.llamadas_guardar_informe == ["texto del informe generado"]
    assert repo_falso.informe == "texto del informe generado"


def test_informe_repeat_request_no_llama_llm_de_nuevo(cliente, repo_falso, monkeypatch):
    _completar_onboarding(repo_falso)
    repo_falso.informe = "informe ya generado antes"
    llamado = {"veces": 0}

    def _procesar_migracion_no_deberia_llamarse(*args, **kwargs):
        llamado["veces"] += 1
        raise AssertionError("procesar_migracion no debería correr si ya hay informe")

    def _interpretar_clinica_no_deberia_llamarse(*args, **kwargs):
        llamado["veces"] += 1
        raise AssertionError("interpretar_clinica no debería llamarse dos veces (generate-once)")

    monkeypatch.setattr(clinicas, "procesar_migracion", _procesar_migracion_no_deberia_llamarse)
    monkeypatch.setattr(clinicas, "interpretar_clinica", _interpretar_clinica_no_deberia_llamarse)

    respuesta = cliente.post("/clinicas/clinica-1/informe")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"texto": "informe ya generado antes"}
    assert llamado["veces"] == 0


# --- GET /informe --------------------------------------------------------


def test_obtener_informe_404_cuando_no_se_genero_todavia(cliente, repo_falso):
    respuesta = cliente.get("/clinicas/clinica-1/informe")

    assert respuesta.status_code == 404


def test_obtener_informe_devuelve_lo_persistido(cliente, repo_falso):
    repo_falso.informe = "informe persistido"

    respuesta = cliente.get("/clinicas/clinica-1/informe")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"texto": "informe persistido"}
