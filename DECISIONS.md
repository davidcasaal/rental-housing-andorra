# Decisiones metodológicas

Log de decisiones tomadas durante el proyecto: qué se decidió, por qué, y qué alternativas se descartaron.

---

## 2026-09-14 — Gestor de entorno y dependencias: `venv` + `pip` + `requirements.txt`

**Decisión:** usar el módulo estándar `venv` para el entorno virtual y `pip` con un `requirements.txt` para las dependencias.

**Por qué:** es la opción con menos piezas nuevas que aprender de golpe, viene incluida con Python (sin instalar nada extra) y tiene la documentación más extendida. El autor viene de R y está aprendiendo el ecosistema Python desde cero.

**Alternativas descartadas:**
- `uv`: más rápido y moderno, pero una herramienta adicional que aprender antes de tener el flujo básico dominado.
- `conda`/`miniforge`: más robusto con dependencias que compilan (geopandas), pero más pesado y no es necesario todavía.

**Reconsiderar si:** aparecen problemas de instalación con paquetes geoespaciales (`geopandas`) que `pip` no resuelva bien — en ese caso, revisar `conda`.

---

## 2026-09-14 — Layout del código: `src/` con paquete `andorra_housing`

**Decisión:** el código Python vive en `src/andorra_housing/` (paquete instalable), no como carpeta suelta en la raíz del repo.

**Por qué:** obliga a instalar el propio proyecto (`pip install -e .`) para importarlo, lo que evita imports que solo funcionan "por accidente" al ejecutar desde una carpeta concreta. Es el estándar actual en proyectos Python de portfolio.

**Alternativas descartadas:**
- Layout plano (`andorra_housing/` en la raíz): más simple de entender al principio, pero con más riesgo de imports frágiles.

---

## 2026-09-14 — Visibilidad del repositorio: público desde el inicio

**Decisión:** el repositorio de GitHub (`rental-housing-andorra`) es público desde el primer commit.

**Por qué:** así lo pide el plan del proyecto (portfolio para búsqueda de empleo); mostrar el proceso de construcción, no solo el resultado final, también tiene valor de cara a reclutadores.

**Alternativas descartadas:**
- Privado hasta cerrar la Fase 1: evita mostrar pasos intermedios desordenados, pero se descarta para no restar valor de mostrar el proceso completo.
