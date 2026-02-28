FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml /app/pyproject.toml
COPY src /app/src

RUN pip install --no-cache-dir -e .

EXPOSE 8088
CMD ["file-translator-web"]
