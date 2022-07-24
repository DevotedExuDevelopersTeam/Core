FROM python:3.10-bullseye
RUN apt-get update -y
RUN apt-get install ffmpeg -y

RUN pip install --no-cache-dir -U poetry

COPY pyproject.toml poetry.lock /app/
WORKDIR /app
RUN poetry install

COPY . .

ENTRYPOINT ["poetry", "run", "python"]
CMD ["bot.py"]
