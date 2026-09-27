"""Serve ClueGrid and private, host-controlled rooms.

Room links contain a random read capability. A separate host capability is
required for mutations and is never included in a room snapshot or invite.
"""
from contextlib import closing
from collections import Counter
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time

from flask import Flask, abort, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

ROOT = Path(__file__).resolve().parent
ROOM_LIFETIME = 7 * 24 * 60 * 60


def winner(teams, history):
    if any(teams[index] == 'assassin' for index in history):
        return 'assassin'
    for team in ('red', 'blue'):
        if all(index in history for index, value in enumerate(teams) if value == team):
            return team
    return None


def validate_game(value):
    if not isinstance(value, dict):
        abort(400, 'A game is required.')
    seed, version = value.get('seed'), value.get('version')
    teams, history = value.get('teams'), value.get('history', [])
    if (not isinstance(seed, str) or not seed.strip() or len(seed) > 80
            or version not in ('gu-v1', 'gu-v2')):
        abort(400, 'Invalid seed or vocabulary version.')
    if (not isinstance(teams, list) or len(teams) != 25
            or any(team not in ('red', 'blue', 'neutral', 'assassin') for team in teams)):
        abort(400, 'Invalid board.')
    counts = Counter(teams)
    if (sorted([counts['red'], counts['blue']]) != [8, 9]
            or counts['neutral'] != 7 or counts['assassin'] != 1):
        abort(400, 'Invalid board distribution.')
    if (not isinstance(history, list) or len(history) > 25
            or any(type(index) is not int or not 0 <= index < 25 for index in history)
            or len(set(history)) != len(history)):
        abort(400, 'Invalid reveals.')
    for end in range(1, len(history)):
        if winner(teams, history[:end]):
            abort(400, 'Reveals cannot continue after game over.')
    return dict(seed=seed.strip().lower(), version=version, teams=teams, history=history)


def snapshot(row):
    game = json.loads(row['game'])
    return dict(seed=game['seed'], version=game['version'], history=game['history'],
                winner=winner(game['teams'], game['history']), revision=row['revision'],
                round=row['round'], expiresAt=row['expires_at'])


def create_app(database=None, static_directory=None, allowed_origins=None):
    app = Flask(__name__, static_folder=None)
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024
    database = str(database or os.environ.get('ROOM_DB', ROOT / 'instance' / 'rooms.sqlite3'))
    static_directory = Path(static_directory or ROOT / 'dist').resolve()
    allowed_origins = set(allowed_origins if allowed_origins is not None
                          else filter(None, os.environ.get('ALLOWED_ORIGINS', '').split(',')))
    Path(database).parent.mkdir(parents=True, exist_ok=True)

    def connect():
        db = sqlite3.connect(database, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    with closing(connect()) as db, db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('''CREATE TABLE IF NOT EXISTS rooms (
            id TEXT PRIMARY KEY, host_hash TEXT NOT NULL, game TEXT NOT NULL,
            revision INTEGER NOT NULL, round INTEGER NOT NULL,
            created_at REAL NOT NULL, expires_at REAL NOT NULL)''')
        db.execute('CREATE INDEX IF NOT EXISTS rooms_expiry ON rooms(expires_at)')

    def payload():
        value = request.get_json()
        if not isinstance(value, dict):
            abort(400, 'Expected a JSON object.')
        return value

    def room_row(db, value):
        room = value.get('room')
        if not isinstance(room, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', room):
            abort(404, 'This room is unavailable or has expired. Ask the host for a new link.')
        row = db.execute('SELECT * FROM rooms WHERE id = ? AND expires_at > ?',
                         (room, time.time())).fetchone()
        if row is None:
            abort(404, 'This room is unavailable or has expired. Ask the host for a new link.')
        return row

    def allowed_origin(origin):
        return origin in allowed_origins or origin in (f'http://{request.host}', f'https://{request.host}')

    @app.before_request
    def check_origin():
        origin = request.headers.get('Origin')
        if request.path.startswith('/api/') and origin and not allowed_origin(origin):
            abort(403, 'This website is not allowed to connect to the room service.')

    @app.after_request
    def response_headers(response):
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
            origin = request.headers.get('Origin')
            if origin and allowed_origin(origin):
                response.headers['Access-Control-Allow-Origin'] = origin
                response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
                response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
                response.headers['Access-Control-Max-Age'] = '600'
                response.vary.add('Origin')
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        if request.path.startswith('/api/'):
            return jsonify(error=error.description), error.code
        return error

    @app.get('/health')
    def health():
        with closing(connect()) as db:
            db.execute('SELECT 1 FROM rooms LIMIT 1').fetchone()
        return jsonify(ok=True)

    @app.post('/api/rooms')
    def create_room():
        game = validate_game(payload().get('game'))
        room, host = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        now = time.time()
        with closing(connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM rooms WHERE expires_at <= ?', (now,))
            if db.execute('SELECT count(*) FROM rooms').fetchone()[0] >= 5000:
                abort(503, 'Rooms are currently full. Please try again later.')
            if db.execute('SELECT count(*) FROM rooms WHERE created_at > ?', (now - 60,)).fetchone()[0] >= 60:
                abort(429, 'Too many new rooms. Please try again in a minute.')
            db.execute('INSERT INTO rooms VALUES (?, ?, ?, 0, 0, ?, ?)',
                       (room, hashlib.sha256(host.encode()).hexdigest(), json.dumps(game),
                        now, now + ROOM_LIFETIME))
            state = snapshot(room_row(db, dict(room=room)))
        return jsonify(room=room, hostKey=host, state=state), 201

    # Keep room capabilities in request bodies, out of server URL/access logs.
    @app.post('/api/rooms/state')
    def read_room():
        value = payload()
        with closing(connect()) as db:
            return jsonify(state=snapshot(room_row(db, value)))

    @app.post('/api/rooms/action')
    def change_room():
        value = payload()
        with closing(connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            row = room_row(db, value)
            auth = request.headers.get('Authorization', '')
            token = auth[7:] if auth.startswith('Bearer ') else ''
            if not hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(), row['host_hash']):
                abort(403, 'Only the host can change this game.')
            if type(value.get('revision')) is not int or value['revision'] != row['revision']:
                return jsonify(error='The board changed. Please try again.', state=snapshot(row)), 409
            game = json.loads(row['game'])
            round_number = row['round']
            action = value.get('action')
            if action == 'reveal':
                index = value.get('index')
                if type(index) is not int or not 0 <= index < 25:
                    abort(400, 'Invalid card.')
                if index in game['history']:
                    return jsonify(state=snapshot(row))
                if winner(game['teams'], game['history']):
                    abort(409, 'This game is over. Start a new game to continue.')
                game['history'].append(index)
            elif action == 'reset':
                game['history'] = []
                round_number += 1
            elif action == 'new':
                game = validate_game(value.get('game'))
                game['history'] = []
                round_number += 1
            else:
                abort(400, 'Unknown game action.')
            db.execute('UPDATE rooms SET game = ?, revision = revision + 1, round = ? WHERE id = ?',
                       (json.dumps(game), round_number, row['id']))
            result = snapshot(room_row(db, value))
        return jsonify(state=result)

    @app.get('/')
    def index():
        return send_from_directory(static_directory, 'index.html')

    @app.get('/<path:path>')
    def assets(path):
        if path.split('/')[0] not in ('styles', 'scripts', 'data'):
            abort(404)
        return send_from_directory(static_directory, path)

    return app


if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=int(os.environ.get('PORT', 8000)), threaded=True)
