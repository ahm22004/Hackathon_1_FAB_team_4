# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install git and other dependencies
RUN apt-get update && apt-get install -y \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set GIT_PYTHON_GIT_EXECUTABLE environment variable
ENV GIT_PYTHON_REFRESH=quiet
ENV GIT_PYTHON_GIT_EXECUTABLE=/usr/bin/git

# Copy the current directory contents into the container at /app
COPY . .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make port 8002 available to the world outside this container
EXPOSE 8002

# Run app.py when the container launches
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
