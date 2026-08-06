"""
config.py

Configuración del driving adapter `api/`: credenciales del cliente
Supabase anon-key (auth + JWT verification, distinto del cliente
service_role que vive dentro de `AdaptadorSupabase`) y los límites de
upload que va a consumir el endpoint de migración de archivos
(`POST /onboarding/{clinica_id}/migrar`, PR posterior — se definen acá
para que ese router solo importe las constantes, no las reinvente).

Mismo criterio fail-closed que `adaptador_supabase.py`: sin
SUPABASE_URL/SUPABASE_ANON_KEY en el entorno, `obtener_cliente_supabase_anon`
revienta con RuntimeError en vez de intentar conectar. La verificación es
lazy (recién al llamar la función, no al importar el módulo) para que
`api/deps.py` y los tests puedan importar este módulo sin tener el
entorno de Supabase configurado.
"""

import os
from typing import Any, Optional

try:
    from supabase import create_client
except ImportError:  # pragma: no cover
    create_client = None


# Límites de upload para el endpoint de migración de archivos (PR3).
# NOTA: estos números NO están fijados por spec/design — son un criterio
# propio para archivos típicos de una clínica dental (planillas Excel,
# resúmenes en PDF, fotos de pantalla/facturación). Ajustar si el negocio
# define un límite distinto.
TAMANO_MAXIMO_ARCHIVO_BYTES = 20 * 1024 * 1024  # 20 MB
EXTENSIONES_PERMITIDAS = {".xlsx", ".xls", ".pdf", ".jpg", ".jpeg", ".png"}


def obtener_cliente_supabase_anon() -> Any:
    """Cliente Supabase con la anon key: el único que usa `api/` para
    signup/login y para verificar el JWT de cada request
    (`auth.get_user(token)`). Nunca el service_role key — ese vive
    exclusivamente en `AdaptadorSupabase`."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError(
            "Faltan SUPABASE_URL/SUPABASE_ANON_KEY en el entorno: sin "
            "credenciales no se conecta a ninguna base real (falla cerrado)."
        )
    assert create_client is not None, "Instalar el SDK: pip install supabase"
    return create_client(url, key)
