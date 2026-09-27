"""Room isolation, authorization, persistence, and concurrent host writes."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
import tempfile
import unittest

from server import create_app


def game(seed='namaste', history=None):
    return dict(seed=seed, version='gu-v2', teams=['red'] * 9 + ['blue'] * 8 + ['neutral'] * 7 + ['assassin'],
                history=history or [])


class RoomTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / 'rooms.sqlite3'
        self.app = create_app(self.database)
        self.client = self.app.test_client()

    def create(self, **changes):
        response = self.client.post('/api/rooms', json={'game': game(**changes)})
        self.assertEqual(response.status_code, 201)
        return response.json

    def read(self, room):
        return self.client.post('/api/rooms/state', json={'room': room['room']})

    def act(self, room, action='reveal', revision=0, **values):
        return self.client.post('/api/rooms/action',
                                json=dict(room=room['room'], action=action, revision=revision, **values),
                                headers={'Authorization': f"Bearer {room['hostKey']}"})

    def test_rooms_with_same_seed_are_isolated_and_host_key_is_private(self):
        first, second = self.create(), self.create()
        self.assertNotEqual(first['room'], second['room'])
        self.assertEqual(self.act(first, index=0).json['state']['history'], [0])
        response = self.read(first)
        self.assertEqual(response.json['state']['history'], [0])
        self.assertEqual(self.read(second).json['state']['history'], [])
        self.assertNotIn(first['hostKey'], response.get_data(as_text=True))
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(self.client.get('/api/rooms').status_code, 404)
        self.assertEqual(self.client.post('/api/rooms/state', json={'room': 'unknown'}).status_code, 404)

    def test_guest_or_other_host_cannot_reveal_reset_or_replace_board(self):
        first, other = self.create(), self.create()
        for action in ('reveal', 'reset', 'new'):
            for key in ('', other['hostKey']):
                response = self.client.post('/api/rooms/action', json=dict(
                    room=first['room'], action=action, revision=0, index=0, game=game('other')),
                    headers={'Authorization': f'Bearer {key}'})
                self.assertEqual(response.status_code, 403)
        self.assertEqual(self.read(first).json['state']['revision'], 0)

    def test_resume_current_state_after_server_restart(self):
        room = self.create(history=[0, 10])
        self.act(room, index=18)
        resumed = create_app(self.database).test_client()
        state = resumed.post('/api/rooms/state', json={'room': room['room']}).json['state']
        self.assertEqual(state['history'], [0, 10, 18])

    def test_reset_and_new_board_keep_the_room(self):
        room = self.create(history=[1, 2])
        state = self.act(room, 'reset').json['state']
        self.assertEqual((state['history'], state['round'], state['revision']), ([], 1, 1))
        state = self.act(room, 'new', revision=1, game=game('next')).json['state']
        self.assertEqual((state['seed'], state['round'], state['revision']), ('next', 2, 2))
        self.assertEqual(self.read(room).json['state'], state)

    def test_terminal_results_stop_further_reveals(self):
        for moves, index, result in [([*range(8)], 8, 'red'), ([*range(9, 16)], 16, 'blue'), ([], 24, 'assassin')]:
            room = self.create(history=moves)
            state = self.act(room, index=index).json['state']
            self.assertEqual(state['winner'], result)
            self.assertEqual(self.act(room, revision=1, index=23).status_code, 409)

    def test_concurrent_or_stale_writes_do_not_overwrite_moves(self):
        room = self.create()
        with ThreadPoolExecutor(max_workers=2) as pool:
            def reveal(index):
                with self.app.test_client() as client:
                    return client.post('/api/rooms/action', json=dict(room=room['room'], action='reveal',
                        revision=0, index=index), headers={'Authorization': f"Bearer {room['hostKey']}"})
            results = list(pool.map(reveal, [0, 1]))
        self.assertEqual(sorted(response.status_code for response in results), [200, 409])
        state = self.read(room).json['state']
        self.assertEqual(len(state['history']), 1)
        missing = next(index for index in [0, 1] if index not in state['history'])
        self.assertEqual(self.act(room, revision=state['revision'], index=missing).json['state']['revision'], 2)

    def test_malformed_requests_and_expired_rooms(self):
        for value in [None, {}, {'game': game(history=[True])}, {'game': game(history=[24, 0])},
                      {'game': game(history=[0, 0])}, {'game': {**game(), 'teams': ['red'] * 25}}]:
            self.assertIn(self.client.post('/api/rooms', json=value).status_code, [400, 415])
        room = self.create()
        for index in (-1, 25, True, '0', None):
            self.assertEqual(self.act(room, index=index).status_code, 400)
        import sqlite3
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('UPDATE rooms SET expires_at = 0')
        self.assertEqual(self.read(room).status_code, 404)
        self.assertEqual(self.act(room, index=0).status_code, 404)

    def test_only_configured_websites_can_use_cross_origin_api(self):
        client = create_app(self.database, allowed_origins=['https://example.github.io']).test_client()
        allowed = {'Origin': 'https://example.github.io', 'Access-Control-Request-Method': 'POST',
                   'Access-Control-Request-Headers': 'content-type,authorization'}
        preflight = client.options('/api/rooms/action', headers=allowed)
        self.assertEqual(preflight.status_code, 200)
        self.assertEqual(preflight.headers['Access-Control-Allow-Origin'], allowed['Origin'])
        self.assertIn('Authorization', preflight.headers['Access-Control-Allow-Headers'])
        created = client.post('/api/rooms', json={'game': game()}, headers=allowed)
        self.assertEqual(created.status_code, 201)
        blocked = client.post('/api/rooms/state', json={'room': created.json['room']},
                              headers={'Origin': 'https://unrelated.example'})
        self.assertEqual(blocked.status_code, 403)
        self.assertNotIn('Access-Control-Allow-Origin', blocked.headers)


if __name__ == '__main__':
    unittest.main()
