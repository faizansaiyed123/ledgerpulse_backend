FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY . .

EXPOSE 5000

CMD ["sh", "-c", "flask --app backend.app db upgrade && gunicorn --bind 0.0.0.0:5000 --workers ${WEB_CONCURRENCY:-2} --threads ${WEB_THREADS:-4} backend.wsgi:app"]
