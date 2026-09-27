"""Browser smoke test. Install Playwright and run with a server on port 8765."""
from pathlib import Path
import os
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.test-deps'))
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1100})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    base_url = os.environ.get('KODENAMES_TEST_URL', 'http://127.0.0.1:8765')
    page.goto(f'{base_url}/?seed=namaste')
    page.wait_for_load_state('load')
    assert page.locator('.card').count() == 25
    assert page.locator('.card.red,.card.blue,.card.assassin').count() == 0
    assert page.locator('#main-language').input_value() == 'gu'
    assert page.locator('#meaning-language').input_value() == 'en'
    gujarati_terms = page.locator('.term').all_text_contents()
    english_meanings = page.locator('.meaning').all_text_contents()
    page.locator('#focus-mode').click()
    page.wait_for_function("document.body.classList.contains('game-focus')")
    assert page.locator('.toolbar').is_hidden()
    assert page.locator('.card').count() == 25
    assert page.locator('#seed').input_value() == 'namaste'
    assert page.evaluate('!!document.fullscreenElement')
    page.mouse.move(500, 500)
    page.wait_for_timeout(2500)
    assert page.locator('#focus-exit').evaluate('e => getComputedStyle(e).opacity') == '1'
    page.locator('#focus-exit').click()
    page.wait_for_function("!document.body.classList.contains('game-focus')")
    assert page.locator('.toolbar').is_visible()
    page.locator('#swap-languages').click()
    assert page.locator('#main-language').input_value() == 'en'
    assert page.locator('#meaning-language').input_value() == 'gu'
    assert page.locator('.term').all_text_contents() == english_meanings
    assert page.locator('.meaning').all_text_contents() == gujarati_terms
    assert 'lang=en' in page.url and 'meaning=gu' in page.url
    page.reload(); page.wait_for_load_state('load')
    assert page.locator('.term').all_text_contents() == english_meanings
    page.locator('#swap-languages').click()
    assert page.locator('#main-language').input_value() == 'gu'
    assert page.locator('#meaning-language').input_value() == 'en'
    assert page.locator('.term').all_text_contents() == gujarati_terms
    page.goto(f'{base_url}/?seed=namaste&lang=en&meaning=en')
    page.wait_for_load_state('load')
    assert page.locator('#main-language').input_value() != page.locator('#meaning-language').input_value()
    page.goto(f'{base_url}/?seed=namaste&lang=gu&meaning=en')
    page.wait_for_load_state('load')
    terms = page.locator('.term').all_text_contents()
    page.locator('#meanings').uncheck()
    assert page.locator('.meaning:visible').count() == 0
    page.locator('#meanings').check()
    page.locator('.card').first.click()
    assert page.locator('#modal').is_visible()
    page.get_by_role('button', name='Cancel', exact=True).click()
    assert page.locator('.revealed').count() == 0
    page.locator('.card').first.click()
    page.get_by_role('button', name='Reveal card', exact=True).click()
    assert page.locator('.revealed').count() == 1
    page.reload(); page.wait_for_load_state('load')
    assert page.locator('.revealed').count() == 1
    page.locator('#spymaster').click()
    page.get_by_role('button', name='Show key', exact=True).click()
    assert page.locator('.card.assassin').count() == 1
    assert page.locator('.revealed.synced-reveal').count() == 1
    assert page.locator('.revealed .term').evaluate('e => getComputedStyle(e).color') == 'rgb(0, 0, 0)'
    assert all(label in ['', '\u2713'] for label in page.locator('.identity').all_text_contents())
    assert page.locator('.card:not(.revealed).synced-reveal').count() == 0
    page.locator('#swap-languages').click()
    assert page.locator('#spymaster').get_attribute('aria-pressed') == 'true'
    assert page.locator('.revealed').count() == 1
    page.locator('#swap-languages').click()
    page.locator('#player').click()
    assert page.locator('.card:not(.revealed).red,.card:not(.revealed).blue,.card:not(.revealed).assassin').count() == 0
    page.locator('#reset').click(); page.get_by_role('button', name='Restart board', exact=True).click()
    assert page.locator('.revealed').count() == 0
    assert terms == page.locator('.term').all_text_contents()
    assert page.locator('#end-turn, #turn-heading, #mobile-end-turn').count() == 0
    page.locator('#help').click(); assert page.locator('#modal').is_visible()
    page.keyboard.press('Escape')
    page.locator('#seed').fill('  TEST-SEED  '); page.locator('#seed').press('Enter')
    assert page.locator('#seed').input_value() == 'test-seed'
    assert terms != page.locator('.term').all_text_contents()
    second = browser.new_page()
    second.goto(page.url); second.wait_for_load_state('load')
    assert second.locator('.term').all_text_contents() == page.locator('.term').all_text_contents()
    second.close()
    Path('test-artifacts').mkdir(exist_ok=True)
    page.screenshot(path='test-artifacts/desktop.png', full_page=True)
    for width in [375, 768]:
        page.set_viewport_size({'width': width, 'height': 900})
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        assert page.locator('.card').count() == 25
        page.screenshot(path=f'test-artifacts/mobile-{width}.png', full_page=True)

    # Old invite links retain the original vocabulary and saved progress.
    page.set_viewport_size({'width': 1440, 'height': 1100})
    page.goto(f'{base_url}/?seed=namaste&v=gu-v1')
    page.wait_for_load_state('load')
    assert page.locator('#word-bank-size').inner_text() == '180 words to explore'
    legacy_terms = page.locator('.term').all_text_contents()
    expected = page.evaluate("Game.generate('namaste', GUJARATI_WORD_BANKS['gu-v1'], Math.seedrandom).cards.map(c => c.term)")
    assert legacy_terms == expected
    page.evaluate("localStorage.setItem('kodenames:gu-v1:namaste', JSON.stringify({history: ['end', 0]}))")
    page.reload(); page.wait_for_load_state('load')
    assert page.locator('.revealed').count() == 1
    page.locator('#new-game').click()
    page.locator('#modal-actions').get_by_role('button', name='New game', exact=True).click()
    assert 'v=gu-v2' in page.url
    assert page.locator('#word-bank-size').inner_text() == '2,150 words to explore'
    page.goto(f'{base_url}/?seed=namaste&v=gu-v1')
    page.wait_for_load_state('load')
    assert page.locator('.term').all_text_contents() == legacy_terms
    assert page.locator('.revealed').count() == 1

    # Exercise the real renderer with the longest entries, not just a fortunate random seed.
    page.goto(f'{base_url}/?seed=long-word-layout&v=gu-v2')
    page.wait_for_load_state('load')
    page.evaluate("GUJARATI_WORD_BANKS['gu-v2'] = [...GUJARATI_WORDS].sort((a,b) => b.term.length-a.term.length).slice(0,25)")
    page.locator('#new-game').click()
    for width in [320, 375, 768, 1440]:
        page.set_viewport_size({'width': width, 'height': 1000})
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        overflow = page.locator('.term,.meaning').evaluate_all('(nodes) => nodes.filter(n => n.scrollWidth > n.clientWidth + 1).map(n => n.textContent)')
        assert not overflow, (width, overflow)
    page.set_viewport_size({'width': 375, 'height': 1000})
    page.screenshot(path='test-artifacts/long-words-mobile.png', full_page=True)
    page.goto(f'{base_url}/?seed=version-check&v=unknown-version')
    page.wait_for_load_state('load')
    assert 'unsupported vocabulary version' in page.locator('#status').inner_text()
    assert 'v=gu-v2' in page.url
    # Results appear over the board in fullscreen and disappear after three seconds.
    for team in ['red', 'blue', 'assassin']:
        page.goto(f'{base_url}/?seed=result-{team}')
        page.wait_for_load_state('load')
        page.locator('#confirm').uncheck()
        indices = page.evaluate("""team => Game.generate(`result-${team}`, WORD_BANKS['gu-v2'], Math.seedrandom)
            .cards.flatMap((card, index) => card.team === team ? [index] : [])""", team)
        page.locator('#focus-mode').click()
        page.wait_for_function("document.body.classList.contains('game-focus')")
        page.clock.install()
        for index in indices:
            page.locator(f'.card[data-index="{index}"]').click()
        if team == 'assassin':
            assert page.locator('#modal').is_hidden()
            expected = 'Game over'
        else:
            expected = f'Game over — {team.title()} team wins!'
        assert page.locator('#game-result').inner_text() == expected
        assert page.locator('#game-result').is_visible()
        assert page.locator('.card:disabled').count() == 25
        page.clock.fast_forward(2900)
        assert page.locator('#game-result').is_visible()
        page.clock.fast_forward(100)
        assert page.locator('#game-result').is_hidden()
        assert page.locator('#status').inner_text() == expected
        page.locator('#focus-exit').click()
        page.wait_for_function("!document.body.classList.contains('game-focus')")
    assert not errors, errors
    browser.close()
    print('Browser checks passed: gameplay, legacy seeds and progress, new-bank upgrade, unknown-version warning, long terms at 320/375/768/1440px; no JS errors.')
