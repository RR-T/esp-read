FROM python:3.12-slim

# lxml wheels are prebuilt for slim, so no build toolchain needed.
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV LIBRARY_ROOT=/data/library \
    HOST=0.0.0.0 \
    PORT=8000

EXPOSE 8000

# --proxy-headers + trusting forwarded IPs so X-Forwarded-Proto from Caddy is
# honoured (OPDS absolute URLs then use the external https scheme). Caddy
# preserves the Host header by default.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
