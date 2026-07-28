# Checklist — próximo a implementar

## Bloqueado (necesita `ANTHROPIC_API_KEY`)

- [ ] Exportar `ANTHROPIC_API_KEY` (vos)
- [ ] Armar `parser/probar_manual.py` (runner mínimo, sin FastAPI)
- [ ] Conseguir 2-3 archivos reales de prueba (Excel/CSV + foto de planilla)
- [ ] Correr el pipeline completo contra la API real y ajustar `SYSTEM_PROMPT`
- [ ] Probar `interpretar_kpi` con cliente real (hoy solo probado con `client=None`)

## No bloqueado — capacidades nuevas del agente (planeamos juntos)

- [ ] Estructura en `interpretacion.py` para cargar documentos de conocimiento
      en el system prompt (vos escribís el contenido, yo preparo el código)
- [ ] Diseño de salida de doble nivel: diagnóstico en lenguaje natural +
      anexo técnico accionable
- [ ] Paso 9 del diagrama del Miro: detectar cuándo se desplaza el cuello
      de botella (comparar top-3 de un período vs. el anterior)
- [ ] Actualizar el Miro: spec de qué métricas muestra el hub principal
      del dashboard (diseño, no frontend todavía)
