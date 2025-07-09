# Docker Deployment Guide

This guide explains how to deploy the Vinted Telegram bot using Docker.

## Prerequisites

- Docker and Docker Compose installed
- Telegram Bot Token from @BotFather

## Quick Start

1. **Clone the repository:**
   ```bash
   git clone https://github.com/HamletDuFromage/vintelegram.git
   cd vintelegram
   ```

2. **Set up environment variables:**
   ```bash
   cp env.example .env
   # Edit .env and add your TELEGRAM_BOT_TOKEN
   ```

3. **Build and run with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

## Environment Variables

Create a `.env` file with the following variables:

```env
# Required: Telegram Bot Token (get from @BotFather)
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Optional: Bot settings (defaults shown)
CHECK_INTERVAL=300
MAX_ITEMS_PER_CHECK=10
DEFAULT_LANGUAGE=en
LOG_LEVEL=INFO
```

## Docker Commands

### Build the image:
```bash
docker build -t vintelegram .
```

### Run with Docker:
```bash
docker run -d \
  --name vinted-bot \
  --restart unless-stopped \
  -e TELEGRAM_BOT_TOKEN=your_token_here \
  -v $(pwd)/data:/app/data \
  vintelegram
```

### Run with Docker Compose:
```bash
# Start the bot
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the bot
docker-compose down

# Restart the bot
docker-compose restart
```

## Data Persistence

The bot's database is stored in the `./data` directory, which is mounted as a volume in Docker. This ensures your URLs and settings persist across container restarts.

## Health Checks

The container includes health checks to ensure the bot is running properly. You can check the status with:

```bash
docker ps
```

## Troubleshooting

### View logs:
```bash
docker-compose logs -f vinted-bot
```

### Access the container:
```bash
docker exec -it vintelegram bash
```

### Reset the database:
```bash
docker-compose down
rm -rf data/
docker-compose up -d
```

## Production Deployment

For production deployment, consider:

1. **Using a reverse proxy** (nginx, traefik) for SSL termination
2. **Setting up monitoring** with Prometheus/Grafana
3. **Using Docker secrets** for sensitive environment variables
4. **Setting up log rotation** for the database and logs

## Security Notes

- The bot runs as a non-root user inside the container
- Database files are stored in a mounted volume for persistence
- Environment variables are used for configuration
- The container exposes port 8080 (though not needed for polling mode) 