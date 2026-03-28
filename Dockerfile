FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# spaCy/thinc on slim images may need libgomp at runtime; certs help model downloads.
RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
		build-essential \
		cargo \
		ca-certificates \
		libgomp1 \
		rustc \
	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
	&& python -m pip install --no-cache-dir -r /app/requirements.txt

# Download spaCy language models
RUN python -m spacy download ja_core_news_sm \
	&& python -m spacy download en_core_web_sm

COPY . /app
