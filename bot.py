import logging
import asyncio
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from db_config_manager import DBConfigManager
from vinted_client import VintedClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Reduce noise from httpx and other libraries
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('telegram.ext._application').setLevel(logging.WARNING)
logging.getLogger('telegram.ext._updater').setLevel(logging.WARNING)
logging.getLogger('apscheduler').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

class VintedBot:
    def __init__(self):
        self.config_manager = DBConfigManager()
        self.vinted_client = VintedClient(self.config_manager)
        self.bot_token = self.config_manager.get_bot_token()
        
        if not self.bot_token:
            raise ValueError("Bot token not found! Please set TELEGRAM_BOT_TOKEN environment variable or add it to config.yaml")
        
        self.application = Application.builder().token(self.bot_token).build()
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup all bot handlers."""
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("add", self.add_url_command))
        self.application.add_handler(CommandHandler("list", self.list_urls_command))
        self.application.add_handler(CommandHandler("remove", self.remove_url_command))
        self.application.add_handler(CommandHandler("search", self.search_command))
        self.application.add_handler(CommandHandler("settings", self.settings_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("pause", self.pause_command))
        self.application.add_handler(CommandHandler("resume", self.resume_command))
        
        # Message handler for URLs
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Callback query handler for inline keyboards
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Add job to check new items periodically
        self.application.job_queue.run_repeating(self.check_new_items_job, interval=300, first=10)
        
        # Add job to cleanup old seen items daily
        self.application.job_queue.run_daily(self.cleanup_job, time=datetime.time(hour=3, minute=0))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        chat_id = update.effective_chat.id
        chat_title = update.effective_chat.title or update.effective_user.first_name
        
        # Add chat to config if not exists
        self.config_manager.add_chat(chat_id, chat_title)
        
        welcome_message = f"""
🤖 Welcome to Vinted Bot, {chat_title}!

I can help you monitor Vinted search results and notify you about new items.

📋 Available commands:
• /add <url> - Add a Vinted search URL to monitor
• /list - Show your monitored URLs
• /remove <url> - Remove a URL from monitoring
• /search <url> - Search items from a URL immediately
• /settings - Configure your preferences
• /status - Check bot status
• /help - Show this help message

To get started, send me a Vinted search URL or use /add <url>
        """
        
        await update.message.reply_text(welcome_message)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_message = """
📚 Vinted Bot Help

🔍 **Adding URLs to monitor:**
• Send a Vinted search URL directly
• Use /add <url> command
• Example: /add https://www.vinted.fr/vetements?search_text=nike

📋 **Managing your URLs:**
• /list - Show all your monitored URLs
• /remove <url> - Remove a URL from monitoring

🔎 **Searching:**
• /search <url> - Search items immediately
• Send any Vinted URL to search

⚙️ **Settings:**
• /settings - Configure notifications and price filters
• /pause - Completely pause bot activity (no background searches)
• /resume - Resume bot activity

📊 **Status:**
• /status - Check bot status and statistics

