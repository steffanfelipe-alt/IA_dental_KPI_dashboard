"""
ledger.py

Construye `ledger_pacientes` ({paciente_id: [eventos]}) a partir de una
lista de registros ya extraídos, uno por fila transaccional (turno,
presupuesto, pago, alta, referido). Vive aparte de extractors/excel_parser.py
a propósito: ese módulo mapea UNA columna a UNA variable, pero un evento de
ledger necesita varias columnas a la vez (nombre + fecha + tipo + monto +
tratamiento) resueltas en conjunto contra matching.py — no encaja en ese
contrato. Esta función es agnóstica de CÓMO se extrajeron los registros
(hoy: ninguna extracción en vivo se los pasa todavía — ver nota de scope
más abajo); opera sobre dicts ya planos, sea cual sea su origen.

## Vocabulario de eventos (`tipo_evento`)

  turno_asistido, turno_no_show           — cada turno agendado es UN evento
  presupuesto_emitido, presupuesto_aceptado
  tratamiento_iniciado, tratamiento_completado
  pago                                     — dinero efectivamente cobrado
  alta                                     — fin de un ciclo de tratamiento
  referido_recibido                        — este paciente trajo a alguien

Un evento con un `tipo_evento` fuera de este vocabulario no rompe nada —
metricas_paciente.py simplemente no lo cuenta para las métricas que
dependen de un tipo puntual, nunca asume qué era.

## Nota de scope (Fase 2)

Hoy no hay ningún extractor en vivo (excel_parser.py, vision_parser.py)
que arme esta lista de `registros` automáticamente desde una hoja real —
eso requeriría extender el contrato del SYSTEM_PROMPT de excel_parser.py
para que Claude identifique una columna de nombre + fecha + tipo en una
hoja transaccional, un cambio que necesita validarse contra la API real
(fuera de alcance sin poder correr esa validación en este entorno). Esta
función es el punto de enganche ya listo para cuando esa extracción se
construya: toma registros ya planos, sin importar de dónde salieron.
"""

from typing import Optional

from parser.pacientes.matching import RegistroClientes, encontrar_o_crear_cliente
from parser.vocabulario.periodos import normalizar_periodo

TIPOS_EVENTO = {
    "turno_asistido", "turno_no_show",
    "presupuesto_emitido", "presupuesto_aceptado",
    "tratamiento_iniciado", "tratamiento_completado",
    "pago",
    "alta",
    "referido_recibido",
}


def construir_ledger_pacientes(
    registros: list[dict],
    campo_nombre: str = "paciente",
    campo_fecha: str = "fecha",
    campo_tipo: str = "tipo_evento",
    campo_monto: str = "monto",
    campo_tratamiento: str = "tratamiento",
    registro_clientes: Optional[RegistroClientes] = None,
    campo_es_id_estable: bool = False,
) -> tuple[dict[str, list[dict]], RegistroClientes]:
    """Cada `registro` es un dict con al menos nombre y fecha. Un registro
    sin nombre o con fecha irreconocible se descarta del ledger — no hay
    dónde ubicarlo en el tiempo ni a quién asignarlo, y no se inventa
    ninguna de las dos cosas (misma filosofía que `variables_en_cuarentena`:
    lo que no se puede confirmar queda afuera, no se adivina).

    Devuelve (ledger, registro_clientes) — pasar el mismo
    `registro_clientes` a través de todos los archivos de una migración,
    igual que hace `pipeline.procesar_migracion` con `aplicar_mapeo`.

    Fase H4a: `campo_es_id_estable=True` cuando la columna de paciente ya
    es un identificador canónico (ej. "P1045" de un sistema de gestión),
    no un nombre tipeado a mano. `matching.py` existe para el problema de
    "Juan Pérez" vs "J. Perez" — nombres reales, con variación de tipeo.
    Un ID ya es estable por construcción; pasarlo igual por matching
    difuso es activamente peligroso: se probó que identificadores como
    "Paciente 1"/"Paciente 2"/"Paciente 3" superan el umbral de fusión
    automática (comparten el primer token "PACIENTE" + similitud > 0.80)
    y el sistema los fusiona EN SILENCIO en un solo cliente — exactamente
    lo que `matching.py` promete no hacer nunca. Acá se evita el problema
    entero: con un ID estable no se llama a `matching.py` en absoluto, se
    usa el valor (normalizado) directo como `cliente_id`. Con el default
    `False`, el comportamiento es exactamente el de siempre — el camino
    de nombres reales no cambia una línea."""
    registro_clientes = registro_clientes if registro_clientes is not None else RegistroClientes()
    ledger: dict[str, list[dict]] = {}

    for r in registros:
        nombre = r.get(campo_nombre)
        fecha_cruda = r.get(campo_fecha)
        if not nombre or fecha_cruda is None:
            continue
        periodo = normalizar_periodo(str(fecha_cruda))
        if periodo is None:
            continue

        if campo_es_id_estable:
            cliente_id = str(nombre).strip()
        else:
            cliente_id = encontrar_o_crear_cliente(str(nombre), registro_clientes, periodo).cliente_id
        evento = {
            "fecha": str(fecha_cruda),
            "periodo": periodo,
            "tipo_evento": r.get(campo_tipo),
            "monto": r.get(campo_monto),
            "tratamiento": r.get(campo_tratamiento),
        }
        ledger.setdefault(cliente_id, []).append(evento)

    for eventos in ledger.values():
        eventos.sort(key=lambda e: e["periodo"])

    return ledger, registro_clientes
