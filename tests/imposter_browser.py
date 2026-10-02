"""Separate player contexts, both modes, private reveal, refresh, and layouts."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.test-deps'))
from playwright.sync_api import sync_playwright, expect

BASE = os.environ.get('IMPOSTER_TEST_URL', 'http://127.0.0.1:8896/imposter/')
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    pages = [browser.new_context().new_page() for _ in range(4)]
    host, guest, guest2, stranger = pages
    errors = []
    for page in pages:
        page.on('pageerror', lambda error: errors.append(str(error)))
    host.goto(BASE)
    host.locator('#host-name').fill('Host')
    host.locator('#create').click()
    expect(host.locator('#settings')).to_be_visible(timeout=100000)
    invite = host.url
    for page, name in ((guest, 'Alex'), (guest2, '<img src=x>')):
        page.goto(invite)
        expect(page.locator('#join-form')).to_be_visible()
        page.locator('#player-name').fill(name)
        page.locator('#join').click()
        expect(page.locator('#join-form')).to_be_hidden()
    expect(host.locator('#player-count')).to_have_text('3 / 20 players')
    host.locator('#start').click()
    for page in pages[:3]:
        expect(page.locator('#playing')).to_be_visible()
        expect(page.locator('#secret')).to_be_hidden()
        page.locator('#peek').click()
        expect(page.locator('#secret-word')).not_to_be_empty()
    words = [page.locator('#secret-word').inner_text() for page in pages[:3]]
    assert len(set(words)) == 2
    assert all('imposter' not in word.lower() for word in words)
    guest.reload()
    expect(guest.locator('#playing')).to_be_visible()
    expect(guest.locator('#secret')).to_be_hidden()
    guest.locator('#peek').click()
    expect(guest.locator('#secret-word')).to_have_text(words[1])
    stranger.goto(invite)
    expect(stranger.locator('#spectating')).to_be_visible()
    expect(stranger.locator('#playing')).to_be_hidden()
    # Failed state fetch covers the secret and disables remote controls.
    guest.route('**/api/imposter/rooms/state', lambda route: route.abort())
    expect(guest.locator('#connection')).to_have_text('Reconnecting…', timeout=20000)
    expect(guest.locator('#secret')).to_be_hidden()
    guest.unroute('**/api/imposter/rooms/state')
    expect(guest.locator('#connection')).to_have_text('Connected', timeout=20000)
    host.locator('#end').click()
    host.locator('#confirm-end').click()
    for page in pages[:3]:
        expect(page.locator('#results')).to_be_visible()
        expect(page.locator('#result-list li')).to_have_count(3)
        assert page.locator('#result-list img').count() == 0
    host.locator('#next').click()
    expect(host.locator('#lobby')).to_be_visible()
    host.locator('#mode').select_option('blank')
    host.locator('#start').click()
    for page in pages[:3]:
        expect(page.locator('#playing')).to_be_visible()
        page.locator('#peek').click()
    assert sum(page.locator('#secret-word').inner_text() == 'You are the imposter.' for page in pages[:3]) == 1
    for width in (320, 390, 768, 1440):
        for page in (host, stranger):
            page.set_viewport_size({'width':width, 'height':900})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
        host.locator('.games-menu summary').click()
        expect(host.get_by_role('navigation', name='Games').get_by_role('link', name='Empire')).to_be_visible()
        host.locator('.games-menu summary').click()
    assert not errors, errors
    browser.close()
print('Imposter: both modes, separate devices, private cards, refresh, outage, reveal, and responsive layouts passed.')
