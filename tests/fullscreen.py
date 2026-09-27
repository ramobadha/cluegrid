"""Native fullscreen success, exit, rejection, and grid fit in Chrome."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.test-deps'))
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    page = browser.new_page()
    base = os.environ.get('KODENAMES_TEST_URL', 'http://127.0.0.1:8765')
    for width, height in [(1440, 900), (390, 844), (667, 375)]:
        page.set_viewport_size({'width': width, 'height': height})
        page.goto(f'{base}/?seed=fullscreen')
        page.locator('#focus-mode').click()
        page.wait_for_function('!!document.fullscreenElement')
        box = page.locator('#board').bounding_box()
        assert box['y'] >= 0 and box['y'] + box['height'] <= height, box
        assert page.locator('.card').count() == 25
        assert page.locator('#board').evaluate('e => e.scrollHeight <= e.clientHeight + 1')
        assert page.locator('.board-heading .view-switch').is_hidden()
        page.mouse.move(width / 2, height / 2)
        page.wait_for_timeout(2500)
        page.screenshot(path=f'test-artifacts/fullscreen-{width}.png')
        page.locator('#focus-reveal').click()
        page.locator('#focus-exit').focus()
        page.wait_for_timeout(2500)
        assert page.locator('#focus-exit').evaluate('e => getComputedStyle(e).opacity') == '1'
        page.keyboard.press('Enter')
        page.wait_for_function('!document.fullscreenElement')
        page.wait_for_function("!document.body.classList.contains('game-focus')")
        assert page.locator('.toolbar').is_visible()
    page.evaluate("() => { document.documentElement.requestFullscreen = () => Promise.reject(new Error('Blocked')); }")
    page.locator('#focus-mode').click()
    page.wait_for_function("document.getElementById('status').textContent.includes('blocked')")
    assert not page.evaluate("document.body.classList.contains('game-focus')")
    assert page.locator('#focus-exit').is_hidden()
    browser.close()
    print('Fullscreen passed: native entry/exit, grid fit, hidden controls, keyboard access, denied request.')
