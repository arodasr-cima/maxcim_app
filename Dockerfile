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

EXPOSE 8080

CMD ["sh", "-c", "python init_db.py && exec gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 4 --timeout 900 wsgi:app"]
