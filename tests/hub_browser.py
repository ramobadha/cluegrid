"""Game hub: destinations, responsive layout, and keyboard access."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.test-deps'))
from playwright.sync_api import sync_playwright, expect

BASE = os.environ.get('HUB_TEST_URL', 'http://127.0.0.1:8894/')

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel='chrome', headless=True)
    for width, height in ((320, 720), (390, 844), (768, 900), (1440, 1000)):
        page = browser.new_page(viewport={'width': width, 'height': height})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(BASE)
        expect(page).to_have_title('Game Night')
        expect(page.get_by_role('link', name='Play ClueGrid')).to_have_attribute('href', '/cluegrid/')
        expect(page.get_by_role('link', name='Play Empire')).to_have_attribute('href', '/empire/')
        assert page.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth')
        page.keyboard.press('Tab')
        expect(page.get_by_role('link', name='Play ClueGrid')).to_be_focused()
        assert not errors
        page.close()
    browser.close()

print('Game hub browser checks passed at 320, 390, 768, and 1440 pixels.')
