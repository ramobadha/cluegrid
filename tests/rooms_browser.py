"""Real server + isolated browsers: live reveals, authorization, recovery, results."""
import os
import sys
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.test-deps'))
from playwright.sync_api import sync_playwright, expect

BASE = os.environ.get('KODENAMES_TEST_URL', 'http://127.0.0.1:8877')
API = os.environ.get('CLUEGRID_API_URL', BASE)

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    contexts = [browser.new_context(permissions=['clipboard-read', 'clipboard-write']) for _ in range(4)]
    host, guest_b, guest_c, other = [context.new_page() for context in contexts]
    errors = []
    for page in [host, guest_b, guest_c, other]:
        page.on('pageerror', lambda error: errors.append(str(error)))
    seed = f'room-{uuid.uuid4().hex[:12]}'
    local_url = f'{BASE}/?seed={seed}'
    host.goto(local_url)
    host.locator('#confirm').uncheck()
    # Share an already-started board; its existing reveals become room state.
    teams = host.evaluate("Game.generate(new URLSearchParams(location.search).get('seed'), WORD_BANKS['gu-v2'], Math.seedrandom).cards.map(c => c.team)")
    neutral = [index for index, team in enumerate(teams) if team == 'neutral']
    host.locator(f'[data-index="{neutral[0]}"]').click()
    host.locator('#share').click()
    expect(host.locator('#room-status')).to_have_text('Host · Live')
    invite = host.url
    assert '#room=' in invite
    assert host.evaluate('navigator.clipboard.readText()') == invite
    room_id = invite.split('#room=')[1]
    host_key = host.evaluate('(id) => localStorage.getItem(`cluegrid:host:${id}`)', room_id)
    assert host_key and host_key not in invite
    for page in [guest_b, guest_c]:
        page.goto(invite)
        expect(page.locator('#room-status')).to_have_text('Guest · Live')
        expect(page.locator('.revealed')).to_have_count(1)
        expect(page.locator('.card:disabled')).to_have_count(25)
        expect(page.locator('#reset')).to_be_disabled()
        expect(page.locator('#new-game')).to_be_disabled()
    # Same seed without the room link is still a separate, local game.
    other.goto(local_url)
    expect(other.locator('.revealed')).to_have_count(0)
    # A second room with the same seed must also remain separate.
    other.locator('#share').click()
    expect(other.locator('#room-status')).to_have_text('Host · Live')
    assert other.url != invite
    host.locator(f'[data-index="{neutral[1]}"]').click()
    for page in [host, guest_b, guest_c]:
        expect(page.locator('.revealed')).to_have_count(2)
    expect(other.locator('.revealed')).to_have_count(0)
    # UI restrictions are also enforced by the API.
    denied = contexts[1].request.post(f'{API}/api/rooms/action', data={
        'room': room_id, 'action': 'reveal', 'revision': 1, 'index': neutral[2]})
    assert denied.status == 403
    # Guests keep their own language and key view while updates arrive.
    guest_b.locator('#swap-languages').click()
    guest_b.locator('#spymaster').click()
    guest_b.get_by_role('button', name='Show key', exact=True).click()
    host.locator(f'[data-index="{neutral[2]}"]').click()
    expect(guest_b.locator('.revealed')).to_have_count(3)
    assert guest_b.locator('#main-language').input_value() == 'en'
    assert guest_b.locator('#spymaster').get_attribute('aria-pressed') == 'true'
    assert guest_c.locator('#spymaster').get_attribute('aria-pressed') == 'false'
    # Reload preserves host ownership and guests get the authoritative history.
    host.reload()
    expect(host.locator('#room-status')).to_have_text('Host · Live')
    expect(host.locator('.revealed')).to_have_count(3)
    guest_c.reload()
    expect(guest_c.locator('.revealed')).to_have_count(3)
    # A disconnected guest catches up after reconnecting.
    contexts[2].set_offline(True)
    expect(guest_c.locator('#room-status')).to_have_text('Guest · Offline', timeout=15000)
    host.locator(f'[data-index="{neutral[3]}"]').click()
    expect(host.locator('.revealed')).to_have_count(4)
    contexts[2].set_offline(False)
    expect(guest_c.locator('.revealed')).to_have_count(4, timeout=15000)
    expect(guest_c.locator('#room-status')).to_have_text('Guest · Live')
    # A failed host request cannot leave a local-only reveal on screen.
    host.route('**/api/rooms/action', lambda route: route.abort())
    host.locator(f'[data-index="{neutral[4]}"]').click()
    expect(host.locator('#room-status')).to_have_text('Host · Offline')
    expect(host.locator('.revealed')).to_have_count(4)
    host.unroute('**/api/rooms/action')
    expect(host.locator('#room-status')).to_have_text('Host · Live', timeout=15000)
    host.locator(f'[data-index="{neutral[4]}"]').click()
    expect(guest_c.locator('.revealed')).to_have_count(5)
    # Game-over appears on every participant, including a fullscreen guest.
    guest_c.set_viewport_size({'width': 390, 'height': 844})
    guest_c.locator('#focus-mode').click()
    assert guest_c.evaluate('document.documentElement.scrollWidth <= innerWidth')
    room_label = guest_c.locator('#room-status').bounding_box()
    exit_icon = guest_c.locator('#focus-exit').bounding_box()
    assert room_label['x'] + room_label['width'] <= exit_icon['x']
    host.locator(f'[data-index="{teams.index("assassin")}"]').click()
    for page in [host, guest_b, guest_c]:
        expect(page.locator('#game-result')).to_have_text('Game over')
        expect(page.locator('#game-result')).to_be_visible()
    expect(guest_c.locator('#game-result')).to_be_hidden(timeout=5000)
    expect(guest_c.locator('.card:disabled')).to_have_count(25)
    # Restart and a new board propagate on the same invitation URL.
    host.locator('#reset').click()
    host.get_by_role('button', name='Restart board', exact=True).click()
    for page in [host, guest_b, guest_c]:
        expect(page.locator('.revealed')).to_have_count(0)
    for index, team in enumerate(teams):
        if team == 'red':
            host.locator(f'[data-index="{index}"]').click()
            expect(host.locator(f'[data-index="{index}"]')).to_have_class('card red revealed')
    for page in [host, guest_b, guest_c]:
        expect(page.locator('#game-result')).to_have_text('Game over — Red team wins!')
        expect(page.locator('#game-result')).to_be_visible()
    host.locator('#new-game').click()
    expect(host.locator('.revealed')).to_have_count(0)
    new_seed = host.locator('#seed').input_value()
    assert new_seed != seed
    expect(guest_c.locator('#seed')).to_have_value(new_seed)
    assert host.url.split('#room=')[1] == room_id
    # A host in another tab must not confirm a card from a superseded round.
    host_tab = contexts[0].new_page()
    host_tab.goto(invite)
    expect(host_tab.locator('#room-status')).to_have_text('Host · Live')
    host_tab.locator('#confirm').check()
    host_tab.locator('.card').first.click()
    expect(host_tab.locator('#modal')).to_be_visible()
    host.locator('#reset').click()
    host.get_by_role('button', name='Restart board', exact=True).click()
    expect(host_tab.locator('#modal')).to_be_hidden()
    # An old copy of the link joins the current round, not the seed in its query.
    late = contexts[2].new_page()
    late.goto(invite)
    expect(late.locator('#seed')).to_have_value(new_seed)
    late.locator('#leave-room').click()
    expect(late.locator('#room-status')).to_be_hidden()
    assert '#room=' not in late.url
    expect(late.locator('.card:enabled')).to_have_count(25)
    invalid = contexts[3].new_page()
    invalid.goto(f'{local_url}#room=missing')
    expect(invalid.locator('#room-status')).to_have_text('Unavailable')
    expect(invalid.locator('.card:disabled')).to_have_count(25)
    assert not errors, errors
    browser.close()
    print('Private rooms passed: isolated browsers/rooms, host-only writes, refresh, reconnect, failed moves, results, reset, new game, late join, and leaving.')
