import concurrent.futures
import secrets
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server import create_app
from imposter_api import recommended
from imposter_words import PAIRS


class ImposterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app(Path(self.temp.name) / 'rooms.sqlite3')
        self.client = self.app.test_client()
        self.keys = [secrets.token_urlsafe(32) for _ in range(4)]
        result = self.client.post('/api/imposter/rooms', json=dict(name='Host', playerKey=self.keys[0])).json
        self.room = result['room']
        self.headers = {'Authorization': 'Bearer ' + result['hostKey']}
        for i in range(1, 4):
            self.post('join', i, name='Player ' + str(i))

    def tearDown(self):
        self.temp.cleanup()

    def post(self, path, player=0, host=False, client=None, **extra):
        return (client or self.client).post('/api/imposter/rooms/' + path,
            headers=self.headers if host else {}, json=dict(room=self.room, playerKey=self.keys[player], **extra))

    def action(self, action, **extra):
        revision = self.post('state').json['state']['revision']
        return self.post('action', host=True, action=action, revision=revision, **extra)

    def test_private_assignments_and_final_reveal(self):
        result = self.action('start', mode='different', imposters=1)
        self.assertEqual(result.status_code, 200)
        states = [self.post('state', i, host=i == 0).json['state'] for i in range(4)]
        words = [s['secret']['word'] for s in states]
        self.assertEqual(sorted(words.count(w) for w in set(words)), [1, 3])
        for s in states:
            self.assertEqual(set(s['secret']), {'word', 'meaning'})
            self.assertNotIn('results', s)
            self.assertNotIn('words', s)
            self.assertTrue(all(set(p) == {'id', 'name'} for p in s['players']))
            self.assertTrue(s['secret']['meaning'])
        stranger = self.client.post('/api/imposter/rooms/state', headers=self.headers,
            json=dict(room=self.room, playerKey=secrets.token_urlsafe(32))).json['state']
        self.assertNotIn('secret', stranger)  # Host credential alone reveals no words.
        ended = self.action('end').json['state']
        self.assertEqual(sum(p['imposter'] for p in ended['results']), 1)
        self.assertNotIn('secret', ended)
        self.assertEqual(self.post('state', 2).json['state']['results'], ended['results'])
        lobby = self.action('lobby').json['state']
        self.assertEqual(lobby['phase'], 'lobby')
        self.assertNotIn('results', lobby)
        self.assertEqual(len(lobby['players']), 4)

    def test_blank_mode_and_refresh(self):
        self.action('start', mode='blank', imposters=1)
        states = [self.post('state', i).json['state'] for i in range(4)]
        self.assertEqual(sum(s['secret']['word'] is None for s in states), 1)
        self.assertEqual(len({s['secret']['word'] for s in states if s['secret']['word']}), 1)
        self.assertEqual(states[1], self.post('state', 1).json['state'])
        self.assertEqual(self.post('join', 1, name='Player 1').status_code, 200)
        self.assertEqual(self.client.post('/api/imposter/rooms/join', json=dict(room=self.room,
            playerKey=secrets.token_urlsafe(32), name='Late')).status_code, 409)

    def test_authorization_validation_and_retries(self):
        revision = self.post('state').json['state']['revision']
        self.assertEqual(self.post('action', 1, action='start', revision=revision, mode='blank', imposters=1).status_code, 403)
        for count in (0, 2, True, '1'):
            self.assertEqual(self.action('start', mode='blank', imposters=count).status_code, 400)
        self.assertEqual(self.action('start', mode='invalid', imposters=1).status_code, 400)
        self.assertEqual(self.action('end').status_code, 409)
        self.assertEqual(self.action('start', mode='blank', imposters=1).status_code, 200)
        self.assertEqual(self.post('action', host=True, action='start', revision=revision, mode='blank', imposters=1).status_code, 409)
        self.assertEqual(self.action('lobby').status_code, 409)
        self.assertEqual(self.action('remove', target='anything').status_code, 409)

    def test_join_idempotency_names_and_capacity(self):
        for _ in range(2):
            self.assertEqual(len(self.post('join', 1, name='Player 1').json['state']['players']), 4)
        def join(display):
            return self.client.post('/api/imposter/rooms/join', json=dict(room=self.room,
                playerKey=secrets.token_urlsafe(32), name=display))
        self.assertEqual(join('player 1').status_code, 409)
        self.assertEqual(join('Bad\nname').status_code, 400)
        for i in range(16):
            self.assertEqual(join('Guest ' + str(i)).status_code, 200)
        self.assertEqual(join('Extra').status_code, 409)
        state = self.post('state').json['state']
        self.assertEqual(self.action('remove', target=state['me']).status_code, 400)
        self.assertEqual(self.action('remove', target=state['players'][1]['id']).status_code, 200)

    def test_concurrent_deals_only_start_once(self):
        revision = self.post('state').json['state']['revision']
        def deal(_):
            with self.app.test_client() as client:
                return self.post('action', host=True, client=client, action='start', revision=revision,
                                 mode='different', imposters=1).status_code
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(deal, range(2))), [200, 409])
        self.assertEqual(self.post('state').json['state']['round'], 1)

    def test_expiry_room_isolation_and_no_cache(self):
        other = self.client.post('/api/imposter/rooms', json=dict(name='Other', playerKey=self.keys[1])).json
        bad = self.client.post('/api/imposter/rooms/action', headers=self.headers, json=dict(
            room=other['room'], playerKey=self.keys[1], action='start', revision=0, mode='blank', imposters=1))
        self.assertEqual(bad.status_code, 403)
        response = self.post('state')
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        with patch('imposter_api.time.time', return_value=response.json['state']['expiresAt'] + 1):
            self.assertEqual(self.post('state').status_code, 404)

    def test_bank_and_recommendations(self):
        self.assertEqual([recommended(n) for n in (3, 6, 7, 11, 12, 20)], [1, 1, 2, 2, 3, 3])
        self.assertGreaterEqual(len(PAIRS), 60)
        self.assertEqual(len(PAIRS), len(set(PAIRS)))
        for pair in PAIRS:
            self.assertNotEqual(pair[0][0], pair[1][0])
            self.assertTrue(all(word and meaning for word, meaning in pair))
