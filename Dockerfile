FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create uploads directory
RUN mkdir -p uploads

# Environment
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

# Run with gunicorn
CMD ["gunicorn", "-w", "3", "-b", "0.0.0.0:8000", "main:app"]
