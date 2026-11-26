# E5 · Biblioteca de IA

Montas, con un agente, una biblioteca viva sobre el uso de la IA: normas, guías y casos. El agente descarga los documentos, los lee y los ordena, revisa cada semana si hay novedades y te deja una página para consultarlo todo.

## Qué hay en esta carpeta

| Archivo | Para qué |
|---|---|
| `fuentes.csv` | 23 documentos de partida: 5 normas, 13 guías y 5 casos, con su enlace oficial (separador «;»). |
| `AGENTS.md` | Reglas de la carpeta. Cópialo dentro de tu carpeta de trabajo (en Claude, guárdalo también como `CLAUDE.md`). |
| `criterios_clasificacion.md` | Tipos, temas y estados que usará el agente para ordenar. |
| `plantilla_ficha.md` | La ficha que el agente rellena por cada documento. |
| `biblioteca_plantilla.xlsx` | El índice de la biblioteca, con las columnas y listas desplegables. |
| `prompt_rutina_semanal.md` | El prompt de la tarea programada de los lunes. |
| `prompt_interfaz.md` | El prompt para crear la página de consulta. |
| `rubrica.md` | Cómo comprobar que la biblioteca es fiable. |

## Antes de empezar

Crea una carpeta de trabajo (por ejemplo, `biblioteca-ia`) con `fuentes.csv`, `AGENTS.md`, `criterios_clasificacion.md`, `plantilla_ficha.md` y `biblioteca_plantilla.xlsx`. Ábrela en la app de Claude, en la app de ChatGPT, en Claude Code o en Codex.

Si tu agente no puede descargar archivos de internet, descarga a mano cinco PDF de `fuentes.csv`, déjalos en `/descargas` y sigue desde el paso 2.

## Paso 1 · Descarga automatizada (10 min)

```
Lee fuentes.csv. Descarga cada documento en /descargas con el nombre
AAAA-MM-DD_organismo_titulo-corto.ext (sin espacios ni tildes).
Si la URL es una página y no un PDF, guarda la página como .md y apunta los PDF que enlaza.
Descarga solo de las URL de fuentes.csv: no sigas otros enlaces.
Al terminar, crea descargas.log con una línea por fuente: id, estado (ok / falla / página) y motivo.
No borres nada.
```

## Paso 2 · Análisis y ordenación (15 min)

```
Para cada documento de /descargas:
1. Clasifícalo con criterios_clasificacion.md (tipo, ámbito, temas y estado).
2. Rellena una ficha con plantilla_ficha.md en /fichas, con el mismo nombre que el documento.
3. Muévelo a /normas, /guias o /casos.
Después, crea biblioteca.xlsx a partir de biblioteca_plantilla.xlsx: una fila por documento.
Cada dato de la ficha tiene que salir del documento: si no lo encuentras, escribe PENDIENTE.
Antes de mover nada, enséñame la lista de cambios y espera mi visto bueno.
```

Comprueba a mano dos fichas: fecha, organismo y estado.

## Paso 3 · Búsqueda semanal de novedades (5 min)

Prueba primero a mano el prompt de `prompt_rutina_semanal.md`. Si funciona, prográmalo para los lunes a las 8:00:

- **Claude:** Programadas › Nueva tarea, o pídeselo en el chat.
- **App de ChatGPT:** pídele en el chat que lo programe cada lunes.
- **Gemini:** acciones programadas.

La tarea propone novedades en `novedades/AAAA-MM-DD.md`. No descarga ni cambia la biblioteca sin tu visto bueno.

## Paso 4 · Interfaz para sacarle partido (10 min)

Pega el prompt de `prompt_interfaz.md`. El resultado es `biblioteca.html`: un buscador con filtros que se abre con doble clic, sin instalar nada. Si usas Claude, puedes pedir que la publique como artefacto para compartirla con tu equipo.

## Entrega

- `biblioteca.xlsx` y la carpeta `/fichas`.
- `descargas.log` con lo que falló.
- La tarea semanal programada (captura de pantalla) y su primer `novedades/AAAA-MM-DD.md`.
- `biblioteca.html` funcionando.

## Ojo con

- **Fechas y estados:** la normativa cambia. Que el agente diga de dónde saca cada fecha y cada estado, y la fecha de consulta.
- **Normas en tramitación:** un proyecto de ley no es una ley. Comprueba si sigue vivo.
- **Sanciones y sentencias:** pueden recurrirse o anularse. Busca si hay resolución posterior.
- **Guías:** orientan, no obligan. La columna «vinculante» tiene que reflejarlo.

_Lista de fuentes revisada el 26 de noviembre de 2026. Material preparado para el curso «Agentes y automatizaciones con IA» (ComunIA, UMH)._
