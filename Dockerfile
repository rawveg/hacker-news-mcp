FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Expose port for HTTP transport
EXPOSE 8000

# Run the server with SSE transport by default
CMD ["python", "run.py", "--transport", "sse", "--host", "0.0.0.0", "--port", "8000"]
