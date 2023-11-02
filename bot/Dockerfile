FROM --platform=linux/amd64 python:3.10

RUN apt-get update && \
    apt-get upgrade -y

WORKDIR /app

RUN pip install --upgrade pip

RUN curl -sSL https://install.python-poetry.org | python -

ENV PATH /root/.local/bin:$PATH

RUN poetry config virtualenvs.create false

COPY pyproject.toml .

RUN poetry install --only main

COPY . .

COPY ["config.yaml", "/root/.config/Open Interpreter/"]

CMD ["gunicorn", "-b", "0.0.0.0:8080", "main:app"]
