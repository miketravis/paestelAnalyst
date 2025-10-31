# Use an official Python runtime as a parent image
FROM python:3.14-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies needed for psycopg2
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Gunicorn is the production server
# Cloud Run automatically sets the $PORT environment variable
CMD ["gunicorn", "-b", "0.0.0.0:$PORT", "main:app", "-k", "uvicorn.workers.UvicornWorker"]