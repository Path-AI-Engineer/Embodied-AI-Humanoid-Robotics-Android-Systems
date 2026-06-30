# 62-perception-memory-action-agent-lab

## 🧠 Descripción

Lab aplicado para construir un agente simulado pequeño que conecte **percepción, memoria y acción**.

Este proyecto continúa el:

```txt id="p62-prev"
61-embodied-ai-foundations-lab
```

pero cambia el enfoque:

```txt id="p62-change"
Antes:
entender el ciclo embodied AI

Ahora:
crear un agente que observe, recuerde y actúe
```

Este proyecto pertenece al:

```txt id="p62-plan"
Plan 11 — Embodied AI, Humanoid Robotics & Android Systems
```

y forma parte del conjunto:

```txt id="p62-set"
Inteligencia Encarnada, Humanoides y Arquitectura de Androides
```

La idea central es que un agente encarnado necesita estado interno.

No basta con recibir una observación aislada.

Debe poder construir memoria mínima del entorno.

```txt id="p62-core"
observación
→ percepción
→ memoria
→ estado interno
→ decisión
→ acción
→ actualización de memoria
```

---

## 🎯 Objetivo

Construir un agente simulado pequeño que procese observaciones, mantenga memoria simple, decida una acción y actualice su estado interno.

El objetivo técnico es aprender:

* Perception loop.
* Memory state.
* Environment observations.
* Object tracking conceptual.
* Internal world state.
* Action selection.
* Memory update.
* Ambigüedad perceptiva.
* Fallos de memoria.

---

## 👤 Usuario objetivo

* AI Engineer en formación.
* Persona interesada en embodied agents.
* Estudiante de robótica e IA.
* Futuro constructor de humanoides.
* Futuro constructor de sistemas con memoria.
* Reclutador técnico interesado en embodied AI.

---

## 🧱 Arquitectura esperada

```txt id="p62-arch"
Environment Observation
      ↓
Perception Input
      ↓
Memory State
      ↓
Internal World State
      ↓
Action Selection
      ↓
Action Execution
      ↓
Memory Update
      ↓
Failure Notes
```

---

## 🔁 Flujo técnico

```txt id="p62-flow"
observe environment
   ↓
extract perceived objects
   ↓
update memory
   ↓
build internal state
   ↓
select action
   ↓
execute action
   ↓
record result
   ↓
update memory again
```

---

## 🧩 Módulos

### Módulo 1 — Perception Input

Definir qué recibe el agente como percepción.

Incluye:

* Observaciones del entorno.
* Objetos visibles.
* Posición.
* Señales disponibles.
* Información parcial.
* Incertidumbre.

Pregunta central:

```txt id="p62-q1"
¿Qué información llega realmente al agente desde el entorno?
```

---

### Módulo 2 — Memory State

Diseñar memoria simple.

Incluye:

* Objetos vistos.
* Ubicaciones recordadas.
* Últimas acciones.
* Objetivo actual.
* Historial mínimo.
* Estados olvidados o inciertos.

Pregunta central:

```txt id="p62-q2"
¿Qué debe recordar el agente para actuar mejor después?
```

---

### Módulo 3 — Internal World State

Construir estado interno.

Incluye:

* Representación del entorno.
* Mapa simple.
* Objetos conocidos.
* Objetivo.
* Riesgos.
* Diferencia entre observación actual y memoria.

Pregunta central:

```txt id="p62-q3"
¿Cómo convierte el agente percepción y memoria en una imagen interna del mundo?
```

---

### Módulo 4 — Action Selection

Elegir acción según estado interno.

Incluye:

* Acciones posibles.
* Acción más razonable.
* Acción insegura.
* Acción desconocida.
* Reglas simples.
* Selección basada en objetivo.

Pregunta central:

```txt id="p62-q4"
¿Cómo decide el agente qué hacer usando lo que percibe y recuerda?
```

---

### Módulo 5 — Memory Update

Actualizar memoria después de actuar.

Incluye:

* Nuevo estado.
* Resultado de acción.
* Objeto encontrado.
* Objeto perdido.
* Corrección de memoria.
* Fallos de percepción.

Pregunta central:

```txt id="p62-q5"
¿Cómo cambia la memoria después de una acción?
```

---

### Módulo 6 — Failure and Ambiguity Notes

Documentar fallos.

Incluye:

* Observación parcial.
* Memoria incorrecta.
* Objeto desaparecido.
* Acción basada en dato viejo.
* Ambigüedad.
* Necesidad de verificar.

Pregunta central:

```txt id="p62-q6"
¿Qué puede salir mal cuando un agente actúa con percepción incompleta?
```

---

## 🧪 Labs

### tec-labs

* `tec-perception-input-lab`
* `tec-memory-state-lab`
* `tec-internal-world-state-lab`
* `tec-action-selection-lab`
* `tec-memory-update-lab`
* `tec-embodied-agent-failure-notes-lab`

---

## 📊 Métricas / señales de análisis

Métricas posibles:

* Objetos detectados.
* Objetos recordados.
* Acciones ejecutadas.
* Acciones correctas vs incorrectas.
* Fallos por memoria desactualizada.
* Casos de percepción parcial.
* Actualizaciones de memoria.

Señales de aprendizaje:

* El agente separa observación de memoria.
* El estado interno se actualiza.
* Las acciones usan contexto.
* La memoria puede fallar.
* Se documentan casos ambiguos.

---

## 📌 Próximos pasos

* Definir entorno pequeño.
* Definir observaciones posibles.
* Crear estructura de memoria.
* Crear estado interno.
* Definir acciones.
* Crear selección de acción.
* Ejecutar ciclo percepción-memoria-acción.
* Actualizar memoria después de acciones.
* Probar casos ambiguos.
* Documentar fallos.
* Actualizar README.
* Grabar explicación corta.
* Actualizar LinkedIn y CV.

---

## ✅ Entregable final

Al terminar este proyecto debe existir:

* Agente simulado pequeño.
* Perception input definido.
* Memory state definido.
* Internal world state.
* Action selection.
* Memory update.
* Casos de fallo.
* README técnico.
* Labs documentados.
* Reporte de ambigüedad y límites.

---

## 🧭 Regla final

```txt id="p62-rule"
Un agente encarnado no actúa solo con lo que ve ahora.
Actúa con percepción, memoria y estado interno.

Si la memoria falla,
la acción también puede fallar.
```

Este proyecto no busca memoria avanzada.

Busca construir el primer ciclo funcional percepción-memoria-acción.
