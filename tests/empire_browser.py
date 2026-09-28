"""Empire: separate devices, private reveal, refresh, offline retry, mobile."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.test-deps'))
from playwright.sync_api import sync_playwright, expect

BASE = os.environ.get('EMPIRE_TEST_URL', 'http://127.0.0.1:8877/empire/')
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    host_context = browser.new_context(permissions=['clipboard-read', 'clipboard-write'])
    host = host_context.new_page()
    guest_context = browser.new_context()
    guest = guest_context.new_page()
    guest2 = browser.new_context().new_page()
    errors = []
    for page in (host, guest, guest2):
        page.on('pageerror', lambda error: errors.append(str(error)))
    host.goto(BASE)
    host.locator('#create').click()
    expect(host.locator('#host-controls')).to_be_visible(timeout=100000 if BASE.startswith('https:') else 10000)
    expect(host.locator('#show')).to_be_disabled()
    invite = host.url
    host.locator('#share').click()
    expect(host.locator('#message')).to_contain_text('Invitation copied')
    assert host.evaluate('navigator.clipboard.readText()') == invite
    guest.goto(invite)
    guest2.goto(BASE)
    guest2.locator('#invite').fill(invite)
    guest2.get_by_role('button', name='Join room', exact=True).click()
    for page in (guest, guest2):
        expect(page.locator('#word-form')).to_be_visible()
        expect(page.locator('#host-controls')).to_be_hidden()
    # Connection failures retain the draft and never pretend a word was accepted.
    guest.route('**/api/empire/rooms/submit', lambda route: route.abort())
    guest.locator('#word').fill('Mango')
    guest.locator('#submit').click()
    expect(guest.locator('#message')).to_contain_text('not been confirmed')
    expect(guest.locator('#word')).to_have_value('Mango')
    guest.unroute('**/api/empire/rooms/submit')
    guest.locator('#submit').click()
    expect(guest.locator('#waiting')).to_be_visible()
    guest.reload()
    expect(guest.locator('#word-form')).to_be_hidden()
    expect(host.locator('#count')).to_have_text('1')
    guest2.locator('#word').fill('<img src=x onerror=alert(1)>')
    guest2.locator('#submit').click()
    expect(host.locator('#count')).to_have_text('2')
    assert 'Mango' not in host.locator('body').inner_text()
    extra_host = host_context.new_page()
    extra_host.goto(invite)
    expect(extra_host.locator('#show')).to_be_enabled()
    host.locator('#show').click()
    host.locator('#confirm-reveal').click()
    expect(host.locator('#words li')).to_have_count(2)
    assert sorted(host.locator('#words li').all_text_contents()) == ['<img src=x onerror=alert(1)>', 'Mango']
    assert host.locator('#words img').count() == 0
    for page in (guest, guest2):
        expect(page.locator('#connection')).to_have_text('Entries closed')
        expect(page.locator('#words li')).to_have_count(0)
        expect(page.locator('#word-form')).to_be_hidden()
    expect(extra_host.locator('#show')).to_be_disabled()
    expect(extra_host.locator('#words li')).to_have_count(0)
    host.reload()
    expect(host.locator('#words li')).to_have_count(2)
    host.locator('#hide-words').click()
    expect(host.locator('#reveal')).to_be_hidden()
    host.locator('#show').click()
    expect(host.locator('#reveal')).to_be_visible()
    for width in (320, 390, 768, 1440):
        host.set_viewport_size({'width': width, 'height': 900})
        assert host.evaluate('document.documentElement.scrollWidth <= innerWidth')
        host.screenshot(path=f'test-artifacts/empire-host-{width}.png', full_page=True)
    guest.set_viewport_size({'width': 390, 'height': 844})
    guest.screenshot(path='test-artifacts/empire-guest.png', full_page=True)
    assert not errors, errors
    browser.close()
    print('Empire passed: host/player rooms, private words, closed submissions, tab ownership, refresh, retry, safe text, mobile layouts.')
