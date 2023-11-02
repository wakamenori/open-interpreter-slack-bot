FROM python:3.10

RUN apt-get update && \
    apt-get upgrade -y \
    && apt-get install -y sqlite3 \
    && sqlite3 --version
#    apt-get install -y libgl1-mesa-dev ffmpeg fonts-ipaexfont libtesseract-dev tesseract-ocr tesseract-ocr-jpn

WORKDIR /app

RUN pip install --upgrade pip

RUN curl -sSL https://install.python-poetry.org | python -

ENV PATH /root/.local/bin:$PATH

RUN poetry config virtualenvs.create false

# Set japanese font for matplotlib
#RUN sed -i "s/^#font\.family.*/font.family:  IPAexGothic/g" /usr/local/lib/python3.10/site-packages/matplotlib/mpl-data/matplotlibrc

COPY pyproject.toml .

RUN poetry install --only main

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8081"]
