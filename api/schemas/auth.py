"""
schemas/auth.py

Pydantic wrappers para `POST /auth/signup`, `POST /auth/login` y
`POST /auth/refresh`. `email` queda como `str` (no `pydantic.EmailStr`)
para no sumar la dependencia `email-validator` fuera del alcance de este
cambio — Supabase Auth ya valida el formato del lado del servidor y
rechaza emails inválidos.

`SessionResponse` sirve para las tres rutas: en login y refresh,
`access_token`/`refresh_token` siempre vienen (spec lo exige). En signup
pueden venir `None` si el proyecto de Supabase tiene confirmación de
email activada (el usuario se crea, pero no hay sesión todavía hasta que
confirme) — no es un error, es un estado normal de Supabase Auth.
"""

from typing import Optional

from pydantic import BaseModel


class SignupRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class SessionResponse(BaseModel):
    user_id: str
    email: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
