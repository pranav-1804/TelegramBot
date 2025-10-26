# Use a lightweight Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy dependency files first (for caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project
COPY . .

# Set environment variables (optional)
ENV PYTHONUNBUFFERED=1

# Define the default command to run your bot
CMD ["python", "services/telegram_listener.py"]
