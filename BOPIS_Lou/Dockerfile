FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Expose port for FastAPI
EXPOSE 8000

# Command to run tests
CMD ["python", "-m", "pytest", "tests/", "-v"]