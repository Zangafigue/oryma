FROM python:3.13-alpine3.22

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir .

EXPOSE 8080
CMD ["uvicorn", "admin_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
