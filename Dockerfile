# Use Python 3.13 slim image
FROM python:3.13-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies for WeasyPrint
RUN apt-get update && apt-get install -y --no-install-recommends \
    # WeasyPrint core dependencies
    libgobject-2.0-0 \
    libglib2.0-0 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libfontconfig1 \
    shared-mime-info \
    # Fonts
    fonts-liberation \
    fonts-dejavu-core \
    fontconfig \
    # Build tools and PostgreSQL dependencies
    gcc \
    g++ \
    libpq-dev \
    && fc-cache -f -v \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy project files
COPY . .

# Set working directory to support folder (where manage.py is)
WORKDIR /app/support

# Make start.sh executable
#RUN chmod +x start.sh

# Expose port (Railway will use $PORT environment variable)
EXPOSE 8080

# Start command
CMD ["bash", "start.sh"]