"""
main.py

Instancia de FastAPI. `api/` es un driving adapter (Screaming
Architecture): no tiene lógica de negocio propia, sólo traduce
HTTP↔dominio y delega todo a `parser/`. Ver design del cambio
api-auth-onboarding-diagnostico para el detalle completo.

Las rutas de diagnóstico/informe (tasks 4.5/4.6) viven dentro de
`clinicas.router` (prefix `/clinicas`), no en un router aparte — no
hace falta un `include_router` nuevo para ellas.
"""

from fastapi import FastAPI

from api.errores import registrar_manejadores_de_error
from api.routers import auth, clinicas, onboarding

app = FastAPI(title="Agencia IA Dental — API")

registrar_manejadores_de_error(app)

app.include_router(auth.router)
app.include_router(clinicas.router)
app.include_router(onboarding.router)
