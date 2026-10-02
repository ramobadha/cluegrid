"""Server-assigned private words; the host has no extra access to secrets."""
from contextlib import closing
import hashlib
import hmac
import json
import re
import secrets
import time
import unicodedata

from flask import abort, jsonify, request
from imposter_words import PAIRS


def recommended(count):
    return 1 if count <= 6 else 2 if count <= 11 else 3


def register_imposter(app, connect, payload):
    with closing(connect()) as db, db:
        db.execute('''CREATE TABLE IF NOT EXISTS imposter_rooms (
            id TEXT PRIMARY KEY, host_hash TEXT NOT NULL, game TEXT NOT NULL,
            created_at REAL NOT NULL, expires_at REAL NOT NULL)''')
        db.execute('CREATE INDEX IF NOT EXISTS imposter_expiry ON imposter_rooms(expires_at)')

    def key(value):
        if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', value):
            abort(400, 'Invalid browser key. Reload and try again.')
        return hashlib.sha256(value.encode()).hexdigest()

    def name(value):
        if not isinstance(value, str):
            abort(400, 'Enter your name.')
        value = unicodedata.normalize('NFC', value.strip())
        if not value or len(value) > 30 or any(unicodedata.category(c).startswith('C') or c in '\u2028\u2029' for c in value):
            abort(400, 'Use a name of 1–30 characters on one line.')
        return value

    def host(row):
        auth = request.headers.get('Authorization', '')
        return hmac.compare_digest(hashlib.sha256(auth.removeprefix('Bearer ').encode()).hexdigest(), row['host_hash'])

    def room_for(db, value):
        room = value.get('room')
        if not isinstance(room, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', room):
            abort(404, 'This Imposter room is unavailable.')
        row = db.execute('SELECT * FROM imposter_rooms WHERE id = ? AND expires_at > ?', (room, time.time())).fetchone()
        if row is None:
            abort(404, 'This room has expired or the server restarted. Create a new room.')
        return row, json.loads(row['game'])

    def snapshot(row, game, player):
        members = game['players']
        me = next((p for p in members if p['key'] == player), None)
        state = dict(host=host(row), phase=game['phase'], revision=game['revision'], round=game['round'],
                     players=[dict(id=p['id'], name=p['name']) for p in members],
                     me=me['id'] if me else None, mode=game['mode'], imposters=game['imposters'],
                     recommended=recommended(len(members)), expiresAt=row['expires_at'])
        if game['phase'] == 'playing' and me:
            # Different-word mode deliberately does not tell either side its role.
            state['secret'] = dict(word=me['word'], meaning=me['meaning'])
        if game['phase'] == 'ended':
            state['results'] = [dict(name=p['name'], imposter=p['imposter'], word=p['word']) for p in members]
            state['words'] = game['words']
        return state

    @app.post('/api/imposter/rooms')
    def imposter_create():
        value = payload()
        player, display = key(value.get('playerKey')), name(value.get('name'))
        room, host_key = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        now = time.time()
        game = dict(phase='lobby', revision=0, round=0, mode='different', imposters=0,
                    players=[dict(key=player, id=secrets.token_urlsafe(12), name=display)], used=[])
        with closing(connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM imposter_rooms WHERE expires_at <= ?', (now,))
            if db.execute('SELECT count(*) FROM imposter_rooms').fetchone()[0] >= 1000:
                abort(503, 'Rooms are full. Try again later.')
            if db.execute('SELECT count(*) FROM imposter_rooms WHERE created_at > ?', (now - 60,)).fetchone()[0] >= 60:
                abort(429, 'Too many new rooms. Try again in a minute.')
            db.execute('INSERT INTO imposter_rooms VALUES (?, ?, ?, ?, ?)',
                       (room, key(host_key), json.dumps(game), now, now + 7 * 86400))
        return jsonify(room=room, hostKey=host_key), 201

    @app.post('/api/imposter/rooms/state')
    def imposter_state():
        value = payload()
        player = key(value.get('playerKey'))
        with closing(connect()) as db:
            row, game = room_for(db, value)
            return jsonify(state=snapshot(row, game, player))

    @app.post('/api/imposter/rooms/join')
    def imposter_join():
        value = payload()
        player, display = key(value.get('playerKey')), name(value.get('name'))
        with closing(connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            row, game = room_for(db, value)
            if any(p['key'] == player for p in game['players']):
                return jsonify(state=snapshot(row, game, player))
            if game['phase'] != 'lobby':
                abort(409, 'A round is in progress. Wait for the host to reopen the lobby.')
            if len(game['players']) >= 20:
                abort(409, 'This room already has 20 players.')
            if any(p['name'].casefold() == display.casefold() for p in game['players']):
                abort(409, 'That name is taken. Add an initial or choose another name.')
            game['players'].append(dict(key=player, id=secrets.token_urlsafe(12), name=display))
            game['revision'] += 1
            db.execute('UPDATE imposter_rooms SET game = ? WHERE id = ?', (json.dumps(game), row['id']))
            return jsonify(state=snapshot(row, game, player))

    @app.post('/api/imposter/rooms/action')
    def imposter_action():
        value = payload()
        player = key(value.get('playerKey'))
        with closing(connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            row, game = room_for(db, value)
            if not host(row):
                abort(403, 'Only the host can manage the round.')
            # Optimistic concurrency prevents retries/double clicks from dealing twice.
            if type(value.get('revision')) is not int or value['revision'] != game['revision']:
                abort(409, 'The room changed. Refresh its state and try again.')
            action = value.get('action')
            if action == 'start':
                count = len(game['players'])
                if game['phase'] != 'lobby' or not 3 <= count <= 20:
                    abort(409, 'Start from the lobby with 3–20 players.')
                mode, imposters = value.get('mode'), value.get('imposters')
                if mode not in ('different', 'blank') or type(imposters) is not int or not 1 <= imposters <= (count - 1) // 2:
                    abort(400, 'Choose a mode and keep imposters below half the players.')
                available = [i for i in range(len(PAIRS)) if i not in game['used']]
                if not available:
                    available = list(range(len(PAIRS)))
                    game['used'] = []
                pair_id = secrets.choice(available)
                game['used'].append(pair_id)
                words = list(PAIRS[pair_id])
                secrets.SystemRandom().shuffle(words)
                selected = set(secrets.SystemRandom().sample(range(count), imposters))
                for index, p in enumerate(game['players']):
                    p['imposter'] = index in selected
                    p['word'], p['meaning'] = ((None, None) if mode == 'blank' and p['imposter'] else words[int(p['imposter'])])
                game.update(phase='playing', round=game['round'] + 1, mode=mode, imposters=imposters,
                            words=[dict(word=w, meaning=m) for w, m in words] if mode == 'different' else [dict(word=words[0][0], meaning=words[0][1])])
            elif action == 'end':
                if game['phase'] != 'playing':
                    abort(409, 'There is no active round to end.')
                game['phase'] = 'ended'
            elif action == 'lobby':
                if game['phase'] != 'ended':
                    abort(409, 'End the round before reopening the lobby.')
                game['phase'] = 'lobby'
                game.pop('words', None)
                game['players'] = [{k: p[k] for k in ('id', 'key', 'name')} for p in game['players']]
            elif action == 'remove':
                if game['phase'] != 'lobby':
                    abort(409, 'Players can only be removed in the lobby.')
                target = next((p for p in game['players'] if p['id'] == value.get('target')), None)
                if target is None or target['key'] == player:
                    abort(400, 'Choose another player to remove.')
                game['players'].remove(target)
            else:
                abort(400, 'Unknown room action.')
            game['revision'] += 1
            db.execute('UPDATE imposter_rooms SET game = ? WHERE id = ?', (json.dumps(game), row['id']))
            return jsonify(state=snapshot(row, game, player))
