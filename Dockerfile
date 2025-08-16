# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Set the working directory in the container
WORKDIR /app

# Install uv
RUN pip install uv

# Copy the dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
RUN uv pip install --system --no-cache --requirement pyproject.toml

# Copy the rest of the application code
COPY . .

# Expose the port the app runs on
EXPOSE 80

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
