FROM python:3.11-bullseye

RUN pip install --no-cache-dir -U poetry==1.2.2

COPY pyproject.toml poetry.lock /app/
WORKDIR /app
RUN poetry install --no-dev

COPY . .

ENTRYPOINT ["poetry", "run", "python"]
CMD ["main.py"]
