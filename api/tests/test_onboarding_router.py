"""
test_onboarding_router.py

Las 5 rutas de `api/routers/onboarding.py` vía `TestClient`, overrideando
`obtener_usuario_actual`/`obtener_repositorio` (mismo patrón que
`test_clinicas_router.py`) y monkeypatcheando `procesar_migracion`/
`resolver_conflicto`/`escribir_temporales` directo en el módulo del
router (`api.routers.onboarding.*`) — este router los llama como
funciones de dominio, no vía `Depends`, así que un
`app.dependency_overrides` no los alcanza. Nunca se invoca el pipeline
real (que necesitaría archivos reales + credenciales de Vision/LLM);
sólo se prueba que el router arma los argumentos correctos y hace lo
que corresponde con el resultado.
"""

from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from api.deps import UsuarioActual, obtener_repositorio, obtener_usuario_actual
from api.main import app
from api.routers import onboarding
from parser.diagnostico.guia_diagnostico import PreguntaGuia


class _RepoFalso:
    """Fake mínimo de `PuertoRepositorioClinicas`: sólo los métodos que
    este router llama (más `obtener_owner_id`, que llama `owner_de_clinica`)."""

    def __init__(self, owner_id: str = "user-1"):
        self._owner_id = owner_id
        self.variables: dict = {}
        self.respuestas: dict[str, str] = {}
        self.migracion_completada = False
        self.llamadas_guardar_variables: list[dict] = []
        self.llamadas_marcar_completada = 0

    def obtener_owner_id(self, clinica_id: str):
        return self._owner_id

    def cargar_variables(self, clinica_id: str) -> dict:
        return self.variables

    def guardar_variables(self, clinica_id: str, variables: dict) -> None:
        self.llamadas_guardar_variables.append(variables)
        self.variables = variables

    def cargar_respuestas_diagnostico(self, clinica_id: str) -> dict[str, str]:
        return self.respuestas

    def guardar_respuestas_diagnostico(self, clinica_id: str, respuestas: dict[str, str]) -> None:
        self.respuestas.update(respuestas)

    def marcar_migracion_completada(self, clinica_id: str) -> None:
        self.llamadas_marcar_completada += 1
        self.migracion_completada = True

    def esta_migracion_completada(self, clinica_id: str) -> bool:
        return self.migracion_completada


@pytest.fixture()
def repo_falso():
    return _RepoFalso()


@pytest.fixture()
def cliente(repo_falso):
    usuario_actual = UsuarioActual(id="user-1", email="owner@clinica.com")
    app.dependency_overrides[obtener_usuario_actual] = lambda: usuario_actual
    app.dependency_overrides[obtener_repositorio] = lambda: repo_falso
    yield TestClient(app)
    app.dependency_overrides.clear()


# --- POST /migrar --------------------------------------------------------


