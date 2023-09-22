FROM python:3.10-slim

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y libgl1-mesa-dev ffmpeg fonts-ipaexfont libtesseract-dev tesseract-ocr tesseract-ocr-jpn

WORKDIR /app

RUN pip install --upgrade pip

COPY requirements.txt .

RUN pip install -r requirements.txt

# Set japanese font for matplotlib
RUN sed -i "s/^#font\.family.*/font.family:  IPAexGothic/g" /usr/local/lib/python3.10/site-packages/matplotlib/mpl-data/matplotlibrc

COPY . .

CMD ["gunicorn", "-b", "0.0.0.0:8080", "main:app"]
