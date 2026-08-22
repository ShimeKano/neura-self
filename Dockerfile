FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=7860

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libgl1 libsm6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-huggingface.txt ./requirements-huggingface.txt
RUN pip install --upgrade pip && pip install -r requirements-huggingface.txt

COPY . .

RUN mkdir -p /app/data /app/config

EXPOSE 7860

CMD ["python", "hf_app.py"]
