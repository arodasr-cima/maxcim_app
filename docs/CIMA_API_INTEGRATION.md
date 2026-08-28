# Contrato de integración con CIMA School

MAXCIM consume una sola API REST con cuatro operaciones documentadas:

| Operación | Método y ruta | Uso en MAXCIM |
|---|---|---|
| Acceso con usuario | `POST /api/v2/authentication/with/user` | Login cuando el identificador no contiene `@` |
| Acceso con correo | `POST /api/v2/authentication/with/email` | Login con correo institucional |
| Aulas del docente | `GET /api/v2/gradesection/list/group/user/{idDocente}` | Tablón y validación de pertenencia |
| Alumnos del aula | `GET /api/v2/studentschool/list/gradesectiongroup/{idGradoSection}/type/{type}/order/{order}` | Lista del aula autorizada |

Base documentada: `https://apicima.colegiocima.edu.pe:8086`.

## Autenticación

Los dos POST envían `password`, `idSystem` (21) e `identifier`, además de `username` o `email`. La respuesta esperada contiene el token en `content.token`. Como el valor ya puede comenzar por `Bearer`, el cliente normaliza el encabezado para que exista exactamente un prefijo.

La contraseña solo vive durante esa solicitud. El JWT se cifra con Fernet en `cima_sessions`; la cookie Flask contiene únicamente el ID aleatorio de la sesión. Al cerrar sesión se borra el registro cifrado.

## Autorización de aulas

Antes de consultar alumnos, MAXCIM solicita de nuevo las aulas del docente y exige coincidencia tanto de `id` como de `type`. Los únicos tipos admitidos son `N` y `G`; los órdenes admitidos son `A` y `N`.

Durante el login también se hace una consulta inicial de aulas antes de asociar el claim docente con datos locales. Esto detecta una configuración de claim que el endpoint de autorización no acepta. Aun así, la unicidad y estabilidad del claim debe ser confirmada por CIMA antes de producción.

El campo booleano `status` se muestra de forma literal como información de la API. MAXCIM no lo interpreta como activo/inactivo porque esa semántica no está definida en la documentación recibida.

## Minimización de datos

La respuesta de alumnos puede contener `photoRoute`, `institutionalEmail` e `idStudentSchool`. MAXCIM no los conserva ni los entrega al navegador. Para la lista solo utiliza:

- `idPerson` como identificador técnico;
- `firstName`;
- `lastName`.

## Confirmaciones pendientes del proveedor

- Claim exacto del JWT que representa `idDocente`/ID de usuario.
- Significado y formato exigido para `identifier`.
- Duración y eventual renovación del JWT.
- Formato de errores, límites de frecuencia y disponibilidad acordada.
- Política de tratamiento, retención y auditoría de datos de menores.

Hasta confirmar esos puntos, el sistema no debe declararse listo para producción institucional. Las pruebas automatizadas usan clientes simulados y nunca credenciales reales.
