"""Touch gameplay, mobile layout, and cross-engine checks against a running preview."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.test-deps'))
sys.stdout.reconfigure(line_buffering=True)
from playwright.sync_api import sync_playwright

BASE = os.environ.get('KODENAMES_TEST_URL', 'http://127.0.0.1:8917')
SIZES = [(320, 568), (360, 640), (375, 667), (390, 844), (412, 915),
         (430, 932), (540, 720), (768, 1024), (820, 1180), (1024, 1366),
         (568, 320), (667, 375), (844, 390), (932, 430)]
ARTIFACTS = Path('test-artifacts')
ARTIFACTS.mkdir(exist_ok=True)


def check_layout(page, width, height):
    page.set_viewport_size({'width': width, 'height': height})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (width, height, 'page overflow')
    assert page.locator('.card').count() == 25
    assert page.locator('.board').evaluate("e => getComputedStyle(e).gridTemplateColumns.split(' ').length") == 5
    overflow = page.locator('.term,.meaning,.identity').evaluate_all('''nodes => nodes.filter(n =>
        n.clientWidth && n.scrollWidth > n.clientWidth + 1).map(n => n.textContent)''')
    assert not overflow, (width, height, overflow)
    small = page.locator('button:visible,.toggle:visible').evaluate_all('''nodes => nodes.filter(n => {
        const r = n.getBoundingClientRect(); return r.width < 43.5 || r.height < 43.5;
    }).map(n => ({text: n.textContent, w: n.offsetWidth, h: n.offsetHeight}))''')
    assert not small, (width, height, small)
    assert page.locator('#main-language').is_visible()
    assert page.locator('#meaning-language').is_visible()
    assert page.locator('#main-language').evaluate('e => e.getBoundingClientRect().height') >= 43.5
    assert page.locator('#meaning-language').evaluate('e => e.getBoundingClientRect().height') >= 43.5
    assert float(page.locator('#seed').evaluate('e => getComputedStyle(e).fontSize').replace('px', '')) >= 16


with sync_playwright() as p:
    for engine in os.environ.get('KODENAMES_TEST_ENGINES', 'chromium,webkit,firefox').split(','):
        browser_type = getattr(p, engine)
        browser = browser_type.launch(**({'channel': 'chrome'} if engine == 'chromium' else {}), headless=True)
        context_options = {'viewport': {'width': 390, 'height': 844}, 'has_touch': True, 'device_scale_factor': 2}
        if engine != 'firefox':
            context_options['is_mobile'] = True
        context = browser.new_context(**context_options)
        page = context.new_page()
        errors = []
        external_requests = []
        pending = set()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: external_requests.append(request.url) if not request.url.startswith(BASE) else None)
        page.on('request', lambda request: pending.add(request.url))
        page.on('requestfinished', lambda request: pending.discard(request.url))
        page.on('requestfailed', lambda request: pending.discard(request.url))
        page.goto(f'{BASE}/?seed=mobile-check&v=gu-v2', wait_until='load')
        page.evaluate('document.fonts.ready')
        assert page.locator('#main-language').input_value() == 'gu'
        assert page.locator('#meaning-language').input_value() == 'en'
        for width, height in SIZES:
            check_layout(page, width, height)

        page.set_viewport_size({'width': 390, 'height': 844})
        page.evaluate('scrollTo(0, 0)')
        page.locator('#focus-mode').tap()
        page.wait_for_function("document.body.classList.contains('game-focus')")
        assert page.locator('#seed-form').is_hidden()
        assert page.locator('.scores').is_visible()
        assert page.locator('#focus-exit').is_visible()
        assert page.locator('.card').count() == 25
        for width, height in [(568, 320), (667, 375), (844, 390), (390, 844)]:
            # Firefox exits native fullscreen when automation resizes its window.
            page.locator('#focus-exit').tap()
            page.wait_for_function("!document.body.classList.contains('game-focus')")
            page.set_viewport_size({'width': width, 'height': height})
            page.locator('#focus-mode').tap()
            page.wait_for_function("document.body.classList.contains('game-focus')")
            page.wait_for_function('Math.abs(document.querySelector(".game").getBoundingClientRect().height - innerHeight) < 1')
            box = page.locator('#board').bounding_box()
            viewport = page.evaluate('({width: innerWidth, height: innerHeight})')
            assert abs(box['width'] - viewport['width']) < 1 and abs(box['y'] + box['height'] - viewport['height']) < 1, (engine, box)
            assert page.evaluate('document.documentElement.scrollHeight <= innerHeight')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert page.locator('.game').evaluate('e => e.scrollHeight <= e.clientHeight')
        page.locator('#focus-exit').tap()
        page.wait_for_function("!document.body.classList.contains('game-focus')")
        assert page.locator('#seed-form').is_visible()
        page.screenshot(path=str(ARTIFACTS / f'{engine}-phone.png'), full_page=True)
        page.locator('.card').first.tap()
        assert page.locator('#modal').is_visible()
        assert page.locator('.dialog-word').inner_text() == page.locator('.card .term').first.inner_text()
        assert page.locator('.dialog-meaning').inner_text() == page.locator('.card .meaning').first.inner_text()
        page.screenshot(path=str(ARTIFACTS / f'{engine}-confirm.png'))
        page.get_by_role('button', name='Cancel', exact=True).tap()
        assert page.locator('.revealed').count() == 0
        page.locator('.card').first.tap()
        page.get_by_role('button', name='Reveal card', exact=True).tap()
        assert page.locator('.revealed').count() == 1
        assert page.locator('#red-score').is_visible()
        assert page.locator('#blue-score').is_visible()
        page.locator('#reset').tap()
        page.get_by_role('button', name='Restart board', exact=True).tap()
        page.locator('#spymaster').tap()
        page.get_by_role('button', name='Show key', exact=True).tap()
        assert page.locator('.card.assassin').count() == 1
        for width, height in [(320, 568), (390, 844), (667, 375)]:
            check_layout(page, width, height)
        page.locator('#player').tap()

        # The two language selectors swap roles without changing the seeded board.
        gujarati_words = page.locator('.term').all_text_contents()
        english_words = page.locator('.meaning').all_text_contents()
        page.locator('#main-language').select_option('en')
        assert page.locator('#main-language').input_value() == 'en'
        assert page.locator('#meaning-language').input_value() == 'gu'
        assert page.locator('.term').all_text_contents() == english_words
        assert page.locator('.meaning').all_text_contents() == gujarati_words
        assert 'lang=en' in page.url and 'meaning=gu' in page.url
        page.reload(wait_until='load')
        assert page.locator('.term').all_text_contents() == english_words
        page.locator('#meaning-language').select_option('en')
        assert page.locator('#main-language').input_value() == 'gu'
        assert page.locator('#meaning-language').input_value() == 'en'
        assert page.locator('.term').all_text_contents() == gujarati_words

        # Preferences persist, and hiding meanings also hides the confirmation gloss.
        page.locator('#meanings').uncheck()
        page.reload(wait_until='load')
        assert not page.locator('#meanings').is_checked()
        page.locator('.card').first.tap()
        assert page.locator('.dialog-meaning').count() == 0
        page.get_by_role('button', name='Cancel', exact=True).tap()
        page.locator('#meanings').check()

        # Long terms use the actual game renderer, including revealed identities.
        page.goto(f'{BASE}/?seed=long-mobile-check&v=gu-v2')
        page.wait_for_load_state('load')
        page.evaluate("GUJARATI_WORD_BANKS['gu-v2'] = [...GUJARATI_WORDS].sort((a,b) => b.term.length-a.term.length).slice(0,25)")
        page.locator('#new-game').tap()
        for width, height in SIZES:
            check_layout(page, width, height)
        page.set_viewport_size({'width': 390, 'height': 844})
        page.locator('#help').tap()
        for width, height in [(320, 568), (568, 320), (390, 360)]:
            page.set_viewport_size({'width': width, 'height': height})
            box = page.locator('#modal').bounding_box()
            assert box['x'] >= -1 and box['y'] >= -1
            assert box['y'] + box['height'] <= height + 1
            assert page.locator('#modal').evaluate('e => e.scrollWidth <= e.clientWidth + 1')
        page.get_by_role('button', name='Close dialog').tap()
        assert not errors, (engine, errors)
        assert not external_requests, (engine, external_requests)
        browser.close()
        print(f'{engine}: passed 14 screen sizes, touch gameplay, scores, spymaster, preferences, long words, and short-screen dialogs')
