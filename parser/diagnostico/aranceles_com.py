"""
aranceles_com.py

Arancel mínimo sugerido del Círculo Odontológico de Mar del Plata — la
única referencia 100% argentina y oficial de todo el research de
benchmarks (ver `parser/referencias/benchmarks_research_AR.md`). Se usa
como unidad de referencia para blindar de la inflación los benchmarks en
pesos (ticket promedio, producción por hora): en vez de guardar un monto
fijo en ARS que se desactualiza en semanas, `benchmarks.py` los guarda
como múltiplo de "consulta" y los resuelve a ARS acá, en tiempo real.

Actualizar estos números cuando el Círculo publique un arancel nuevo (lo
hacen varias veces por año) — eso revaloriza automáticamente todos los
benchmarks que dependen de "consulta", sin tocar benchmarks.py.
"""

ARANCEL_COM = {
    "fecha": "2025-03",
    "fuente": (
        "Círculo Odontológico de Mar del Plata — Aranceles marzo 2025 "
        "(circulo.com.org.ar/wp-content/uploads/2025/03/ARANCELES-C0M-MARZO-2025.pdf)"
    ),
    "consulta": 29795,                  # unidad base de referencia
    "consulta_urgencia": 34531,
    "obturacion_simple": 47386,
    "endodoncia_unirradicular": 95653,  # ≈ 3.2 consultas
    "endodoncia_3_conductos": 139846,
    "limpieza": 38328,                  # tartrectomía + cepillado, ≈ 1.3 consultas
    "consulta_preventiva_fluor": 28148,
    "corona_porcelana": 306238,         # ≈ 10.3 consultas
    "corona_circonio": 367484,
    "extraccion_simple": 52415,
}
