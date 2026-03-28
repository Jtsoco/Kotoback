FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Download spaCy language models
RUN python -m spacy download ja_core_news_sm
RUN python -m spacy download en_core_web_sm

COPY . /app
