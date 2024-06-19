FROM python:3.11

WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN pip install --no-cache-dir poetry

RUN poetry install --no-root

COPY . .
#COPY backend/.env . # delete for ci

# add python root module
ENV PYTHONPATH="${PYTHONPATH}/app"

CMD ["poetry","run","python","backend/main.py"]

# in server
# docker build -t bada-api-image:latest .
# docker run -d -p 3000:8000 --name bada-api-container --network=bada-db_bada-bridge bada-api-image
