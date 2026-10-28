FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
# PyPI CDN can stall during wheel downloads; use a bounded, longer read timeout.
RUN pip install --no-cache-dir --timeout 120 --retries 8 -r requirements.txt
COPY . .
RUN chmod +x /app/entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
