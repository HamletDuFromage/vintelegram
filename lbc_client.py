import lbc
from typing import List, Dict, Any, Optional
import logging
from urllib.parse import urlparse, unquote
from datetime import datetime, timezone
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class LeBonCoinClient:
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
                title = item.subject
                price = getattr(item, "price", "N/A")
                currency = getattr(item, "currency", "EUR")
                url = item.url
                images = getattr(item, "images", [])
                brand = getattr(item, "brand", "Unknown brand")
                created_at = datetime.strptime(item.first_publication_date, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                photo_url = images[0] if images else ""

                return cls(
                    title=title,
                    price=price,
                    currency=currency,
                    url=url,
                    photo_url=photo_url,
                    brand=brand,
                    created_at=created_at,
                    id=item.id,
                    search_url=search_url,
                )

            except Exception as e:
                logger.error(f"Error creating LeBonCoin Item: {e}")
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

    def __init__(self, config_manager=None):
        self.lbc = lbc.Client()
        self.last_check_times = {}  # Track last check time for each URL
        self.failed_attempts = 0
        self.config_manager = config_manager

    def refresh_session(self):
        pass

    def randomize_user_agent(self):
        pass
    
    def search_items(self, url: str, max_items: int = 10) -> List[Any]:
        """Search for items using a LeBonCoin URL."""
        self.failed_attempts += 1
        url = unquote(url)
        items = self.lbc.search(url, limit=max_items, page=1)
        
        logger.info(f"Found {len(items.ads)} items for URL: {url}")
        res = [
            item for item in items.ads
            if not any(
                attr.key == "transaction_status" and (attr.value == "pending" or attr.value == "sold")
                for attr in item.attributes
            )
        ]
        items = [LeBonCoinClient.Item.from_raw(item, search_url=url) for item in res]
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
        new_items = []
        for item in items:
            if str(item.id) not in seen_items:
                new_items.append(item)
                # Mark as seen with URL tracking
                self.config_manager.add_seen_item(chat_id, str(item.id), url)
        
        logger.info(f"Found {len(new_items)} new items for URL: {url}")
        return new_items
    
    def format_item_message(self, item: "LeBonCoinClient.Item") -> str:
        """
        Format an Item instance into a Telegram message.
        """
        message = f"🛍️ *{item.title}*\n"
        message += f"🏷️ Brand: {item.brand}\n"
        message += f"💰 Price: {item.price} {item.currency}\n"

        if item.url:
            message += f"🔗 [View on Leboncoin]({item.url})\n"

        if item.photo_url:
            message += f"📸 [Photo]({item.photo_url})\n"

        if item.search_url:
            message += f"🔍 [Search URL]({item.search_url})\n"

        return message
    
    def validate_url(self, url: str) -> bool:
        """Validate if a URL is a valid LeBonCoin search URL."""
        try:
            parsed = urlparse(url)
            return 'leboncoin' in parsed.netloc.lower()
        except Exception:
            return False
        
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    client = LeBonCoinClient()
    test_url = "https://www.leboncoin.fr/recherche?text=La+Pavoni"  # replace with a valid LeBonCoin URL

    if client.validate_url(test_url):
        items = client.search_items(test_url, max_items=5)
        print(f"Found {len(items)} items.")
        for item in items:
            print(item)
            print(client.format_item_message(item))
    else:
        print("Invalid LeBonCoin URL")