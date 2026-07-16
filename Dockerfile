FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for SQLite database and logs
RUN mkdir -p /app/data /app/logs

# Hugging Face Spaces runs as user 1000
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER 1000

# Hugging Face Spaces exposes port 7860 by default
ENV PORT=7860
ENV APP_ENV=production
EXPOSE 7860

# Run the FastAPI application using Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
