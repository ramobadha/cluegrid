import concurrent.futures
from contextlib import closing
import secrets
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from server import create_app


class EmpireTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / 'rooms.sqlite3'
        self.app = create_app(self.database)
        self.client = self.app.test_client()
        self.created = self.client.post('/api/empire/rooms', json={}).get_json()
        self.room = self.created['room']
        self.host = {'Authorization': 'Bearer ' + self.created['hostKey']}
        self.player = secrets.token_urlsafe(32)
        self.viewer = secrets.token_urlsafe(32)

    def tearDown(self):
        self.temp.cleanup()

    def post(self, path, **body):
        return self.client.post('/api/empire/rooms/' + path, json={'room': self.room, **body})

    def show(self, viewer=None, client=None):
        return (client or self.client).post('/api/empire/rooms/show', headers=self.host,
                    json={'room': self.room, 'viewerKey': viewer or self.viewer})

    def test_private_list_and_single_viewer(self):
        self.assertEqual(self.post('submit', playerKey=self.player, word='secret mango').status_code, 200)
        self.assertNotIn('secret mango', self.post('state').get_data(as_text=True))
        host_state = self.client.post('/api/empire/rooms/state', headers=self.host, json={'room': self.room})
        self.assertNotIn('secret mango', host_state.get_data(as_text=True))
        self.assertTrue(host_state.json['state']['host'])
        self.assertEqual(self.post('show', viewerKey=self.viewer).status_code, 403)
        result = self.show()
        self.assertEqual(result.json['words'], ['secret mango'])
        self.assertEqual(self.show().json['words'], ['secret mango'])
        self.assertEqual(self.show(secrets.token_urlsafe(32)).status_code, 403)
        self.assertNotIn('secret mango', self.post('state').get_data(as_text=True))
        self.assertNotIn('words', self.post('state').json['state'])
        self.assertEqual(self.post('submit', playerKey=secrets.token_urlsafe(32), word='late').status_code, 409)
        self.assertEqual(result.headers['Cache-Control'], 'no-store')

    def test_room_and_words_are_deleted_three_minutes_after_show(self):
        self.post('submit', playerKey=self.player, word='temporary secret')
        revealed_at = time.time()
        with patch('empire_api.time.time', return_value=revealed_at):
            result = self.show()
        self.assertAlmostEqual(result.json['state']['clearsAt'], revealed_at + 180)
        with patch('empire_api.time.time', return_value=revealed_at + 179):
            self.assertEqual(self.post('state').status_code, 200)
        with patch('empire_api.time.time', return_value=revealed_at + 180):
            self.assertEqual(self.post('state').status_code, 404)
        import sqlite3
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM empire_rooms WHERE id = ?', (self.room,)).fetchone()[0], 0)

    def test_submission_retry_is_idempotent_and_immutable(self):
        for _ in range(2):
            response = self.post('submit', playerKey=self.player, word='moon')
            self.assertEqual(response.json['state']['count'], 1)
        self.assertEqual(self.post('submit', playerKey=self.player, word='sun').status_code, 409)
        self.show()
        self.assertEqual(self.post('submit', playerKey=self.player, word='moon').status_code, 200)

    def test_validation_and_empty_show(self):
        self.assertEqual(self.show().status_code, 409)
        for word in ['', '  ', 'a\nb', 'x' * 81, 7, 'a\u2028b']:
            self.assertEqual(self.post('submit', playerKey=self.player, word=word).status_code, 400)
        self.assertEqual(self.post('submit', playerKey='bad', word='valid').status_code, 400)
        self.assertEqual(self.post('submit', playerKey=self.player, word='ગુજરાત').status_code, 200)

    def test_rooms_are_separate(self):
        other = self.client.post('/api/empire/rooms', json={}).json
        self.post('submit', playerKey=self.player, word='hidden')
        result = self.client.post('/api/empire/rooms/state', json={'room': other['room']})
        self.assertEqual(result.json['state']['count'], 0)
        denied = self.client.post('/api/empire/rooms/show',
            json={'room': self.room, 'viewerKey': self.viewer},
            headers={'Authorization': 'Bearer ' + other['hostKey']})
        self.assertEqual(denied.status_code, 403)

    def test_only_one_simultaneous_viewer_wins(self):
        self.post('submit', playerKey=self.player, word='crown')
        def reveal(_):
            with self.app.test_client() as client:
                return self.show(secrets.token_urlsafe(32), client).status_code
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(reveal, range(2))), [200, 403])

    def test_submit_and_close_are_atomic(self):
        self.post('submit', playerKey=self.player, word='first')
        def submit():
            with self.app.test_client() as client:
                return client.post('/api/empire/rooms/submit', json={
                    'room': self.room, 'playerKey': secrets.token_urlsafe(32), 'word': 'racing'})
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            entry = pool.submit(submit)
            shown = pool.submit(self.show, self.viewer, self.app.test_client())
            submission, reveal = entry.result(), shown.result()
        self.assertEqual('racing' in reveal.json['words'], submission.status_code == 200)
        self.assertIn(submission.status_code, (200, 409))


if __name__ == '__main__':
    unittest.main()
