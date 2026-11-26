# Rutina semanal en GitHub

La rutina de `prompt_rutina_semanal.md` corre sola en GitHub Actions: el workflow `.github/workflows/rutina-semanal.yml` ejecuta `herramientas/rutina_semanal.py` cada lunes a las 9:00, hora de Madrid. No usa IA ni claves de API, y no cuesta nada en un repositorio público.

## Qué hace cada lunes
1. Revisa los 7 días anteriores (incluido el lunes) en las fuentes del prompt:
   - el Diario Oficial de la UE (vista diaria de las series L y C);
   - la página de la Comisión sobre el marco regulador de la IA;
   - las guías y las noticias de la AESIA;
   - las notas de prensa de la AEPD;
   - los sumarios diarios del BOE;
   - el TJUE.
2. Compara lo encontrado con `biblioteca.xlsx`, incluido el PDF que enlaza cada nota, y aparta lo que ya está.
3. Revisa si ha cambiado el estado de lo que figura en tramitación, en aplicación diferida, recurrido o PENDIENTE.
4. Guarda `novedades/AAAA-MM-DD.md`, con el mismo formato que los informes hechos a mano, y regenera `biblioteca.html`. La web se actualiza en un par de minutos.
5. Si hay documentos nuevos o posibles cambios de estado, abre un *issue* con el informe. GitHub te avisa según tus preferencias de notificaciones.

No descarga documentos, no mueve archivos y no toca `biblioteca.xlsx`. Para añadir una novedad, pídeselo al agente en el chat: «Añade a la biblioteca las novedades 1 y 3 del informe de hoy». Después, cierra el *issue*.

## Cómo se usa
- **Lanzarla a mano:** pestaña *Actions* › *Rutina semanal de novedades* › *Run workflow*. Puedes indicar una fecha (AAAA-MM-DD) o dejarla vacía para usar la de hoy.
- **Ver qué ha hecho:** en cada ejecución, el resumen muestra el informe completo.
- **Pararla:** *Actions* › *Rutina semanal de novedades* › menú «…» › *Disable workflow*. Para reanudarla, *Enable workflow*.
- **Antes de trabajar en local:** haz `git pull` para traer los informes que haya guardado la rutina.

## En qué se queda corta frente al prompt hecho por un agente
- El tipo, los temas y «por qué importa» son propuestas automáticas: «por qué importa» cita la entradilla de la fuente. Revísalos antes de añadir nada.
- Una nota o noticia cuenta como documento si menciona la IA y su título anuncia una publicación («publica», «aprueba», «suscriben una declaración», «guía», «estándares»…). Las crónicas de eventos van a «Descartados» con un «revísala».
- Busca en los títulos. No lee los documentos completos, así que no puede avisar de instrucciones escondidas dentro de ellos (tampoco las sigue: no hay ningún agente leyendo).
- El TJUE no se puede consultar sin un navegador: queda anotado como fallo y hay que mirarlo a mano.
- Un cambio de estado solo se detecta si una publicación del periodo nombra el documento. Por ejemplo, la aprobación de la ley de N04 en el BOE sí se detectaría; la disolución de las Cortes no, porque no nombra el proyecto.
- Desde los servidores de GitHub, EUR-Lex u otra web pueden mostrar un control anti-robots que no saltan las pruebas desde un ordenador normal. Si pasa, el informe lo anota como fallo y sigue con lo demás.

## Tarea programada en la app de Claude
Si dejas activas las dos rutinas, las dos escribirán el informe del lunes, y el `git pull` chocará con el archivo que ya tienes en local. Usa solo una: la de GitHub, que además actualiza la web, o la de la app, que redacta con un agente pero no sube nada.
