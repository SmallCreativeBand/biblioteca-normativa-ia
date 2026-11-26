# Actualizar biblioteca.html

Usa este prompt cada vez que cambie la biblioteca: un documento nuevo, una ficha corregida, un cambio de estado o un informe semanal nuevo en /novedades.

```
Regenera biblioteca.html con los datos actuales de la biblioteca.

1. Comprueba que biblioteca.xlsx y /fichas cuadran: una ficha por cada fila de la hoja
   «biblioteca», con el mismo nombre que su documento y el mismo ID, y que cada archivo de
   la columna «archivo» existe. Si algo no cuadra, dímelo y espera antes de seguir.
2. Desde la carpeta de la biblioteca, ejecuta:
   python3 herramientas/generar_biblioteca_html.py
   El script mueve la versión anterior de biblioteca.html a /papelera y escribe la nueva.
3. Si el script muestra AVISOS, enséñamelos. No corrijas datos sin mi visto bueno.
4. Abre biblioteca.html y comprueba:
   - el número de documentos coincide con las filas de biblioteca.xlsx;
   - la «Última actualización» es la fecha más reciente de la biblioteca o de los informes;
   - al buscar «decisiones automatizadas» salen los documentos de ese tema;
   - una ficha se abre completa y el botón de exportar descarga el CSV;
   - la consola del navegador no muestra errores.
5. No cambies el diseño ni la plantilla salvo que te lo pida, y no añadas nada externo
   (fuentes, scripts, CDN): la página tiene que seguir funcionando con doble clic y sin conexión.

6. La biblioteca está publicada en GitHub (SmallCreativeBand/biblioteca-normativa-ia) y la web
   sale de la rama main con GitHub Pages. Cuando todo esté bien, enséñame los cambios y,
   con mi visto bueno, haz commit y push para que la web se actualice.

Al terminar, dime en tres líneas qué ha cambiado (documentos, informes, avisos).
```

La web pública es https://smallcreativeband.github.io/biblioteca-normativa-ia/ (abre biblioteca.html). No quites los archivos `index.html` y `.nojekyll` de la raíz: el primero lleva a la página y el segundo evita que GitHub transforme las fichas .md y rompa los enlaces.

## Si el agente no puede ejecutar Python

Que siga el mismo esquema a mano, sin cambiar el diseño:
1. Copia `herramientas/plantilla_biblioteca.html` como `biblioteca.html`, después de mover la versión anterior a /papelera.
2. Sustituye `__DATOS__` por el JSON con los datos (esquema de abajo). Los caracteres `<`, `>` y `&` dentro del JSON van escritos como `<`, `>` y `&`.
3. Sustituye `__CSP__` por la política de seguridad, con el hash SHA-256 en base64 del contenido exacto del `<style>` y del `<script>` de la página: `default-src 'none'; script-src 'sha256-…'; style-src 'sha256-…'; img-src data:; base-uri 'none'; form-action 'none'; object-src 'none'`. Si el hash no coincide, el navegador bloquea la página y la consola lo dice.

Esquema del JSON: `actualizado` (AAAA-MM-DD), `generado` (AAAA-MM-DD HH:MM), `documentos` (uno por fila de la hoja «biblioteca», con sus columnas, más `corto`, `pais`, `temas` como lista, `ficha_archivo`, `origen` («alta inicial» o «rutina semanal»), `fechas_clave` [{`fecha`, `texto`}], `ficha` {`titulo`, `campos` [[campo, valor]], `secciones` [{`titulo`, `parrafos`, `items`}]} y `xlsx` (la fila tal cual)), `novedades_hoja` (filas de la hoja «novedades») e `informes` (uno por archivo de /novedades: `fecha`, `archivo`, `resumen`, `documentos_nuevos` [{`titulo`, `urls`}], `cambios` [{`id`, `estado`, `mirado`, `resultado`}]).

## De dónde saca cada parte los datos

| Parte de la página | Origen |
|---|---|
| Portada (frase y barra de estados) | Recuentos de la hoja «biblioteca»: tipos, cuántos obligan y cuántos documentos hay en cada estado. |
| Tarjetas, buscador y filtros | Hoja «biblioteca» de biblioteca.xlsx (tipo, ámbito, temas, estado, vinculante, resumen, url…). El título de la tarjeta es el de la ficha. Los filtros son botones que se combinan (dentro de un grupo suman; entre grupos se cruzan) y su número indica cuántos documentos quedarían. |
| Ficha completa | El archivo de /fichas indicado en la columna «ficha». |
| Novedades · añadido | Documentos con `fecha_alta` en las últimas cuatro semanas, contadas desde el día en que se abre la página. Se agrupan en «alta inicial» y «rutina semanal» (ID que empieza por NUEVO- o URL marcada «añadir» en la hoja «novedades»). |
| Novedades · cambios de estado | Tabla «Cambios de estado» de los informes de las últimas cuatro semanas: hay cambio cuando el estado anotado en el informe ya no es el de biblioteca.xlsx. También muestra lo que revisó el último informe. |
| Novedades · propuestas | «Documentos nuevos» del último informe que aún no están en la biblioteca (se comparan las URL). |
| Línea de tiempo | Apartado «Fechas clave» de cada ficha. Sigue la búsqueda y los filtros. |
| Exportar CSV | Las columnas de biblioteca.xlsx de los documentos que se ven, separadas por «;» y en UTF-8, para abrir en Excel. |
| Última actualización | La fecha más reciente entre `fecha_alta`, `fecha_consulta` y los informes de /novedades. |

## Para que la página siga cuadrando
- Al dar de alta un documento, rellena `fecha_alta` en biblioteca.xlsx.
- En las fichas, escribe las fechas clave como `- AAAA-MM-DD: qué ocurre` (o `AAAA-MM` / `AAAA` si el documento no da el día). Las líneas sin fecha (por ejemplo, «PENDIENTE: …») no salen en la línea de tiempo.
- En los informes semanales, la tabla «Cambios de estado» debe tener cuatro columnas: ID, estado en biblioteca.xlsx (el de antes), qué se ha mirado y resultado.
- Puedes editar biblioteca.xlsx en Excel: el script lee tanto los textos que escribe Excel como las celdas de fecha.
- Para cambiar el diseño, edita `herramientas/plantilla_biblioteca.html` y regenera. Mantén un solo `<style>` y un solo `<script>`, sin atributos `style="…"` ni `onclick="…"`: la política de seguridad de la página los bloquea.