def test_migrar_archivo_valido_procesa_guarda_y_marca_completada(cliente, repo_falso, monkeypatch):
    resultado_falso = {
        "variables": {"turnos_mensuales": {"valor": 120, "fuente": "migracion_excel", "confianza": 1.0}},
        "archivos_fallidos": [],
        "kpis_calculados": {},
    }
    llamadas_procesar_migracion = []

    def _procesar_migracion_falso(archivos, variables_previas=None, **kwargs):
        llamadas_procesar_migracion.append((archivos, variables_previas))
        return resultado_falso

    @contextmanager
    def _escribir_temporales_falso(archivos_subidos):
        yield [f"/tmp/fake/{a.name}" for a in archivos_subidos]

    monkeypatch.setattr(onboarding, "procesar_migracion", _procesar_migracion_falso)
    monkeypatch.setattr(onboarding, "escribir_temporales", _escribir_temporales_falso)

    respuesta = cliente.post(
        "/onboarding/clinica-1/migrar",
        files=[("archivos", ("planilla.xlsx", b"contenido de prueba", "application/vnd.ms-excel"))],
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == resultado_falso
    assert len(llamadas_procesar_migracion) == 1
    assert repo_falso.llamadas_guardar_variables == [resultado_falso["variables"]]
    assert repo_falso.llamadas_marcar_completada == 1
    assert repo_falso.migracion_completada is True


def test_migrar_archivo_demasiado_grande_devuelve_413_sin_procesar(cliente, monkeypatch):
    monkeypatch.setattr(onboarding, "TAMANO_MAXIMO_ARCHIVO_BYTES", 5)
    llamado = {"veces": 0}

    def _procesar_migracion_no_deberia_llamarse(*args, **kwargs):
        llamado["veces"] += 1
        raise AssertionError("procesar_migracion no debería llamarse con un archivo oversized")

    monkeypatch.setattr(onboarding, "procesar_migracion", _procesar_migracion_no_deberia_llamarse)

    respuesta = cliente.post(
        "/onboarding/clinica-1/migrar",
        files=[("archivos", ("planilla.xlsx", b"contenido bastante mas largo que 5 bytes", "application/vnd.ms-excel"))],
    )

    assert respuesta.status_code == 413
    assert llamado["veces"] == 0


def test_migrar_extension_no_soportada_devuelve_415_sin_procesar(cliente, monkeypatch):
    llamado = {"veces": 0}

    def _procesar_migracion_no_deberia_llamarse(*args, **kwargs):
        llamado["veces"] += 1
        raise AssertionError("procesar_migracion no debería llamarse con una extensión no soportada")

    monkeypatch.setattr(onboarding, "procesar_migracion", _procesar_migracion_no_deberia_llamarse)

    respuesta = cliente.post(
        "/onboarding/clinica-1/migrar",
        files=[("archivos", ("virus.exe", b"contenido", "application/octet-stream"))],
    )

    assert respuesta.status_code == 415
    assert llamado["veces"] == 0


# --- POST /resolver-conflicto ---------------------------------------------


def test_resolver_conflicto_arma_argumentos_y_guarda_variables(cliente, repo_falso, monkeypatch):
    repo_falso.variables = {"turnos_mensuales": {"valor": 100, "fuente": "migracion_excel", "confianza": 0.5}}
    variables_previas_esperadas = dict(repo_falso.variables)  # guardar_variables del fake pisa .variables después
    resultado_falso = {"variables": {"turnos_mensuales": {"valor": 120, "fuente": "confirmado_por_dueno"}}}
    llamadas = []

    def _resolver_conflicto_falso(**kwargs):
        llamadas.append(kwargs)
        return resultado_falso

    monkeypatch.setattr(onboarding, "resolver_conflicto", _resolver_conflicto_falso)

    respuesta = cliente.post(
        "/onboarding/clinica-1/resolver-conflicto",
        json={"variable": "turnos_mensuales", "valor_manual": 120},
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == resultado_falso
    assert len(llamadas) == 1
    assert llamadas[0]["variable"] == "turnos_mensuales"
    assert llamadas[0]["valor_manual"] == 120
    assert llamadas[0]["variables_previas"] == variables_previas_esperadas
    assert repo_falso.llamadas_guardar_variables == [resultado_falso["variables"]]


# --- GET /guia + PUT /respuestas -------------------------------------------


_PREGUNTAS_FALSAS = {
    "P1": PreguntaGuia(id="P1", texto="¿Pregunta uno?", bloque=1, nombre_bloque="Bloque 1", nucleo=True, requerida_diagnostico=True),
}

# P3 es una pregunta REAL de PREGUNTAS_WIZARD (no monkeypatcheada): la
# respaldan turnos_agendados/turnos_asistidos/no_shows/turnos_cancelados.
# P1 no tiene ninguna variable de wizard mapeada -- sirve para probar que
# una pregunta puramente cualitativa nunca se excluye por cobertura.
_PREGUNTAS_CON_P3 = {
    **_PREGUNTAS_FALSAS,
    "P3": PreguntaGuia(
        id="P3",
        texto="¿Cuántos turnos agendan, asisten y cuántos son no-show/cancelación?",
        bloque=1,
        nombre_bloque="Bloque 1",
        nucleo=True,
        requerida_diagnostico=True,
    ),
}

_VARIABLES_P3_COMPLETAS = {
    "turnos_agendados": {"valor": 40, "fuente": "migracion_excel"},
    "turnos_asistidos": {"valor": 35, "fuente": "migracion_excel"},
    "no_shows": {"valor": 3, "fuente": "migracion_excel"},
    "turnos_cancelados": {"valor": 2, "fuente": "migracion_excel"},
}


def test_guia_y_respuestas_hacen_roundtrip(cliente, repo_falso, monkeypatch):
    monkeypatch.setattr(onboarding, "PREGUNTAS_REQUERIDAS_ONBOARDING", _PREGUNTAS_FALSAS)

    respuesta_inicial = cliente.get("/onboarding/clinica-1/guia")
    assert respuesta_inicial.status_code == 200
    preguntas = respuesta_inicial.json()["preguntas"]
    assert len(preguntas) == 1
    assert preguntas[0]["id"] == "P1"
    assert preguntas[0]["respuesta"] is None

    respuesta_put = cliente.put(
        "/onboarding/clinica-1/respuestas",
        json={"respuestas": {"P1": "Se agenda a mano en una libreta."}},
    )
    assert respuesta_put.status_code == 204
    assert repo_falso.respuestas == {"P1": "Se agenda a mano en una libreta."}

    respuesta_final = cliente.get("/onboarding/clinica-1/guia")
    assert respuesta_final.json()["preguntas"][0]["respuesta"] == "Se agenda a mano en una libreta."


# --- GET /guia — filtro de cobertura (change veredicto-wizard-usability-fixes) ---


def test_guia_omite_pregunta_totalmente_cubierta_por_variables_persistidas(cliente, repo_falso, monkeypatch):
    monkeypatch.setattr(onboarding, "PREGUNTAS_REQUERIDAS_ONBOARDING", _PREGUNTAS_CON_P3)
    repo_falso.variables = dict(_VARIABLES_P3_COMPLETAS)

    respuesta = cliente.get("/onboarding/clinica-1/guia")

    ids = [p["id"] for p in respuesta.json()["preguntas"]]
    assert "P3" not in ids
    assert "P1" in ids  # sin mapeo de wizard, P1 siempre se pregunta


def test_guia_mantiene_pregunta_parcialmente_cubierta_con_texto_sin_modificar(cliente, repo_falso, monkeypatch):
    monkeypatch.setattr(onboarding, "PREGUNTAS_REQUERIDAS_ONBOARDING", _PREGUNTAS_CON_P3)
    repo_falso.variables = {
        "turnos_agendados": {"valor": 40, "fuente": "migracion_excel"},
        "turnos_asistidos": {"valor": 35, "fuente": "migracion_excel"},
        "turnos_cancelados": {"valor": 2, "fuente": "migracion_excel"},
        # no_shows falta -> P3 sigue pendiente
    }

    respuesta = cliente.get("/onboarding/clinica-1/guia")

    preguntas = {p["id"]: p for p in respuesta.json()["preguntas"]}
    assert "P3" in preguntas
    assert preguntas["P3"]["texto"] == _PREGUNTAS_CON_P3["P3"].texto


# --- GET /estado ------------------------------------------------------------


def test_estado_incompleto_por_respuestas_faltantes(cliente, repo_falso, monkeypatch):
    monkeypatch.setattr(onboarding, "PREGUNTAS_REQUERIDAS_ONBOARDING", _PREGUNTAS_FALSAS)
    repo_falso.migracion_completada = True  # migración OK, pero falta la respuesta a P1

    respuesta = cliente.get("/onboarding/clinica-1/estado")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["completo"] is False
    assert cuerpo["migracion_completada"] is True
    assert cuerpo["preguntas_faltantes"] == ["P1"]


def test_estado_incompleto_por_migracion_no_procesada(cliente, repo_falso, monkeypatch):
    monkeypatch.setattr(onboarding, "PREGUNTAS_REQUERIDAS_ONBOARDING", _PREGUNTAS_FALSAS)
    repo_falso.respuestas = {"P1": "ya contestada"}  # respuestas OK, pero nunca se subió/procesó un archivo

    respuesta = cliente.get("/onboarding/clinica-1/estado")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["completo"] is False
    assert cuerpo["migracion_completada"] is False
    assert cuerpo["preguntas_faltantes"] == []


def test_estado_completo_cuando_migracion_y_respuestas_estan_ok(cliente, repo_falso, monkeypatch):
    monkeypatch.setattr(onboarding, "PREGUNTAS_REQUERIDAS_ONBOARDING", _PREGUNTAS_FALSAS)
    repo_falso.migracion_completada = True
    repo_falso.respuestas = {"P1": "ya contestada"}

    respuesta = cliente.get("/onboarding/clinica-1/estado")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["completo"] is True
    assert cuerpo["migracion_completada"] is True
    assert cuerpo["preguntas_faltantes"] == []


def test_estado_completo_cuando_variables_persistidas_cubren_pregunta_nucleo_sin_respuesta(
    cliente, repo_falso, monkeypatch
):
    # Change veredicto-wizard-usability-fixes: P3 nunca se contesta a mano
    # en la Guía (no hay entrada en `respuestas`) pero las 4 variables que
    # lo respaldan ya están persistidas -- /estado debe llegar a
    # completo=true igual que /guia deja de pedirlo.
    monkeypatch.setattr(onboarding, "PREGUNTAS_REQUERIDAS_ONBOARDING", _PREGUNTAS_CON_P3)
    repo_falso.migracion_completada = True
    repo_falso.respuestas = {"P1": "ya contestada"}
    repo_falso.variables = dict(_VARIABLES_P3_COMPLETAS)

    respuesta = cliente.get("/onboarding/clinica-1/estado")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["completo"] is True
    assert "P3" not in cuerpo["preguntas_faltantes"]
