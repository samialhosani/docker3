FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies required for building certain Python packages (like sqlite-vec)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy all python modules and configuration files
COPY *.py ./
COPY config.json ./

# Create the materials directory defined in config.json to ensure the API can save uploaded files
RUN mkdir -p /app/materials

EXPOSE 8000

# Start the FastAPI app directly (data.py no longer exists in the project)
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]