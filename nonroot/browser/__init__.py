"""
NonRoot Embedded Browser Subsystem.
Provides Chromium browser automation, visual feedback, and 1:1 site cloning.
"""

from nonroot.browser.manager import BrowserManager, get_browser_manager
from nonroot.browser.cloner import SiteCloner

__all__ = ["BrowserManager", "get_browser_manager", "SiteCloner"]
