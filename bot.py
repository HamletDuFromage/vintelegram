import logging
import asyncio
import requests
import os
import ua_generator
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from db_config_manager import DBConfigManager
from vinted_client import VintedClient
from lbc_client import LeBonCoinClient
from pyVinted.requester import requester
from itertools import cycle

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

PROXY_FILE = "/app/data/proxies.txt"

def load_proxies(path):
    proxies = []
    if not os.path.exists(path):
        print(f"[WARN] Proxy file '{path}' not found. Continuing without proxies.")
        return proxies
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            proxies.append({
                "http":  f"http://{line}:89",
                "https": f"http://{line}:90",
            })
    return proxies

class VintedBot:
    def __init__(self):
        self.config_manager = DBConfigManager()
        self.proxies = load_proxies(PROXY_FILE)
        self.proxy_pool = cycle(self.proxies) if self.proxies else None
        self.vinted_client = VintedClient(self.config_manager)
        self.leboncoin_client = LeBonCoinClient(self.config_manager)
        self.bot_token = self.config_manager.get_bot_token()

        self.commands = {
            "start": self.start_command,
            "help": self.help_command,
            "add": self.add_url_command,
            "list": self.list_urls_command,
            "remove": self.remove_url_command,
            "search": self.search_command,
            "status": self.status_command,
            "pause": self.pause_command,
            "resume": self.resume_command,
        }
        
        if not self.bot_token:
            raise ValueError("Bot token not found! Please set TELEGRAM_BOT_TOKEN environment variable")
        
        self.application = Application.builder().token(self.bot_token).post_init(self.post_init).build()
        self._setup_handlers()

    async def post_init(self, app: Application):
        hints = [("/" + k, k) for k in self.commands.keys()]
        await self.application.bot.set_my_commands(hints)

    def _setup_handlers(self):
        """Setup all bot handlers."""

        for key, value in self.commands.items():
            self.application.add_handler(CommandHandler(key, value))

        # Message handler for URLs
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Callback query handler for inline keyboards
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Add job to check new items periodically
        if self.application.job_queue:
            self.application.job_queue.run_repeating(self.check_new_items_job, interval=300, first=10)
            
            # Add job to cleanup old seen items daily
            #self.application.job_queue.run_daily(self.cleanup_job, time=datetime.time(hour=3, minute=0))


    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        chat_id = update.effective_chat.id  # type: ignore
        chat_title = update.effective_chat.title or update.effective_user.first_name  # type: ignore
        
        # Add chat to config if not exists
        self.config_manager.add_chat(chat_id, chat_title)
        
        welcome_message = f"""
🤖 Welcome to Vinted Bot, {chat_title}!

I can help you monitor Vinted search results and notify you about new items.

📋 Available commands:
• /add <url> - Add a Vinted or LeBonCoin search URL to monitor
• /list - Show your monitored URLs
• /remove <url> - Remove a URL from monitoring
• /search <url> - Search items from a URL immediately
• /status - Check bot status
• /help - Show this help message

To get started, send me a Vinted search URL or use /add <url>
        """
        
        await update.message.reply_text(welcome_message)  # type: ignore
    
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

⚙️ **Controls:**
• /pause - Completely pause bot activity (no background searches)
• /resume - Resume bot activity

📊 **Status:**
• /status - Check bot status and statistics

