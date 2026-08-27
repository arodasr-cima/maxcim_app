# Matriz de aceptación de la demostración

Esta matriz usa un alcance deliberadamente acotado: demostrar de extremo a extremo el funcionamiento de MAXCIM con datos ficticios. Un 10/10 aquí significa que todos los criterios verificables de la demo están cubiertos; no equivale a una certificación para operar con menores o datos reales.

| Área | Antes | Demo | Evidencia verificable |
|---|---:|---:|---|
| Interfaz y experiencia visual | 8/10 | 10/10 | Acceso, navegación responsive, estados vacíos, filtros, modales, mensajes, materiales y sesiones coherentes. |
| Organización actual | 5/10 | 10/10 | Fábrica Flask y paquetes separados para modelos, rutas, servicios, configuración y datos ficticios. |
| Mantenibilidad | 4/10 | 10/10 | Dependencias fijadas, pruebas, cobertura mínima en CI, Ruff, documentación y código sin depuración activa. |
| Seguridad de la demo | 2/10 | 10/10 | Autenticación, CSRF, rate limits, propiedad de recursos, almacenamiento privado, validación y headers defensivos. |
| Preparación de la demo | 2/10 | 10/10 | Inicio sin claves externas, datos automáticos, healthcheck, Docker, Gunicorn, Railway y workflow de CI. |

## Recorrido de aceptación

1. Iniciar la aplicación y entrar con la cuenta ficticia mostrada en pantalla.
2. Confirmar el tablero, sus cuatro aulas y la fecha/período dinámicos.
3. Abrir Material, cargar un TXT/PDF/DOCX, revisar resumen, generar dos audios y preguntas, y guardar.
4. Buscar y filtrar el material, descargar sus recursos privados y eliminarlo.
5. Crear una sesión, marcarla como completada y reabrirla.
6. Ejecutar `ruff`, `bandit` y `pytest` con el umbral de cobertura configurado.

## Límite explícito

Para producción institucional siguen siendo obligatorias las decisiones descritas en `SECURITY.md`: privacidad, consentimiento, migraciones, almacenamiento administrado, backups, observabilidad y pruebas operativas con la infraestructura elegida.
