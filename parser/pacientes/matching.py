"""
matching.py

Fase 2 del plan de evolución (deficiencias-parser-kpis.md, punto 3):
"record linkage" / entity resolution de pacientes. `ingreso_por_paciente`
hoy se arma con el string crudo de la columna de nombre — "Juan Pérez" y
"J. Perez" terminan siendo dos claves distintas, y el LTV real
(`ltv_real()` en metricas_paciente.py) queda silenciosamente subestimado
sin que nadie lo note. Esta misma resolución de identidad potencia además
retención, frecuencia de visitas, reactivación y ticket por cliente — no
es solo para LTV.

Motor de similitud: rapidfuzz si está instalada, fallback a difflib de la
stdlib si no. rapidfuzz importa porque resuelve apellidos compuestos
("Juan Pérez Gómez" vs "Juan Pérez" da ~0.77 con difflib —insuficiente
para fusionar solo— y 1.0 con rapidfuzz.token_set_ratio), algo común en
Argentina y que difflib solo no cierra con ningún umbral razonable.

## El hallazgo que cambió el diseño

Un solo score de similitud NO alcanza. `token_set_ratio("JUAN PEREZ",
"JUANA PEREZ")` da 95% — por encima de cualquier umbral razonable de
"fusión automática", y sin embargo son personas distintas. El problema es
estructural: un fuzzy score a nivel de string no distingue "variante del
mismo nombre" de "nombre de pila distinto que por casualidad es muy
parecido" (Juan/Juana, Marco/Marcos). La corrección: el nombre de pila
(primer token) se evalúa aparte con una regla explícita —igual, o una
inicial suelta compatible ("J" con "Juan")— y esa compatibilidad decide
qué umbral de fusión aplica, no el score general solo:

- nombre de pila COMPATIBLE + similitud alta  -> fusión automática
- nombre de pila COMPATIBLE + similitud media -> zona gris (a confirmar)
- nombre de pila INCOMPATIBLE + similitud muy alta -> zona gris (a
  confirmar; nunca fusión automática, sin importar cuán parecido sea el
  apellido — este es el caso Juan/Juana)
- cualquier otra combinación -> personas distintas

Un falso positivo acá fusiona dos pacientes y corrompe el LTV sin dejar
rastro — más caro que pedirle al dueño que confirme un caso ambiguuo de más.
"""

import difflib
import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

try:
    from rapidfuzz import fuzz as _rapidfuzz_fuzz
except ImportError:  # pragma: no cover — fallback deliberado, ver docstring
    _rapidfuzz_fuzz = None


# Compatible (mismo nombre de pila, o abreviatura): alcanza con esta
# similitud general para fusionar sin preguntar.
UMBRAL_FUSION_NOMBRE_COMPATIBLE = 0.80
# Compatible pero por debajo de la fusión: todavía vale la pena
# preguntarle al dueño en vez de tratarlos como desconocidos.
UMBRAL_ZONA_GRIS_NOMBRE_COMPATIBLE = 0.60
# Nombre de pila INCOMPATIBLE (Juan vs Juana): recién con una similitud
# altísima en el resto vale la pena preguntar — y aun así nunca se
# fusiona solo.
UMBRAL_ZONA_GRIS_NOMBRE_DISTINTO = 0.90

_TITULOS = {"dr", "dra", "sr", "sra", "srta", "lic", "prof"}


def normalizar_nombre(nombre: str) -> str:
    """Mayúsculas, sin acentos, sin títulos ("Dr.", "Sra."), espacios
    colapsados. Hace la mayor parte del trabajo de matching: cuanto mejor
    la normalización, menos depende el resultado de qué motor de
    similitud se use."""
    s = nombre.strip()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.upper()
    s = re.sub(r"[.,]", " ", s)
    palabras = [p for p in s.split() if p.lower() not in _TITULOS]
    return " ".join(palabras)


def _similitud_bruta(a: str, b: str) -> float:
    """0-1, sin ningún ajuste por nombre de pila — el score puro del motor."""
    if not a or not b:
        return 0.0
    if _rapidfuzz_fuzz is not None:
        return _rapidfuzz_fuzz.token_set_ratio(a, b) / 100
    return difflib.SequenceMatcher(None, a, b).ratio()


def _primer_token(nombre_normalizado: str) -> str:
    partes = nombre_normalizado.split()
    return partes[0] if partes else ""


def _nombres_de_pila_compatibles(primero_a: str, primero_b: str) -> bool:
    """True si son el mismo nombre de pila, o si uno es una inicial suelta
    compatible con el otro ("J" con "Juan"). Dos nombres de pila completos
    y distintos (Juan/Juana, Marco/Marcos) NUNCA son compatibles acá,
    aunque compartan casi todas las letras — ver el hallazgo del docstring
    del módulo."""
    if not primero_a or not primero_b:
        return True  # sin dato suficiente: no bloquea, decide el resto del score
    if primero_a == primero_b:
        return True
    if len(primero_a) == 1:
        return primero_b.startswith(primero_a)
    if len(primero_b) == 1:
        return primero_a.startswith(primero_b)
    return False


@dataclass
class Match:
    cliente_id: str
    zona: str  # "fusion_automatica" | "zona_gris" | "nuevo"
    similitud: Optional[float] = None
    candidato_existente: Optional[str] = None  # nombre canónico del más parecido, si zona_gris


