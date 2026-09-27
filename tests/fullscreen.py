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
        assert box['x'] == 0 and box['width'] == width and box['y'] >= 88, box
        assert abs(box['y'] + box['height'] - height) < 1, box
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
        for selector in ['#player', '#spymaster', '#meanings', '#confirm', '#swap-languages', '#share']:
            control = page.locator(selector)
            assert control.is_visible(), selector
            bounds = control.bounding_box()
            assert bounds['y'] + bounds['height'] <= box['y'], (selector, bounds)
            assert bounds['x'] >= 0 and bounds['x'] + bounds['width'] <= width, (selector, bounds)
        page.locator('#meanings').uncheck()
        assert page.locator('.meaning').first.is_hidden()
        page.locator('#meanings').check()
        language = page.locator('#main-language').input_value()
        page.locator('#swap-languages').click()
        assert page.locator('#meaning-language').input_value() == language
        page.mouse.move(width / 2, height / 2)
        page.mouse.wheel(0, 600)
        assert page.locator('#board').bounding_box() == box
        page.wait_for_timeout(2500)
        exit_box = page.locator('#focus-exit').bounding_box()
        assert exit_box['y'] + exit_box['height'] <= box['y']
        assert page.locator('#focus-exit').is_visible()
        page.screenshot(path=f'test-artifacts/fullscreen-{width}.png')
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
    assert page.locator('#focus-exit').get_attribute('aria-label') == 'Exit grid view'
    assert page.evaluate('document.documentElement.scrollHeight <= innerHeight')
    page.locator('#focus-exit').click()
    assert not page.evaluate("document.body.classList.contains('game-focus')")
    assert page.locator('#focus-exit').is_hidden()
    browser.close()
    print('Fullscreen passed: native entry/exit, grid fit, persistent exit icon, keyboard access, denied request.')
