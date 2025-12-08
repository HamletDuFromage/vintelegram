from pyVinted import Vinted
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, parse_qs
from pyVinted.requester import requester
import requests
import ua_generator
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class VintedClient:
    @dataclass
    class Item:
        title: str
        price: Any
        currency: str
        url: str
        photo_url: str
        brand: str
        created_at: datetime
        id: str
        search_url: str = ""

        @classmethod
        def from_raw(cls, item: Any, search_url: str = ""):
            """Create an Item from a raw object."""
            try:
                return cls(
                    title=item.title,
                    price=item.price,
                    currency=item.currency,
                    url=item.url,
                    photo_url=item.photo,
                    brand=getattr(item, "brand_title", "Unknown brand"),
                    created_at=item.created_at_ts,
                    id=item.id,
                    search_url=search_url,
                )
            except Exception as e:
                logger.error(f"Error creating Item: {e}")
                return cls(
                    title="",
                    price=None,
                    currency="",
                    url="",
                    photo_url="",
                    brand="Unknown brand",
                    created_at=datetime.min,
                    id=item.id,
                    search_url=search_url,
            )

    def __init__(self, config_manager=None, randomize_ua: bool = False):
        self.vinted = Vinted()
        self.last_check_times = {}  # Track last check time for each URL
        self.failed_attempts = 0
        self.config_manager = config_manager
        self.randomize_ua = randomize_ua

    def refresh_session(self):
        self.vinted = Vinted()

    def randomize_user_agent(self):
        requester.session = requests.Session()
        requester.HEADER["User-Agent"] = ua_generator.generate(device='desktop', platform='windows').text
        requester.session.headers.update(requester.HEADER)

    def search_items(self, url: str, max_items: int = 10) -> List[Any]:
        """Search for items using a Vinted URL."""
        self.failed_attempts += 1
        if self.randomize_ua:
            self.randomize_user_agent()
        res = self.vinted.items.search(url, max_items, 1)
        items = [VintedClient.Item.from_raw(item, search_url=url) for item in res]

        logger.info(f"Found {len(items)} items for URL: {url}")
        self.failed_attempts = 0
        return items
    
    def get_new_items(self, url: str, chat_id: int, max_items: int = 10) -> List[Any]:
        """Get new items since last check for a specific URL."""
        items = self.search_items(url, max_items)
        
        if not self.config_manager:
            logger.warning("No config manager provided, returning all items as new")
            return items
        
        # Get seen items for this chat
        seen_items = set(self.config_manager.get_seen_items(chat_id))
        
        # Filter items by ID to avoid duplicates
        now = datetime.now(timezone.utc)
        new_items = []
        for item in items:
            if str(item.id) not in seen_items:
                if now - item.created_at < timedelta(days=7):
                    new_items.append(item)
                # Mark as seen with URL tracking
                self.config_manager.add_seen_item(chat_id, str(item.id), url)
        
        logger.info(f"Found {len(new_items)} new items for URL: {url}")
        return new_items
    
    def format_item_dict(self, item: Any) -> Dict[str, Any]:
        """Format an item into a dictionary."""
        try:
            item_dict = {
                "title": item.title,
                "price": item.price,
                "currency": item.currency,
                "url": item.url,
                "photo_url": item.photo,
                "brand": getattr(item, 'brand_title', 'Unknown brand'),
                "search_url": item.search_url,
            }
            return item_dict
            
        except Exception as e:
            logger.error(f"Error formatting item dict: {e}")
            return {"error": f"Error formatting item"}

    def format_item_message(self, item: "VintedClient.Item") -> str:
        message = f"🛍️ *{item.title}*\n"
        message += f"🏷️ Brand: {item.brand}\n"
        message += f"💰 Price: {item.price} {item.currency}\n"

        if item.url:
            message += f"🔗 [View on Vinted]({item.url})\n"

        if item.photo_url:
            message += f"📸 [Photo]({item.photo_url})\n"

        if item.search_url:
            message += f"🔍 [Search URL]({item.search_url})\n"

        return message

    def validate_url(self, url: str) -> bool:
        """Validate if a URL is a valid Vinted search URL."""
        try:
            parsed = urlparse(url)
            return 'vinted' in parsed.netloc.lower()
        except Exception:
            return False 