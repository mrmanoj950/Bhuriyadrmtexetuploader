# Use Python 3.10 slim image as the base image
FROM python:3.10.8-slim-buster

# Install necessary system dependencies
RUN apt-get update -y && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
       gcc libffi-dev musl-dev ffmpeg aria2 python3-pip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy the application code into the container
COPY . /app/

# Set the working directory
WORKDIR /app/

# Install Python dependencies
RUN pip3 install --no-cache-dir --upgrade -r requirements.txt

# Start both the Gunicorn server and the main Python script using supervisord
CMD gunicorn app:app --daemon && python3 modules/main.py
