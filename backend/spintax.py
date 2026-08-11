import random

def parse_spintax(text: str) -> str:
    """Parse traditional spintax {a|b|c} if needed."""
    import re
    def replace(match):
        options = match.group(1).split('|')
        return random.choice(options)
    
    while '{' in text:
        text = re.sub(r'\{([^{}]*)\}', replace, text)
    return text

def get_random_line(text_block: str) -> str:
    if not text_block: return ""
    lines = [line.strip() for line in text_block.split('\n') if line.strip()]
    if not lines: return ""
    return random.choice(lines)

def generate_prompt(subject: str, detail: str, background: str, quality: str) -> str:
    """Combine 4 boxes randomly (like PinShop)."""
    sub = get_random_line(subject)
    det = get_random_line(detail)
    bg = get_random_line(background)
    qual = get_random_line(quality)
    
    parts = [p for p in (sub, det, bg, qual) if p]
    return " ".join(parts)

import requests
import re
from urllib.parse import urlparse

def resolve_shopee_title(url: str) -> str:
    """Resolve Shopee shortlink and extract product title from the URL path."""
    try:
        if "s.shopee.co.id" in url or "shp.ee" in url:
            # allow_redirects will resolve the shortlink
            r = requests.get(url, allow_redirects=True, timeout=10)
            final_url = r.url
        else:
            final_url = url
            
        parsed = urlparse(final_url)
        path = parsed.path.strip("/") # e.g. Avery-TBDO-Meja-Kantor-i.102042394.48515122426
        
        # Remove the -i.ID.ID suffix
        title_part = re.sub(r'-i\.\d+\.\d+.*$', '', path)
        
        # Replace dashes with spaces
        clean_title = title_part.replace("-", " ").strip()
        
        # If path was empty or weird, fallback
        if not clean_title or clean_title == "buyer" or clean_title == "login":
            return "Rekomendasi Produk Terbaik"
            
        # Capitalize words
        return clean_title.title()
        
    except Exception as e:
        print(f"Error resolving shopee link: {e}")
        return "Rekomendasi Produk Estetik"
