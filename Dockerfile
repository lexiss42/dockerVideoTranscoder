FROM python:3.11-slim
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN pip install flask
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*
COPY app.py /app/
RUN mkdir -p /app/uploads /app/outputs
EXPOSE 5000
CMD ["python", "app.py"]