💡 **Tips:**
• You can monitor multiple search URLs
• The bot will check for new items every 5 minutes
• Use specific search URLs for better results
        """
        
        await update.message.reply_text(help_message)
    
    async def add_url_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /add command."""
        chat_id = update.effective_chat.id
        chat_title = update.effective_chat.title or update.effective_user.first_name
        
        # Ensure chat exists in database
        self.config_manager.add_chat(chat_id, chat_title)
        
        if not context.args:
            await update.message.reply_text("❌ Please provide a Vinted URL.\nUsage: /add <url>")
            return
        
        url = context.args[0]
        
        if not self.vinted_client.validate_url(url):
            await update.message.reply_text("❌ Invalid Vinted URL. Please provide a valid Vinted search URL.")
            return
        
        if self.config_manager.add_search_url(chat_id, url):
            await update.message.reply_text(f"✅ URL added successfully!\n\n🔗 {url}")
        else:
            await update.message.reply_text("ℹ️ This URL is already in your monitoring list.")
    
    async def list_urls_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /list command."""
        chat_id = update.effective_chat.id
        chat_title = update.effective_chat.title or update.effective_user.first_name
        
        # Ensure chat exists in database
        self.config_manager.add_chat(chat_id, chat_title)
        
        urls = self.config_manager.get_search_urls(chat_id)
        
        if not urls:
            await update.message.reply_text("📝 You don't have any monitored URLs yet.\n\nUse /add <url> to add a Vinted search URL.")
            return
        
        message = "📋 Your monitored URLs:\n\n"
        for i, url in enumerate(urls, 1):
            message += f"{i}. {url}\n"
        
        message += "\nUse /remove <url> to remove a URL from monitoring."
        
        await update.message.reply_text(message)
    
    async def remove_url_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /remove command."""
        chat_id = update.effective_chat.id
        
        if not context.args:
            await update.message.reply_text("❌ Please provide a URL to remove.\nUsage: /remove <url>")
            return
        
        url = context.args[0]
        
        if self.config_manager.remove_search_url(chat_id, url):
            await update.message.reply_text(f"✅ URL removed successfully!\n\n🔗 {url}")
        else:
            await update.message.reply_text("❌ URL not found in your monitoring list.")
    
    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /search command."""
        chat_id = update.effective_chat.id
        
        if not context.args:
            await update.message.reply_text("❌ Please provide a Vinted URL to search.\nUsage: /search <url>")
            return
        
        url = context.args[0]
        
        if not self.vinted_client.validate_url(url):
            await update.message.reply_text("❌ Invalid Vinted URL. Please provide a valid Vinted search URL.")
            return
        
        await update.message.reply_text("🔍 Searching for items...")
        
        try:
            items = self.vinted_client.search_items(url, max_items=5)
            
            if not items:
                await update.message.reply_text("❌ No items found for this search.")
                return
            
            for item in items:
                message = self.vinted_client.format_item_message(item)
                await update.message.reply_text(message, parse_mode='Markdown')
                
        except Exception as e:
            logger.error(f"Error searching items: {e}")
            await update.message.reply_text("❌ Error occurred while searching. Please try again later.")
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /settings command."""
        chat_id = update.effective_chat.id
        chat_title = update.effective_chat.title or update.effective_user.first_name
        
        # Ensure chat exists in database
        self.config_manager.add_chat(chat_id, chat_title)
        
        chat_config = self.config_manager.get_chat_config(chat_id)
        
        settings_message = f"""
⚙️ Chat Settings

🔔 Notifications: {'✅ Enabled' if chat_config.get('notifications', True) else '❌ Disabled'}
💰 Max Price: {chat_config.get('max_price', 'No limit')} €
💰 Min Price: {chat_config.get('min_price', 'No limit')} €
📊 Monitored URLs: {len(chat_config.get('search_urls', []))}

Settings configuration coming soon!
        """
        
        await update.message.reply_text(settings_message)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        chat_id = update.effective_chat.id
        chat_title = update.effective_chat.title or update.effective_user.first_name
        
        # Ensure chat exists in database
        self.config_manager.add_chat(chat_id, chat_title)
        
        chat_config = self.config_manager.get_chat_config(chat_id)
        all_chats = self.config_manager.get_all_chats()
        bot_settings = self.config_manager.get_bot_settings()
        stats = self.config_manager.get_stats()
        
        status_message = f"""
📊 Bot Status

👥 Total Chats: {len(all_chats)}
🔗 Monitored URLs in this chat: {len(chat_config.get('search_urls', []))}
📦 Total URLs tracked: {stats['search_urls']}
👁️ Total seen items: {stats['seen_items']}
⏰ Check Interval: {bot_settings.get('check_interval', 300)} seconds
📦 Max Items per Check: {bot_settings.get('max_items_per_check', 10)}

✅ Bot is running and monitoring your URLs!
        """
        
        await update.message.reply_text(status_message)
    
    async def pause_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pause command - completely pause bot activity for this chat."""
        chat_id = update.effective_chat.id
        chat_title = update.effective_chat.title or update.effective_user.first_name
        
        # Ensure chat exists in database
        self.config_manager.add_chat(chat_id, chat_title)
        
        if self.config_manager.update_chat_settings(chat_id, notifications=False, paused=True):
            await update.message.reply_text("⏸️ Bot completely paused for this chat.\n\nNo background searches or notifications.\nUse /resume to restart bot activity.")
        else:
            await update.message.reply_text("❌ Error pausing bot.")
    
    async def resume_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /resume command - resume bot activity for this chat."""
        chat_id = update.effective_chat.id
        chat_title = update.effective_chat.title or update.effective_user.first_name
        
        # Ensure chat exists in database
        self.config_manager.add_chat(chat_id, chat_title)
        
        if self.config_manager.update_chat_settings(chat_id, notifications=True, paused=False):
            await update.message.reply_text("▶️ Bot activity resumed for this chat.\n\nBackground searches and notifications enabled.\nUse /pause to stop all activity.")
        else:
            await update.message.reply_text("❌ Error resuming bot.")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages (URLs)."""
        chat_id = update.effective_chat.id
        chat_title = update.effective_chat.title or update.effective_user.first_name
        text = update.message.text
        
        # Ensure chat exists in database
        self.config_manager.add_chat(chat_id, chat_title)
        
        # Check if it's a URL
        if text.startswith(('http://', 'https://')):
            if self.vinted_client.validate_url(text):
                # Ask what to do with the URL
                keyboard = [
                    [
                        InlineKeyboardButton("➕ Add to monitoring", callback_data=f"add_{text}"),
                        InlineKeyboardButton("🔍 Search now", callback_data=f"search_{text}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"🔗 I found a Vinted URL!\n\n{text}\n\nWhat would you like to do?",
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text("❌ This doesn't look like a valid Vinted URL. Please provide a Vinted search URL.")
        else:
            await update.message.reply_text("💡 Send me a Vinted search URL to get started, or use /help to see all commands.")
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries from inline keyboards."""
        query = update.callback_query
        chat_id = query.message.chat.id
        chat_title = query.message.chat.title or query.from_user.first_name
        data = query.data
        
        # Ensure chat exists in database
        self.config_manager.add_chat(chat_id, chat_title)
        
        await query.answer()
        
        if data.startswith("add_"):
            url = data[4:]  # Remove "add_" prefix
            if self.config_manager.add_search_url(chat_id, url):
                await query.edit_message_text(f"✅ URL added to monitoring!\n\n🔗 {url}")
            else:
                await query.edit_message_text("ℹ️ This URL is already in your monitoring list.")
        
        elif data.startswith("search_"):
            url = data[7:]  # Remove "search_" prefix
            await query.edit_message_text("🔍 Searching for items...")
            
            try:
                items = self.vinted_client.search_items(url, max_items=5)
                
                if not items:
                    await query.edit_message_text("❌ No items found for this search.")
                    return
                
                # Send items as separate messages
                for item in items:
                    message = self.vinted_client.format_item_message(item)
                    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
                
                await query.edit_message_text(f"✅ Found {len(items)} items! Check the messages above.")
                
            except Exception as e:
                logger.error(f"Error searching items: {e}")
                await query.edit_message_text("❌ Error occurred while searching. Please try again later.")
    
    async def check_new_items_job(self, context: ContextTypes.DEFAULT_TYPE):
        """Job to check for new items."""
        try:
            all_chats = self.config_manager.get_all_chats()
            bot_settings = self.config_manager.get_bot_settings()
            
            for chat_id_str, chat_config in all_chats.items():
                chat_id = int(chat_id_str)
                search_urls = chat_config.get('search_urls', [])
                
                # Skip if paused or notifications disabled
                if (not search_urls or 
                    not chat_config.get('notifications', True) or 
                    chat_config.get('paused', False)):
                    continue
                
                for url in search_urls:
                    try:
                        new_items = self.vinted_client.get_new_items(
                            url, 
                            chat_id,
                            max_items=bot_settings.get('max_items_per_check', 10)
                        )
                        
                        if new_items:
                            # Send notifications for new items
                            for item in new_items:
                                message = self.vinted_client.format_item_message(item)
                                await context.bot.send_message(
                                    chat_id=chat_id,
                                    text=f"🆕 New item found!\n\n{message}",
                                    parse_mode='Markdown'
                                )
                                
                                # Small delay to avoid rate limiting
                                await asyncio.sleep(1)
                            
                            logger.info(f"Sent {len(new_items)} new item notifications to chat {chat_id}")
                    
                    except Exception as e:
                        logger.error(f"Error checking new items for chat {chat_id}, URL {url}: {e}")
            
        except Exception as e:
            logger.error(f"Error in background check job: {e}")
    
    async def cleanup_job(self, context: ContextTypes.DEFAULT_TYPE):
        """Daily cleanup job to remove old seen items."""
        try:
            cleaned_count = self.config_manager.cleanup_old_seen_items(days_old=30)
            if cleaned_count > 0:
                logger.info(f"Daily cleanup: removed {cleaned_count} old seen items")
        except Exception as e:
            logger.error(f"Error in cleanup job: {e}")
    
    def run(self):
        """Run the bot."""
        logger.info("Starting Vinted Bot...")
        
        # Start the bot
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    bot = VintedBot()
    bot.run() 