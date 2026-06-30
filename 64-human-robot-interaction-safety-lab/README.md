# 64-human-robot-interaction-safety-lab

## 🧠 Descripción

Lab técnico para estudiar **Human-Robot Interaction** y restricciones de seguridad para agentes físicos o simulados.

Este proyecto continúa el:

```txt id="p64-prev"
63-robot-task-planning-control-lab
```

pero cambia el enfoque:

```txt id="p64-change"
Antes:
planificación y control

Ahora:
interacción humana, permisos, seguridad y confianza
```

Este proyecto pertenece al:

```txt id="p64-plan"
Plan 11 — Embodied AI, Humanoid Robotics & Android Systems
```

y forma parte del conjunto:

```txt id="p64-set"
Inteligencia Encarnada, Humanoides y Arquitectura de Androides
```

La idea central es que un robot o agente encarnado no debe ejecutar instrucciones humanas sin validarlas.

```txt id="p64-core"
instrucción humana
→ interpretación
→ validación de seguridad
→ acción permitida o bloqueada
→ explicación
```

Este proyecto introduce una capa crítica: **la seguridad antes de la acción**.

---

## 🎯 Objetivo

Crear un lab para simular instrucciones humanas, interpretarlas, validar seguridad, permitir o bloquear acciones y explicar la decisión.

El objetivo técnico es aprender:

* Human-Robot Interaction.
* Natural language instruction.
* Intent interpretation.
* Safety constraints.
* Confirmation.
* Action blocking.
* Human override.
* Explanation of actions.
* Trust and reliability.
* Safety report.

---

## 👤 Usuario objetivo

* AI Engineer en formación.
* Persona interesada en robótica segura.
* Estudiante de HRI.
* Futuro constructor de humanoides.
* Futuro constructor de android systems.
* Reclutador técnico interesado en seguridad de embodied AI.

---

## 🧱 Arquitectura esperada

```txt id="p64-arch"
Human Instruction
      ↓
Intent Interpretation
      ↓
Safety Validation
      ↓
Action Permission Layer
      ↓
Allowed / Blocked Action
      ↓
Explanation
      ↓
Log
```

---

## 🔁 Flujo técnico

```txt id="p64-flow"
receive instruction
   ↓
parse intent
   ↓
identify requested action
   ↓
check safety rules
   ↓
allow, block, or request confirmation
   ↓
explain decision
   ↓
record event
```

---

## 🧩 Módulos

### Módulo 1 — Human Instruction Input

Definir instrucciones humanas simuladas.

Incluye:

* Comandos simples.
* Comandos ambiguos.
* Comandos inseguros.
* Comandos incompletos.
* Contexto del entorno.
* Intención esperada.

Pregunta central:

```txt id="p64-q1"
¿Qué tipo de instrucciones podría recibir un robot de una persona?
```

---

### Módulo 2 — Intent Interpretation

Interpretar intención.

Incluye:

* Acción solicitada.
* Objeto objetivo.
* Lugar.
* Parámetros.
* Ambigüedad.
* Falta de información.

Pregunta central:

```txt id="p64-q2"
¿Qué quiso que hiciera la persona y qué datos faltan?
```

---

### Módulo 3 — Safety Validation

Validar seguridad.

Incluye:

* Reglas.
* Zonas prohibidas.
* Acciones peligrosas.
* Incertidumbre.
* Riesgo humano.
* Acción segura vs insegura.

Pregunta central:

```txt id="p64-q3"
¿Esta acción debería permitirse en este contexto?
```

---

### Módulo 4 — Action Permission Layer

Crear capa de permisos.

Incluye:

* Permitir.
* Bloquear.
* Pedir confirmación.
* Escalar a humano.
* Registrar razón.
* Política de decisión.

Pregunta central:

```txt id="p64-q4"
¿Cómo decide el sistema si ejecuta, bloquea o pide confirmación?
```

---

### Módulo 5 — Human Override Concept

Entender intervención humana.

Incluye:

* Override.
* Confirmación.
* Cancelación.
* Botón de parada conceptual.
* Control humano final.
* Riesgos de override.

Pregunta central:

```txt id="p64-q5"
¿Cuándo debe intervenir una persona antes de que el agente actúe?
```

---

### Módulo 6 — Safety and Trust Report

Crear reporte de seguridad y confianza.

Incluye:

* Acciones permitidas.
* Acciones bloqueadas.
* Razones.
* Casos ambiguos.
* Riesgos.
* Reglas futuras.

Pregunta central:

```txt id="p64-q6"
¿Cómo construyo confianza mostrando por qué el agente actuó o se detuvo?
```

---

## 🧪 Labs

### tec-labs

* `tec-human-instruction-lab`
* `tec-intent-interpretation-lab`
* `tec-safety-validation-lab`
* `tec-action-permission-layer-lab`
* `tec-human-override-concept-lab`
* `tec-safety-trust-report-lab`

---

## 📊 Métricas / señales de análisis

Métricas posibles:

* Instrucciones procesadas.
* Acciones permitidas.
* Acciones bloqueadas.
* Acciones que requieren confirmación.
* Casos ambiguos.
* Falsos bloqueos.
* Riesgos detectados.
* Explicaciones generadas.

Señales de aprendizaje:

* Las instrucciones no se ejecutan ciegamente.
* La intención se separa de la acción.
* La seguridad filtra decisiones.
* El agente puede pedir confirmación.
* El sistema explica por qué bloqueó algo.

---

## 📌 Próximos pasos

* Crear lista de instrucciones humanas.
* Clasificar instrucciones seguras/inseguras.
* Diseñar reglas de seguridad.
* Crear interpretación de intención.
* Crear permission layer.
* Probar comandos ambiguos.
* Probar comandos peligrosos.
* Generar explicaciones.
* Registrar eventos.
* Crear reporte de seguridad.
* Actualizar README.
* Grabar explicación corta.
* Actualizar LinkedIn y CV.

---

## ✅ Entregable final

Al terminar este proyecto debe existir:

* Conjunto de instrucciones humanas simuladas.
* Interpretación de intención.
* Reglas de seguridad.
* Capa de permisos.
* Acciones permitidas/bloqueadas.
* Confirmación conceptual.
* Logs de decisión.
* README técnico.
* Labs documentados.
* Reporte de seguridad y confianza.

---

## 🧭 Regla final

```txt id="p64-rule"
Un robot no debe obedecer todo.
Debe interpretar, validar, limitar y explicar.

La seguridad no va después de la acción.
Va antes.
```

Este proyecto no busca interacción social avanzada.

Busca construir la capa mínima de seguridad y confianza para embodied AI.
