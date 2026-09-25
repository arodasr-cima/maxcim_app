FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./
# Los archivos de materiales viven fuera de static/ para que no se sirvan sin
# autenticación (ver UPLOADS_ROOT en app.py / MAXCIM_UPLOADS_DIR).
RUN mkdir -p /app/instance/uploads

# Corre como usuario sin privilegios: ni gunicorn ni la app necesitan root, y
# limita el alcance de un contenedor comprometido. El chown va antes de fijar
# el volumen de /app/instance/uploads para que, si se monta vacío, herede el
# dueño correcto.
RUN useradd --create-home --uid 1000 maxcim \
    && chown -R maxcim:maxcim /app
USER maxcim

EXPOSE 8080

# `/health` no toca la base de datos (ver app.py); solo confirma que el
# proceso de Gunicorn sigue vivo y respondiendo.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8080') + '/health', timeout=3)"]

CMD ["sh", "-c", "python init_db.py && exec gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 4 --timeout 900 wsgi:app"]
