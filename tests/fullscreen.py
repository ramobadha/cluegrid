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
    for width, height in [(1440, 900), (390, 844), (568, 320), (667, 375), (844, 390)]:
        page.set_viewport_size({'width': width, 'height': height})
        page.goto(f'{base}/?seed=fullscreen')
        page.locator('#focus-mode').click()
        page.wait_for_function('!!document.fullscreenElement')
        box = page.locator('#board').bounding_box()
        assert box == {'x': 0, 'y': 28, 'width': width, 'height': height - 28}, box
        assert page.evaluate('document.documentElement.scrollHeight <= innerHeight')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert page.locator('.game').evaluate('e => e.scrollHeight <= e.clientHeight')
        scores = page.locator('.scores').bounding_box()
        assert scores['y'] + scores['height'] <= box['y'], scores
        first = page.locator('.card').first.bounding_box()
        last = page.locator('.card').last.bounding_box()
        assert abs(first['x'] - box['x']) < 1 and abs(first['y'] - box['y']) < 1, first
        if width > height:
            assert first['width'] > first['height'], first
        assert abs(last['x'] + last['width'] - box['x'] - box['width']) < 1, last
        assert abs(last['y'] + last['height'] - box['y'] - box['height']) < 1, last
        assert page.locator('.card').count() == 25
        assert page.locator('#board').evaluate('e => e.scrollHeight <= e.clientHeight + 1')
        assert page.locator('.board-heading .view-switch').is_hidden()
        page.mouse.move(width / 2, height / 2)
        page.mouse.wheel(0, 600)
        assert page.locator('#board').bounding_box() == box
        page.wait_for_timeout(2500)
        assert page.locator('#focus-reveal').evaluate('e => getComputedStyle(e).opacity') == '0'
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
    page.wait_for_function("document.body.classList.contains('game-focus')")
    assert not page.evaluate('!!document.fullscreenElement')
    assert page.locator('#focus-exit').inner_text() == 'Exit grid view'
    assert page.evaluate('document.documentElement.scrollHeight <= innerHeight')
    page.locator('#focus-exit').click()
    assert not page.evaluate("document.body.classList.contains('game-focus')")
    assert page.locator('#focus-exit').is_hidden()
    browser.close()
    print('Fullscreen passed: native entry/exit, grid fit, hidden controls, keyboard access, denied request.')
