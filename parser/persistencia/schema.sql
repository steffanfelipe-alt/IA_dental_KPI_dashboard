-- schema.sql
--
-- Schema inicial de persistencia (Repository de Supabase, ver
-- adaptador_supabase.py). Correr una sola vez a mano en el SQL Editor
-- del dashboard de Supabase (Project > SQL Editor > New query) — el
-- cliente REST (supabase-py) no puede crear tablas, solo leer/escribir
-- filas de tablas que ya existen.
--
-- Decisión de diseño (conversación 2026-08-06): esquema HÍBRIDO, no
-- relacional puro. Columnas reales solo para lo que se filtra/consulta
-- (clinica_id, variable, periodo, valor, fuente, confianza); todo lo
-- anidado/opcional de VariableValue (serie, trazabilidad,
-- periodos_no_reconocidos, etiqueta_fila) va a `detalle` JSONB — así un
-- campo nuevo en el dataclase de Python no exige una migración de schema.

create extension if not exists "pgcrypto";

create table if not exists clinicas (
  id          uuid primary key default gen_random_uuid(),
  nombre      text not null,
  creado_en   timestamptz not null default now()
);

create table if not exists variables (
  id              uuid primary key default gen_random_uuid(),
  clinica_id      uuid not null references clinicas(id) on delete cascade,
  variable        text not null,
  valor           double precision,
  periodo         text,
  fuente          text not null,
  confianza       real not null default 1.0,
  archivo_origen  text,
  metodo          text,
  detalle         jsonb,
  actualizado_en  timestamptz not null default now(),
  unique (clinica_id, variable)
);

create table if not exists respuestas_diagnostico (
  clinica_id      uuid not null references clinicas(id) on delete cascade,
  pregunta_id     text not null,
  respuesta       text not null,
  actualizado_en  timestamptz not null default now(),
  primary key (clinica_id, pregunta_id)
);

create index if not exists idx_variables_clinica_id on variables(clinica_id);
create index if not exists idx_respuestas_diagnostico_clinica_id on respuestas_diagnostico(clinica_id);

-- RLS activado sin políticas: hoy nadie accede salvo el backend con la
-- service_role key (que bypassea RLS por completo, así que esto no
-- rompe nada de lo que ya funciona). Deja la base "fallando cerrado"
-- por default para el día que exista un frontend hablando directo con
-- Supabase vía la anon key + Auth — recién ahí se agregan políticas
-- reales por clinica_id (ej. auth.uid() = clinicas.owner_id).
alter table clinicas enable row level security;
alter table variables enable row level security;
alter table respuestas_diagnostico enable row level security;
