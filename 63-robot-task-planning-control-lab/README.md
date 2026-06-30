# 63-robot-task-planning-control-lab

## 🧠 Descripción

Lab técnico para conectar **planificación de tareas** con **control básico** dentro de una simulación.

Este proyecto continúa el:

```txt id="p63-prev"
62-perception-memory-action-agent-lab
```

pero cambia el enfoque:

```txt id="p63-change"
Antes:
percepción, memoria y acción

Ahora:
objetivo, plan, control, feedback y corrección
```

Este proyecto pertenece al:

```txt id="p63-plan"
Plan 11 — Embodied AI, Humanoid Robotics & Android Systems
```

y forma parte del conjunto:

```txt id="p63-set"
Inteligencia Encarnada, Humanoides y Arquitectura de Androides
```

La idea central es separar dos niveles:

```txt id="p63-core"
planner:
decide qué pasos hacer

controller:
ejecuta acciones concretas para avanzar
```

Este proyecto construye el puente entre razonamiento de alto nivel y acción de bajo nivel.

---

## 🎯 Objetivo

Crear un lab donde un agente reciba un objetivo, lo divida en pasos, ejecute acciones de control y use feedback para corregir.

El objetivo técnico es aprender:

* Task planning.
* Goal decomposition.
* Control loop.
* Low-level actions.
* Feedback.
* Error correction.
* Navigation task.
* Manipulation conceptual.
* Diferencia entre planner y controller.

---

## 👤 Usuario objetivo

* AI Engineer en formación.
* Estudiante de robótica.
* Persona interesada en embodied AI.
* Futuro constructor de humanoides.
* Futuro constructor de agentes físicos.
* Reclutador técnico interesado en planning + control.

---

## 🧱 Arquitectura esperada

```txt id="p63-arch"
Goal
   ↓
Task Planner
   ↓
Steps
   ↓
Control Action
   ↓
Environment
   ↓
Feedback
   ↓
Error Correction
   ↓
Completion
```

---

## 🔁 Flujo técnico

```txt id="p63-flow"
receive goal
   ↓
decompose into steps
   ↓
choose low-level action
   ↓
execute action
   ↓
observe feedback
   ↓
adjust if needed
   ↓
finish or replan
```

---

## 🧩 Módulos

### Módulo 1 — Goal Decomposition

Dividir objetivo en subtareas.

Incluye:

* Objetivo principal.
* Pasos.
* Precondiciones.
* Resultado esperado.
* Orden de acciones.
* Fallos posibles.

Pregunta central:

```txt id="p63-q1"
¿Cómo convierto un objetivo grande en pasos ejecutables?
```

---

### Módulo 2 — Task Planner

Diseñar planner simple.

Incluye:

* Lista de pasos.
* Estado actual.
* Próximo paso.
* Verificación.
* Replan conceptual.
* Plan incompleto.

Pregunta central:

```txt id="p63-q2"
¿Cómo decide el sistema cuál es el siguiente paso de la tarea?
```

---

### Módulo 3 — Control Actions

Definir acciones de control.

Incluye:

* Mover.
* Girar.
* Acercarse.
* Esperar.
* Tomar objeto conceptual.
* Soltar objeto conceptual.
* Acción inválida.

Pregunta central:

```txt id="p63-q3"
¿Qué acciones concretas ejecutan los pasos del plan?
```

---

### Módulo 4 — Feedback Loop

Usar feedback del entorno.

Incluye:

* Estado después de acción.
* Distancia al objetivo.
* Acción exitosa.
* Acción fallida.
* Nueva observación.
* Ajuste.

Pregunta central:

```txt id="p63-q4"
¿Cómo sabe el agente si la acción funcionó?
```

---

### Módulo 5 — Error Correction

Corregir errores simples.

Incluye:

* Reintento.
* Ajuste de trayectoria.
* Cambio de paso.
* Detención segura.
* Fallos repetidos.
* Registro de error.

Pregunta central:

```txt id="p63-q5"
¿Qué hace el agente cuando el plan no sale como esperaba?
```

---

### Módulo 6 — Planner vs Controller Report

Documentar diferencia entre planner y controller.

Incluye:

* Decisión de alto nivel.
* Acción de bajo nivel.
* Feedback.
* Control.
* Replan.
* Arquitectura.

Pregunta central:

```txt id="p63-q6"
¿Por qué planificación y control no son lo mismo?
```

---

## 🧪 Labs

### tec-labs

* `tec-goal-decomposition-lab`
* `tec-task-planner-lab`
* `tec-control-actions-lab`
* `tec-feedback-loop-lab`
* `tec-error-correction-control-lab`
* `tec-planner-vs-controller-lab`

---

## 📊 Métricas / señales de análisis

Métricas posibles:

* Tareas completadas.
* Pasos por tarea.
* Reintentos.
* Errores corregidos.
* Acciones inválidas.
* Tiempo hasta completar objetivo.
* Distancia final al objetivo.
* Fallos por mala planificación.

Señales de aprendizaje:

* El objetivo se divide en pasos.
* Las acciones ejecutan pasos.
* El feedback actualiza el flujo.
* El agente puede corregir errores simples.
* Planner y controller quedan diferenciados.

---

## 📌 Próximos pasos

* Elegir tarea simulada.
* Definir objetivo.
* Dividir objetivo en pasos.
* Crear planner simple.
* Definir acciones de control.
* Ejecutar acciones.
* Observar feedback.
* Agregar corrección de errores.
* Documentar fallos.
* Crear reporte planner vs controller.
* Actualizar README.
* Grabar explicación corta.
* Actualizar LinkedIn y CV.

---

## ✅ Entregable final

Al terminar este proyecto debe existir:

* Objetivo definido.
* Planner simple.
* Lista de pasos.
* Acciones de control.
* Feedback loop.
* Error correction.
* Tarea simulada ejecutada.
* README técnico.
* Labs documentados.
* Reporte planner vs controller.

---

## 🧭 Regla final

```txt id="p63-rule"
Planificar no es controlar.
Planificar decide qué hacer.
Controlar ejecuta cómo hacerlo.

Un agente físico necesita ambas capas.
```

Este proyecto no busca robótica avanzada.

Busca entender la conexión entre intención, plan, acción y corrección.
