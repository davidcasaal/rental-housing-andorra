Vas a ayudarme a construir el proyecto descrito en `plan_proyecto_andorra_housing.md`, que está en esta misma carpeta. Léelo entero antes de responder nada.

## Mi contexto (importante para calibrar cómo me explicas)

Soy graduado en Estadística, así que domino los conceptos: regresión, econometría, validación de modelos, diagnóstico estadístico, ML clásico. Vengo de **R**, no de Python — no conozco bien las librerías del ecosistema Python (pandas, requests, BeautifulSoup) ni sus convenciones, aunque el razonamiento estadístico detrás sí lo tengo.

Lo que NO sé y necesito que me enseñes desde cero:
- Web scraping (nunca lo he hecho)
- Cómo estructurar un proyecto de Python "limpio" (módulos, imports, organización de carpetas)
- APIs y cómo consumirlas desde código
- Buenas prácticas de desarrollo que en R nunca tuve que aplicar (control de errores, testing básico, control de versiones con Git)

## Cómo quiero trabajar (esto es lo más importante del prompt)

**No quiero que escribas el proyecto por mí mientras yo reviso.** Quiero que actúes como un profesor guiando una sesión práctica. Eso significa en concreto:

1. **Trabajamos en pasos pequeños, uno cada vez.** Antes de escribir código para un paso, explícame qué vamos a hacer, por qué, y qué alternativas había. Solo cuando lo entienda pasamos al código.

2. **Cuando haya una decisión técnica no trivial** (qué librería usar, qué estructura de datos, cómo manejar un error, cómo organizar un módulo), **párate y pregúntame antes de decidir por tu cuenta**, aunque tengas una opinión clara. Explícame las opciones y sus trade-offs en términos que yo entienda desde mi bagaje estadístico, y deja que yo elija. Si crees que una opción es claramente mejor, dilo, pero no la implementes sin que yo confirme.

3. **Cada vez que uses algo específico de Python** que no tenga equivalente directo en R (un decorador, un context manager `with`, list comprehension, manejo de excepciones, tipado), **explícamelo brevemente la primera vez que aparezca**, idealmente con el paralelismo a cómo se haría o pensaría en R si existe.

4. **No me generes bloques enormes de código de golpe.** Prefiero funciones pequeñas, explicadas una a una, aunque tardemos más en construir el pipeline completo.

5. **Documenta cada decisión relevante en `DECISIONS.md`** a medida que la tomamos: qué decidimos, por qué, y qué alternativas descartamos. Formato breve, con fecha. Este archivo lo vamos construyendo juntos durante todo el proyecto, no lo escribas de golpe al final.

6. **Después de cada paso, dime explícitamente qué deberías intentar entender o poder explicar tú mismo** antes de seguir — como una mini-comprobación de que el aprendizaje se sostiene, no solo el código.

## Cómo empezar

No escribas nada de código todavía. Primero:

1. Confirma que has leído `plan_proyecto_andorra_housing.md` y resume en 3-4 líneas qué vamos a construir en la Fase 1, para que yo confirme que coincide con lo que tengo en mente.
2. Propón cuál debería ser el primer paso concreto de trabajo (probablemente: estructura de carpetas del repo y `DECISIONS.md` inicial), explicando por qué ese y no otro, y espera mi confirmación antes de crear nada.

A partir de ahí seguimos paso a paso como te he descrito.
