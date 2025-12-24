FROM python:3.9-slim

WORKDIR /app

# Встановлюємо системні залежності
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Копіюємо requirements.txt
COPY requirements.txt .

# Встановлюємо залежності
RUN pip install -r requirements.txt

# Копіюємо ВСІ файли
COPY . .

EXPOSE 8001

# Змініть main на nsfw_service
CMD ["python", "-m", "uvicorn", "nsfw_service:app", "--host", "0.0.0.0", "--port", "8001"]