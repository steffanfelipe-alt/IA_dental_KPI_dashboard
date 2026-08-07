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

-- Sin índices extra en clinica_id: unique(clinica_id, variable) en
-- `variables` y el primary key (clinica_id, pregunta_id) en
-- `respuestas_diagnostico` ya indexan clinica_id como columna líder.

-- Migración aditiva (conversación 2026-08-06, cambio api-auth-onboarding-
-- diagnostico): `owner_id` habilita el dueño de cada clínica una vez que
-- existe Auth real; `migracion_completada_en` es la señal explícita de
-- "el archivo de migración ya se procesó" que consume el endpoint
-- GET /onboarding/{id}/estado — no se infiere de `variables` no vacío
-- porque una extracción legítima puede terminar en cero variables (ver
-- Architecture Decisions del design de este cambio). Todo `add column
-- if not exists` / `create table if not exists`: seguro de correr de
-- nuevo, no rompe filas existentes (quedan con owner_id/migracion_
-- completada_en en null hasta que se completen).
alter table clinicas add column if not exists owner_id uuid references auth.users(id);
create index if not exists idx_clinicas_owner_id on clinicas(owner_id);
alter table clinicas add column if not exists migracion_completada_en timestamptz;

-- Un informe narrativo por clínica (Opus, generate-once): `clinica_id`
-- como primary key da la idempotencia gratis — POST /informe primero
-- lee esta tabla, y solo llama al LLM si no hay fila todavía.
create table if not exists informes (
  clinica_id   uuid primary key references clinicas(id) on delete cascade,
  texto        text not null,
  generado_en  timestamptz not null default now()
);

-- RLS activado sin políticas: hoy nadie accede salvo el backend con la
-- service_role key (que bypassea RLS por completo, así que esto no
-- rompe nada de lo que ya funciona). Deja la base "fallando cerrado"
-- por default para el día que exista un frontend hablando directo con
-- Supabase vía la anon key + Auth — recién ahí se agregan políticas
-- reales por clinica_id (ej. auth.uid() = clinicas.owner_id). Sin
-- políticas `create policy` en este cambio (fuera de alcance, ver spec).
alter table clinicas enable row level security;
alter table variables enable row level security;
alter table respuestas_diagnostico enable row level security;
alter table informes enable row level security;
