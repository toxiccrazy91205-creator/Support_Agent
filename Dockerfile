FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
WORKDIR /app
RUN apt-get update && apt-get install -y build-essential
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app/
RUN python manage.py collectstatic --noinput
EXPOSE 8000
CMD sh -c "python manage.py migrate && gunicorn whatsapp_agent_project.wsgi:application --bind 0.0.0.0:8000"
