# Vinted Telegram Bot

A Telegram bot that monitors Vinted search results and notifies chats about new items. Built with python-telegram-bot and pyVinted.

## Features

- 🔍 **Search Monitoring**: Monitor multiple Vinted search URLs per chat
- 🔔 **Real-time Notifications**: Get notified in your chat when new items match your criteria
- 👥 **Multi-chat Support**: Each chat (group or private) can have its own set of monitored URLs
- 📱 **Easy Management**: Add/remove URLs with simple commands
- ⚙️ **Configurable**: Customize check intervals and notification settings
- 🔎 **Instant Search**: Search items immediately from any Vinted URL

## Setup

### 1. Prerequisites

- Python 3.8 or higher
- A Telegram bot token (get from [@BotFather](https://t.me/BotFather))

### 2. Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd vinted-telegram-bot
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp env.example .env
```

5. Edit `.env` file and add your bot token:
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

### 3. Configuration

The bot uses `config.yaml` for configuration. You can customize:

- Check interval (default: 5 minutes)
- Maximum items per check
- Admin users
- Chat-specific settings

### 4. Running the Bot

```bash
python bot.py
```

## Usage

### Commands

- `/start` - Initialize the bot and get welcome message
- `/help` - Show help and available commands
- `/add <url>` - Add a Vinted search URL to monitor for this chat
- `/list` - Show your monitored URLs for this chat
- `/remove <url>` - Remove a URL from monitoring for this chat
- `/search <url>` - Search items from a URL immediately
- `/settings` - View current chat settings
- `/status` - Check bot status and statistics

### Adding Search URLs

1. **Direct URL**: Send any Vinted search URL to the chat
2. **Command**: Use `/add <url>` command
3. **Interactive**: The bot will show buttons to add or search when you send a URL

### Example URLs

```
https://www.vinted.fr/vetements?search_text=nike
https://www.vinted.fr/vetements?search_text=adidas&price_from=10&price_to=50
https://www.vinted.fr/vetements?catalog_ids[]=5&brand_ids[]=53
```

## File Structure

```
vinted-telegram-bot/
├── bot.py                 # Main bot application
├── database.py            # SQLite database operations
├── db_config_manager.py   # Database-backed configuration management
├── config_manager.py      # YAML-based configuration (legacy)
├── vinted_client.py       # Vinted API client
├── config.yaml            # Bot configuration
├── vinted_bot.db          # SQLite database (auto-created)
├── requirements.txt       # Python dependencies
├── env.example            # Environment variables template
└── README.md             # This file
```

## Configuration

### Chat Settings

Each chat (group or private) can configure:
- **Search URLs**: Multiple Vinted search URLs to monitor
- **Notifications**: Enable/disable notifications
- **Price Filters**: Set minimum and maximum price limits
- **Check Frequency**: How often to check for new items

### Bot Settings

Global bot settings in `config.yaml`:
- `check_interval`: Time between checks (seconds)
- `max_items_per_check`: Maximum items to check per URL
- `default_language`: Default language for messages

## Features in Detail

### Multi-chat Support

The bot supports multiple chats, each with their own:
- Monitored URLs
- Notification preferences
- Price filters
- Settings

### Background Monitoring

The bot runs a background task that:
- Checks all monitored URLs for all chats periodically
- Compares new items with previous results
- Sends notifications for new items
- Handles errors gracefully

### URL Validation

The bot validates Vinted URLs to ensure:
- Correct domain (vinted.com, vinted.fr, etc.)
- Valid URL format
- Search parameters are present

## Troubleshooting

### Common Issues

1. **Bot not responding**: Check if the bot token is correct
2. **No notifications**: Verify URLs are valid and notifications are enabled
3. **Rate limiting**: The bot includes delays to avoid API rate limits

### Logs

The bot logs all activities. Check the console output for:
- Chat interactions
- Search results
- Error messages
- Background task status

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This bot is for educational purposes. Please respect Vinted's terms of service and rate limits when using this bot. 