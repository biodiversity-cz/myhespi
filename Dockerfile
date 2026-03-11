FROM python:3.11-slim

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-ces \
        tesseract-ocr-deu \
        tesseract-ocr-lat \
        xz-utils \
        libgl1 \
        libglib2.0-0 \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

RUN addgroup --gid 1000 appgroup \
 && adduser --gid 1000 --uid 1000 --disabled-password --gecos appuser appuser

WORKDIR /app

COPY requirements-hespi.txt .
RUN pip install --no-cache-dir -r requirements-hespi.txt

COPY --chown=appuser:appgroup myhespi ./myhespi
COPY --chown=appuser:appgroup pyproject.toml .

RUN mkdir -p /app/myhespi-temp && chown appuser:appgroup /app/myhespi-temp

USER 1000
EXPOSE 8000

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8000", "-t", "300", "myhespi.wsgi:app"]
