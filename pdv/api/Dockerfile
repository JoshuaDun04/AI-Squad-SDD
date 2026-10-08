FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.lock.txt ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock.txt

COPY pdv_api ./pdv_api
COPY migracoes ./migracoes
COPY alembic.ini ./

RUN useradd --create-home --uid 10001 pdv
USER pdv

EXPOSE 8000
# Migra o banco e sobe a API; recusa iniciar sem JWT_SECRET/GATEWAY_TOKEN fortes.
# X-Forwarded-For só é aceito de redes privadas do Docker (o nginx do painel), que o
# preenche com o IP real do cliente (REV-18, REV-19). FORWARDED_ALLOW_IPS é lido pelo uvicorn.
ENV FORWARDED_ALLOW_IPS=172.16.0.0/12,10.0.0.0/8,192.168.0.0/16
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn pdv_api.main:criar_app_do_ambiente --factory --host 0.0.0.0 --port 8000 --proxy-headers"]
