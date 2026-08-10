"""
config.py

Configuración del driving adapter `api/`: credenciales del cliente
Supabase anon-key (auth + JWT verification, distinto del cliente
service_role que vive dentro de `AdaptadorSupabase`), del cliente
Anthropic (Opus, el único LLM call de todo `api/` — `POST
/clinicas/{id}/informe`) y los límites de upload que consume el
endpoint de migración de archivos (`POST /onboarding/{clinica_id}/migrar`).

Mismo criterio fail-closed que `adaptador_supabase.py` para los dos
clientes: sin las variables de entorno correspondientes,
`obtener_cliente_supabase_anon`/`obtener_cliente_anthropic` revientan
con RuntimeError en vez de intentar conectar. La verificación es lazy
(recién al llamar la función, no al importar el módulo) para que
`api/deps.py` y los tests puedan importar este módulo sin tener ningún
entorno configurado, y para que los tests puedan overridear estos
providers con `app.dependency_overrides` sin necesitar credenciales
reales.
"""

import os
from typing import Any, Optional

try:
    from supabase import create_client
except ImportError:  # pragma: no cover
    create_client = None

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None


# Límites de upload para el endpoint de migración de archivos (PR3).
# NOTA: estos números NO están fijados por spec/design — son un criterio
# propio para archivos típicos de una clínica dental (planillas Excel,
# resúmenes en PDF, fotos de pantalla/facturación). Ajustar si el negocio
# define un límite distinto.
TAMANO_MAXIMO_ARCHIVO_BYTES = 20 * 1024 * 1024  # 20 MB
EXTENSIONES_PERMITIDAS = {".xlsx", ".xls", ".csv", ".pdf", ".jpg", ".jpeg", ".png"}


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


def obtener_cliente_anthropic() -> Any:
    """Cliente Anthropic (Opus) que `interpretar_clinica` usa para
    generar el informe narrativo (`POST /clinicas/{clinica_id}/informe`,
    generate-once — ver `api/routers/clinicas.py`). Como
    `obtener_cliente_supabase_anon`: fail-closed y lazy, para que este
    módulo se pueda importar sin `ANTHROPIC_API_KEY` en el entorno."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "Falta ANTHROPIC_API_KEY en el entorno: sin credenciales no se "
            "llama a la API real de Anthropic (falla cerrado)."
        )
    assert anthropic is not None, "Instalar el SDK: pip install anthropic"
    return anthropic.Anthropic(api_key=key)
