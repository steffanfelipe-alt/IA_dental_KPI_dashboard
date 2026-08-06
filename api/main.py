"""
main.py

Instancia de FastAPI. `api/` es un driving adapter (Screaming
Architecture): no tiene lógica de negocio propia, sólo traduce
HTTP↔dominio y delega todo a `parser/`. Ver design del cambio
api-auth-onboarding-diagnostico para el detalle completo.

`include_router` de `diagnostico`/`informe` (rutas de
`api/routers/clinicas.py` tasks 4.5/4.6) NO está acá todavía — llega en
el PR de diagnóstico/informe.
"""

from fastapi import FastAPI

from api.errores import registrar_manejadores_de_error
from api.routers import auth, clinicas, onboarding

app = FastAPI(title="Agencia IA Dental — API")

registrar_manejadores_de_error(app)

app.include_router(auth.router)
app.include_router(clinicas.router)
app.include_router(onboarding.router)
