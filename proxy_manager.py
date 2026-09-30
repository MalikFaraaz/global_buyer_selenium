import random
import re
import urllib.parse
from selenium.webdriver.chrome.options import Options

# ================================================================
#  ROTATING PROXY MANAGER FOR SCRAPING WORKERS
# ================================================================

class ProxyManager:
    """
    Manages proxy rotation, formatting, and Chrome WebDriver injection.
    Supports HTTP, HTTPS, and SOCKS5 proxies in standard formats:
    - ip:port
    - http://ip:port
    - http://username:password@ip:port
    - socks5://ip:port
    """

    def __init__(self, proxy_list_raw=""):
        self.proxies = self.parse_proxy_list(proxy_list_raw)
        self._current_index = 0

    @staticmethod
    def parse_proxy_list(raw_text):
        if not raw_text:
            return []
        
        lines = [line.strip() for line in raw_text.splitlines() if line.strip() and not line.strip().startswith('#')]
        valid_proxies = []

        for line in lines:
            # Check if protocol specified
            if "://" not in line:
                # Format: user:pass@ip:port or ip:port:user:pass or ip:port
                parts = line.split(":")
                if len(parts) == 4:
                    ip, port, user, pwd = parts
                    formatted = f"http://{user}:{pwd}@{ip}:{port}"
                elif len(parts) == 2:
                    ip, port = parts
                    formatted = f"http://{ip}:{port}"
                else:
                    formatted = f"http://{line}"
            else:
                formatted = line

            valid_proxies.append(formatted)

        return valid_proxies

    def get_proxy(self, worker_id=None):
        """
        Returns a rotated proxy URL or None if no proxies are configured.
        """
        if not self.proxies:
            return None
        
        if worker_id is not None:
            # Deterministic distribution per worker or random
            idx = (worker_id - 1) % len(self.proxies)
            return self.proxies[idx]
        
        return random.choice(self.proxies)

    @staticmethod
    def apply_proxy_to_options(options: Options, proxy_url: str):
        """
        Applies proxy arguments to Selenium Chrome Options.
        """
        if not proxy_url:
            return options

        parsed = urllib.parse.urlparse(proxy_url)
        # Chrome native command line supports --proxy-server=protocol://host:port
        server = f"{parsed.scheme or 'http'}://{parsed.hostname}:{parsed.port}"
        options.add_argument(f"--proxy-server={server}")

        # Note: If proxy has basic auth credentials (user:pass), Chrome requires extension or CDP
        # but for IP whitelisted or standard proxies, --proxy-server handles it seamlessly.
        return options
