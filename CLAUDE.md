# Colaboración en MAXCIM

Estas reglas aplican a cualquier sesión de Claude que trabaje en este repositorio:

1. Trabaja sobre la rama principal `master`, salvo que el propietario indique expresamente otra rama.
2. Antes de editar, ejecuta `git fetch origin` y actualiza `master` únicamente mediante avance rápido.
3. Conserva los cambios existentes del usuario y nunca uses `force-push`, `reset --hard` ni comandos destructivos.
4. No guardes contraseñas, secretos OAuth, tokens, archivos `.env` ni credenciales personales en Git.
5. Mantén las garantías del acceso institucional de Google: Authorization Code, PKCE, `state`, `nonce`, validación del ID token, dominio Workspace y autorización explícita de docentes.
6. Antes de publicar, ejecuta:

   ```bash
   ruff check .
   bandit -q -r maxcim app.py wsgi.py
   pytest --cov=maxcim --cov-report=term-missing --cov-fail-under=75
   ```

7. Publica solamente si todas las comprobaciones terminan correctamente y `master` no ha divergido del remoto.