@dataclass
class RegistroClientes:
    """{cliente_id: {"nombre_canonico": str, "variantes": set[str], "periodos_vistos": set[str]}}.

    Vive en memoria durante la corrida del pipeline — no es una tabla de
    la base. `cliente_id` es un hash del nombre normalizado (ver
    `_id_estable`), nunca el nombre en texto plano: es la variable que se
    propaga al resto del sistema (LTV, series por paciente), y no hace
    falta que lleve el dato personal encima para que el cálculo funcione.

    `ambiguos` acumula TODA zona gris detectada en la vida de este
    registro (aunque `encontrar_o_crear_cliente` se llame suelto, fuera de
    `resolver_lote` — es lo que necesita `excel_parser.py` para poder
    resolver una columna de nombres fila por fila, vía pandas, y aun así
    terminar sabiendo qué quedó ambiguo en toda la migración).
    """
    clientes: dict[str, dict] = field(default_factory=dict)
    ambiguos: list[dict] = field(default_factory=list)


def _id_estable(nombre_normalizado: str) -> str:
    return "pac_" + hashlib.sha256(nombre_normalizado.encode("utf-8")).hexdigest()[:12]


def encontrar_o_crear_cliente(
    nombre: str,
    registro: RegistroClientes,
    periodo: Optional[str] = None,
) -> Match:
    """Busca el paciente más parecido ya visto en `registro` y decide la
    zona (ver tabla del docstring del módulo). Nunca deja un nombre sin
    resolver: en zona gris igual crea un cliente nuevo provisorio (nunca
    fusiona en silencio) para no bloquear el resto del cálculo mientras se
    espera que el dueño confirme — el llamador (`resolver_lote`) es quien
    decide qué hacer con esa ambigüedad."""
    normalizado = normalizar_nombre(nombre)
    if not normalizado:
        raise ValueError("nombre vacío después de normalizar")

    primero = _primer_token(normalizado)
    mejor_id, mejor_similitud, mejor_nombre = None, 0.0, None
    for cid, info in registro.clientes.items():
        candidatos = [info["nombre_canonico"], *info["variantes"]]
        for candidato in candidatos:
            cand_normalizado = normalizar_nombre(candidato)
            similitud = _similitud_bruta(normalizado, cand_normalizado)
            if similitud > mejor_similitud:
                mejor_id, mejor_similitud, mejor_nombre = cid, similitud, info["nombre_canonico"]
                mejor_primero = _primer_token(cand_normalizado)

    zona = "nuevo"
    if mejor_id is not None:
        compatible = _nombres_de_pila_compatibles(primero, mejor_primero)
        if compatible and mejor_similitud >= UMBRAL_FUSION_NOMBRE_COMPATIBLE:
            zona = "fusion_automatica"
        elif compatible and mejor_similitud >= UMBRAL_ZONA_GRIS_NOMBRE_COMPATIBLE:
            zona = "zona_gris"
        elif not compatible and mejor_similitud >= UMBRAL_ZONA_GRIS_NOMBRE_DISTINTO:
            zona = "zona_gris"

    if zona == "fusion_automatica":
        registro.clientes[mejor_id]["variantes"].add(nombre)
        if periodo:
            registro.clientes[mejor_id]["periodos_vistos"].add(periodo)
        return Match(cliente_id=mejor_id, zona=zona, similitud=mejor_similitud)

    nuevo_id = _id_estable(normalizado)
    if nuevo_id not in registro.clientes:
        registro.clientes[nuevo_id] = {
            "nombre_canonico": nombre,
            "variantes": set(),
            "periodos_vistos": {periodo} if periodo else set(),
        }
    elif periodo:
        registro.clientes[nuevo_id]["periodos_vistos"].add(periodo)

    if zona == "zona_gris":
        registro.ambiguos.append({
            "nombre": nombre,
            "cliente_id_provisorio": nuevo_id,
            "candidato_existente": mejor_nombre,
            "similitud": round(mejor_similitud, 3),
            "periodo": periodo,
        })

    return Match(
        cliente_id=nuevo_id, zona=zona,
        similitud=mejor_similitud if mejor_id is not None else None,
        candidato_existente=mejor_nombre if zona == "zona_gris" else None,
    )


def resolver_lote(
    nombres_con_periodo: list[tuple[str, Optional[str]]],
    registro: Optional[RegistroClientes] = None,
) -> tuple[dict[int, str], list[dict], RegistroClientes]:
    """Resuelve una lista de (nombre, período) contra un RegistroClientes
    (nuevo si no se pasa uno ya poblado — para ir agregando registros de
    archivos sucesivos sin perder lo ya resuelto).

    Devuelve (asignaciones, ambiguos, registro):
      - asignaciones: {índice_original: cliente_id}, siempre completo.
      - ambiguos: casos en zona gris, listos para mostrarse en el mismo
        canal que ya usa `conflictos.py` (`conflictos_pendientes`) — el
        dueño decide si son la misma persona o no, el sistema no adivina.
    """
    registro = registro if registro is not None else RegistroClientes()
    asignaciones: dict[int, str] = {}
    ambiguos: list[dict] = []

    for i, (nombre, periodo) in enumerate(nombres_con_periodo):
        match = encontrar_o_crear_cliente(nombre, registro, periodo)
        asignaciones[i] = match.cliente_id
        if match.zona == "zona_gris":
            ambiguos.append({
                "indice": i,
                "nombre": nombre,
                "cliente_id_provisorio": match.cliente_id,
                "candidato_existente": match.candidato_existente,
                "similitud": round(match.similitud, 3) if match.similitud is not None else None,
            })

    return asignaciones, ambiguos, registro
