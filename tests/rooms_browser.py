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
    expect(invalid.locator('#room-status')).to_have_text('Local \u00b7 No sync')
    expect(invalid.locator('.card:enabled')).to_have_count(25)
    # An outage detaches guests, preserves cached history, and permits local play.
    fallback = contexts[1].new_page()
    fallback.goto(host.url)
    expect(fallback.locator('#room-status')).to_have_text('Guest \u00b7 Live')
    fallback.locator('#confirm').uncheck()
    fallback_teams = fallback.evaluate("Game.generate(document.getElementById('seed').value, WORD_BANKS['gu-v2'], Math.seedrandom).cards.map(c => c.team)")
    safe = [i for i, team in enumerate(fallback_teams) if team == 'neutral']
    host.locator(f'[data-index="{safe[0]}"]').click()
    expect(fallback.locator('.revealed')).to_have_count(1)
    cached_invite = fallback.url
    fallback.route('**/api/rooms/**', lambda route: route.abort())
    expect(fallback.locator('#room-status')).to_have_text('Local \u00b7 No sync', timeout=15000)
    assert '#room=' not in fallback.url
    fallback.locator(f'[data-index="{safe[1]}"]').click()
    expect(fallback.locator('.revealed')).to_have_count(2)
    fallback.reload()
    expect(fallback.locator('.revealed')).to_have_count(2)
    # An unavailable invite restores the last successful room snapshot.
    cached = contexts[1].new_page()
    cached.route('**/api/rooms/**', lambda route: route.abort())
    cached.goto(cached_invite)
    expect(cached.locator('#room-status')).to_have_text('Local \u00b7 No sync')
    expect(cached.locator('.revealed')).to_have_count(1)
    # Failed host moves are applied locally, never written back to the old room.
    host.route('**/api/rooms/action', lambda route: route.abort())
    host.locator(f'[data-index="{safe[1]}"]').click()
    expect(host.locator('#room-status')).to_have_text('Local \u00b7 No sync')
    expect(host.locator('.revealed')).to_have_count(2)
    host.unroute('**/api/rooms/action')
    host.wait_for_timeout(1500)
    expect(host.locator('#room-status')).to_have_text('Local \u00b7 No sync')
    expect(host.locator('.revealed')).to_have_count(2)
    # Creating a fresh room carries local progress and leaves the old room alone.
    host.locator('#share').click()
    expect(host.locator('#room-status')).to_have_text('Host \u00b7 Live')
    assert host.url.split('#room=')[1] != room_id
    expect(host.locator('.revealed')).to_have_count(2)
    # Local reset, game-over and new boards remain available after an outage.
    fallback.locator('#reset').click()
    fallback.get_by_role('button', name='Restart board', exact=True).click()
    expect(fallback.locator('.revealed')).to_have_count(0)
    fallback.locator(f'[data-index="{fallback_teams.index("assassin")}"]').click()
    expect(fallback.locator('#game-result')).to_have_text('Game over')
    expect(fallback.locator('#game-result')).to_be_hidden(timeout=5000)
    fallback.locator('#new-game').click()
    expect(fallback.locator('.card:enabled')).to_have_count(25)
    # Sharing with a failed service still supplies a usable seed-only link.
    fallback.route('**/api/rooms', lambda route: route.abort())
    fallback.locator('#share').click()
    expect(fallback.locator('#share')).to_be_enabled()
    expect(fallback.locator('#status')).to_contain_text('Board link copied.')
    assert '#room=' not in fallback.evaluate('navigator.clipboard.readText()')
    # A slow room startup cannot freeze play or roll back a newer local move.
    slow = contexts[3].new_page()
    slow.goto(f'{BASE}/?seed=slow-{uuid.uuid4().hex[:8]}')
    slow.locator('#confirm').uncheck()
    pending = []
    slow.route('**/api/rooms', lambda route: pending.append(route))
    slow.locator('#share').click()
    expect(slow.locator('#share')).to_be_disabled()
    slow.wait_for_timeout(100)
    assert pending
    safe_index = slow.evaluate("Game.generate(document.getElementById('seed').value, WORD_BANKS['gu-v2'], Math.seedrandom).cards.findIndex(c => c.team === 'neutral')")
    slow.locator(f'[data-index="{safe_index}"]').click()
    response = contexts[3].request.post(f'{API}/api/rooms', data=pending[0].request.post_data_json)
    pending[0].fulfill(response=response)
    expect(slow.locator('#share')).to_be_enabled()
    expect(slow.locator('.revealed')).to_have_count(1)
    assert '#room=' not in slow.url
    assert not errors, errors
    browser.close()
    print('Private rooms passed: isolated browsers/rooms, host-only writes, refresh, local outage fallback, cached invites, failed moves, results, reset, new game, late join, and leaving.')