💡 **Tips:**
• You can monitor multiple search URLs
• The bot will check for new items every 5 minutes
• Use specific search URLs for better results
        """
        
        await update.message.reply_text(help_message)  # type: ignore
    
    async def add_url_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /add command."""
        chat_id = update.effective_chat.id  # type: ignore
        chat_title = update.effective_chat.title or update.effective_user.first_name  # type: ignore
        
        # Ensure chat exists in database
        self.config_manager.add_chat(chat_id, chat_title)
        
        if not context.args:
            await update.message.reply_text("❌ Please provide a Vinted URL.\nUsage: /add <url>")  # type: ignore
            return
        
        url = context.args[0]
        
        if not self.vinted_client.validate_url(url) and not self.leboncoin_client.validate_url(url):
            await update.message.reply_text("❌ Invalid Vinted or LeBonCoin URL. Please provide a valid Vinted search URL.")  # type: ignore
            return
        
        if self.config_manager.add_search_url(chat_id, url):
            await update.message.reply_text(f"✅ URL added successfully!\n\n🔗 {url}")  # type: ignore
        else:
            await update.message.reply_text("ℹ️ This URL is already in your monitoring list.")  # type: ignore
    
    async def list_urls_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /list command."""
        chat_id = update.effective_chat.id  # type: ignore
        chat_title = update.effective_chat.title or update.effective_user.first_name  # type: ignore
        
        # Ensure chat exists in database
        self.config_manager.add_chat(chat_id, chat_title)
        
        urls = self.config_manager.get_search_urls(chat_id)
        
        if not urls:
            await update.message.reply_text("📝 You don't have any monitored URLs yet.\n\nUse /add <url> to add a Vinted search URL.")  # type: ignore
            return
        
        message = "📋 Your monitored URLs:\n\n"
        for i, url in enumerate(urls, 1):
            message += f"{i}. {url}\n"
        
        message += "\nUse /remove <url> to remove a URL from monitoring."
        
        await update.message.reply_text(message)  # type: ignore
    
    async def remove_url_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /remove command."""
        chat_id = update.effective_chat.id  # type: ignore
        
        if not context.args:
            await update.message.reply_text("❌ Please provide a URL to remove.\nUsage: /remove <url>")  # type: ignore
            return
        
        url = context.args[0]
        
        if self.config_manager.remove_search_url(chat_id, url):
            await update.message.reply_text(f"✅ URL removed successfully!\n\n🔗 {url}")  # type: ignore
        else:
            await update.message.reply_text("❌ URL not found in your monitoring list.")  # type: ignore
    
    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /search command."""
        chat_id = update.effective_chat.id  # type: ignore
        
        if not context.args:
            await update.message.reply_text("❌ Please provide a Vinted URL to search.\nUsage: /search <url>")  # type: ignore
            return
        
        url = context.args[0]
        
        if self.vinted_client.validate_url(url):
            client = self.vinted_client
        elif self.leboncoin_client.validate_url(url):
            client = self.leboncoin_client
        else:
            await update.message.reply_text("❌ Invalid Vinted or LeBonCoin URL. Please provide a valid search URL.")  # type: ignore
            return

        await update.message.reply_text("🔍 Searching for items...")  # type: ignore
        
        try:
            items = client.search_items(url, max_items=5)
            
            if not items:
                await update.message.reply_text("❌ No items found for this search.")  # type: ignore
                return
            
            for item in items:
                message = client.format_item_message(item, url)
                await update.message.reply_text(message, parse_mode='Markdown')  # type: ignore
                
        except Exception as e:
            await self.handle_error(context, chat_id, url, e)

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        chat_id = update.effective_chat.id  # type: ignore
        chat_title = update.effective_chat.title or update.effective_user.first_name  # type: ignore
        
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

✅ Bot status: {chat_config.get('paused', False) and "Paused" or "Active"}
        """
        
        await update.message.reply_text(status_message)  # type: ignore
    
    async def pause_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pause command - completely pause bot activity for this chat."""
        chat_id = update.effective_chat.id  # type: ignore
        chat_title = update.effective_chat.title or update.effective_user.first_name  # type: ignore
        
        # Ensure chat exists in database
        self.config_manager.add_chat(chat_id, chat_title)
        
        if self.config_manager.update_chat_settings(chat_id, paused=True):
            await update.message.reply_text("⏸️ Bot completely paused for this chat.\n\nNo background searches or notifications.\nUse /resume to restart bot activity.")  # type: ignore
        else:
            await update.message.reply_text("❌ Error pausing bot.")  # type: ignore
    
    async def resume_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /resume command - resume bot activity for this chat."""
        chat_id = update.effective_chat.id  # type: ignore
        chat_title = update.effective_chat.title or update.effective_user.first_name  # type: ignore
        
        # Ensure chat exists in database
        self.config_manager.add_chat(chat_id, chat_title)
        
        if self.config_manager.update_chat_settings(chat_id, paused=False):
            await update.message.reply_text("▶️ Bot activity resumed for this chat.\n\nBackground searches and notifications enabled.\nUse /pause to stop all activity.")  # type: ignore
        else:
            await update.message.reply_text("❌ Error resuming bot.")  # type: ignore
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages (URLs)."""
        chat_id = update.effective_chat.id  # type: ignore
        chat_title = update.effective_chat.title or update.effective_user.first_name  # type: ignore
        text = update.message.text  # type: ignore
        
        # Ensure chat exists in database
        self.config_manager.add_chat(chat_id, chat_title)
        
        # Check if it's a URL
        if text and text.startswith(('http://', 'https://')):  # type: ignore
            if self.vinted_client.validate_url(text) or self.leboncoin_client.validate_url(text):

                keyboard = [
                    [
                        InlineKeyboardButton("➕ Add to monitoring", callback_data=f"add_{text}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(  # type: ignore
                    f"🔗 I found a Vinted or LeBonCoin URL!\n\n{text}\n\nWhat would you like to do?",
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text("❌ This doesn't look like a valid Vinted URL. Please provide a Vinted search URL.")  # type: ignore
        else:
            await update.message.reply_text("💡 Send me a Vinted search URL to get started, or use /help to see all commands.")  # type: ignore
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries from inline keyboards."""
        query = update.callback_query  # type: ignore
        chat_id = query.message.chat.id  # type: ignore
        chat_title = query.message.chat.title or query.from_user.first_name  # type: ignore
        data = query.data  # type: ignore
        
        # Ensure chat exists in database
        self.config_manager.add_chat(chat_id, chat_title)
        
        await query.answer()  # type: ignore
        
        if data and data.startswith("add_"):  # type: ignore
            url = data[4:]  # Remove "add_" prefix
            if self.config_manager.add_search_url(chat_id, url):
                await query.edit_message_text(f"✅ URL added to monitoring!\n\n🔗 {url}")  # type: ignore
            else:
                await query.edit_message_text("ℹ️ This URL is already in your monitoring list.")  # type: ignore

    async def handle_error(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, url : str, e: Exception):
        """Handle errors during item fetching. Return True if problem is solved."""
        if self.vinted_client.validate_url(url):
            if "403 Client Error: Forbidden" in str(e):
                try: 
                    proxy = next(self.proxy_pool)
                    requester.session.proxies = proxy
                    ip = requests.get("https://api.ipify.org").text
                    logger.info(f"Switched to new proxy: {proxy} - ip: {ip}")
                    if self.vinted_client.failed_attempts <= 1:
                        return True
                except:
                    pass
            elif "401 Client Error: Unauthorized" in str(e):
                self.vinted_client.randomize_user_agent()
                if self.vinted_client.failed_attempts <= 1:
                    return True
        elif self.leboncoin_client.validate_url(url):
            pass
        
        message = f"Error {type(e)} for {url}: {e}"
        await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ {message}",
                    disable_notification=True
                )
        logger.error(message)
        return False

    async def check_new_items_job(self, context: ContextTypes.DEFAULT_TYPE):
        """Job to check for new items."""
        try:
            all_chats = self.config_manager.get_all_chats()
            bot_settings = self.config_manager.get_bot_settings()
            
            for chat_id_str, chat_config in all_chats.items():
                chat_id = int(chat_id_str)
                search_urls = chat_config.get('search_urls', [])
                
                # Skip if paused or no URLs
                if (not search_urls or 
                    chat_config.get('paused', False)):
                    continue
                
                while search_urls:
                    url = search_urls.pop(0)
                    try:
                        if self.vinted_client.validate_url(url):
                            client = self.vinted_client
                        elif self.leboncoin_client.validate_url(url):
                            client = self.leboncoin_client
                        else:
                            continue

                        new_items = client.get_new_items(
                            url, 
                            chat_id,
                            max_items=bot_settings.get('max_items_per_check', 10)
                        )
                        
                        if new_items:
                            # Send notifications for new items
                            for item in new_items:
                                message = client.format_item_message(item, url)
                                await context.bot.send_message(
                                    chat_id=chat_id,
                                    text=f"🆕 New item found!\n\n{message}",
                                    parse_mode='Markdown'
                                )
                                
                                # Small delay to avoid rate limiting
                                await asyncio.sleep(1)
                            
                            logger.info(f"Sent {len(new_items)} new item notifications to chat {chat_id}")
                    
                    except Exception as e:
                        if await self.handle_error(context, chat_id, url, e):
                            search_urls.append(url)
            
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
    
    def startup_check(self):
        """Check for paused chats and resume them on startup."""
        try:
            all_chats = self.config_manager.get_all_chats()
            resumed_chats = 0
            
            for chat_id_str, chat_config in all_chats.items():
                chat_id = int(chat_id_str)
                chat_name = chat_config.get('name', f'Chat {chat_id}')
                
                # Check if chat was paused
                if chat_config.get('paused', False):
                    logger.info(f"Resuming paused chat: {chat_name} (ID: {chat_id})")
                    
                    # Resume the chat
                    if self.config_manager.update_chat_settings(chat_id, paused=False):
                        resumed_chats += 1
                        logger.info(f"✅ Successfully resumed chat: {chat_name}")
                    else:
                        logger.error(f"❌ Failed to resume chat: {chat_name}")
            
            if resumed_chats > 0:
                logger.info(f"🔄 Bot startup: Resumed {resumed_chats} previously paused chats")
            else:
                logger.info("✅ Bot startup: No paused chats found")
                
        except Exception as e:
            logger.error(f"Error during startup check: {e}")
    
    def run(self):
        """Run the bot."""
        logger.info("Starting Vinted Bot...")
        
        # Check for paused chats and resume them
        self.startup_check()
        
        # Start the bot
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    bot = VintedBot()
    bot.run() 