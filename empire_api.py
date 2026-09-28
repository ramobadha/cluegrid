"""Private Empire submissions and a host-only, tab-bound reveal."""
from contextlib import closing
import hashlib
import hmac
import json
import re
import secrets
import time
import unicodedata

from flask import abort, jsonify, request

REVEAL_LIFETIME = 3 * 60


def register_empire(app, connect, payload):
    with closing(connect()) as db, db:
        db.execute('''CREATE TABLE IF NOT EXISTS empire_rooms (
            id TEXT PRIMARY KEY, host_hash TEXT NOT NULL, entries TEXT NOT NULL,
            viewer_hash TEXT, words TEXT, created_at REAL NOT NULL, expires_at REAL NOT NULL)''')
        db.execute('CREATE INDEX IF NOT EXISTS empire_expiry ON empire_rooms(expires_at)')

    def token(value):
        if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', value):
            abort(400, 'Invalid browser key. Reload and try again.')
        return hashlib.sha256(value.encode()).hexdigest()

    def row_for(db, value):
        room = value.get('room')
        if not isinstance(room, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', room):
            abort(404, 'This Empire room is unavailable. Ask the host for a new link.')
        now = time.time()
        # Deleting the row clears both the submitted entries and revealed list.
        deleted = db.execute('DELETE FROM empire_rooms WHERE id = ? AND expires_at <= ?', (room, now))
        if deleted.rowcount:
            db.commit()
        row = db.execute('SELECT * FROM empire_rooms WHERE id = ?', (room,)).fetchone()
        if row is None:
            abort(404, 'This Empire room has expired or restarted. Ask the host for a new link.')
        return row

    def is_host(row):
        auth = request.headers.get('Authorization', '')
        key = auth[7:] if auth.startswith('Bearer ') else ''
        return hmac.compare_digest(hashlib.sha256(key.encode()).hexdigest(), row['host_hash'])

    def state(row, player=None):
        entries = json.loads(row['entries'])
        return dict(closed=row['viewer_hash'] is not None, count=len(entries),
                    submitted=bool(player and player in entries), host=is_host(row),
                    clearsAt=row['expires_at'] if row['viewer_hash'] is not None else None)

    @app.post('/api/empire/rooms')
    def empire_create():
        payload()
        room, host = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        now = time.time()
        with closing(connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM empire_rooms WHERE expires_at <= ?', (now,))
            if db.execute('SELECT count(*) FROM empire_rooms').fetchone()[0] >= 1000:
                abort(503, 'Rooms are full. Please try again later.')
            if db.execute('SELECT count(*) FROM empire_rooms WHERE created_at > ?', (now - 60,)).fetchone()[0] >= 60:
                abort(429, 'Too many new rooms. Please try again in a minute.')
            db.execute('INSERT INTO empire_rooms VALUES (?, ?, ?, NULL, NULL, ?, ?)',
                       (room, token(host), '{}', now, now + 7 * 86400))
        return jsonify(room=room, hostKey=host), 201

    @app.post('/api/empire/rooms/state')
    def empire_state():
        value = payload()
        player = token(value['playerKey']) if value.get('playerKey') else None
        with closing(connect()) as db, db:
            return jsonify(state=state(row_for(db, value), player))

    @app.post('/api/empire/rooms/submit')
    def empire_submit():
        value = payload()
        player = token(value.get('playerKey'))
        word = value.get('word')
        if not isinstance(word, str):
            abort(400, 'Enter a word first.')
        word = unicodedata.normalize('NFC', word.strip())
        if not word or len(word) > 80 or any(unicodedata.category(c).startswith('C') or c in '\r\n\u2028\u2029' for c in word):
            abort(400, 'Enter one word or short name, up to 80 characters, on a single line.')
        with closing(connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            row = row_for(db, value)
            entries = json.loads(row['entries'])
            # A retry after an interrupted response confirms the same submission.
            if player in entries:
                if entries[player] != word:
                    abort(409, 'Your word is already submitted and cannot be changed.')
                return jsonify(state=state(row, player))
            if row['viewer_hash'] is not None:
                abort(409, 'Submissions are closed. The host has shown the words.')
            if len(entries) >= 100:
                abort(409, 'This room has reached 100 submissions.')
            entries[player] = word
            db.execute('UPDATE empire_rooms SET entries = ? WHERE id = ?', (json.dumps(entries), row['id']))
            return jsonify(state=state(row_for(db, value), player))

    @app.post('/api/empire/rooms/show')
    def empire_show():
        value = payload()
        viewer = token(value.get('viewerKey'))
        with closing(connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            row = row_for(db, value)
            if not is_host(row):
                abort(403, 'Only the host can show the words.')
            if row['viewer_hash'] is not None:
                if not hmac.compare_digest(viewer, row['viewer_hash']):
                    abort(403, 'The words are only available in the tab that first showed them.')
                return jsonify(words=json.loads(row['words']), state=state(row))
            words = list(json.loads(row['entries']).values())
            if not words:
                abort(409, 'Wait for at least one submission before showing the words.')
            secrets.SystemRandom().shuffle(words)
            db.execute('UPDATE empire_rooms SET viewer_hash = ?, words = ?, expires_at = ? WHERE id = ?',
                       (viewer, json.dumps(words), time.time() + REVEAL_LIFETIME, row['id']))
            return jsonify(words=words, state=state(row_for(db, value)))
