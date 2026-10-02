(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const key = () => btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(32)))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  const read = name => { try { return localStorage.getItem(name); } catch { return null; } };
  const save = (name, value) => { try { localStorage.setItem(name, value); } catch { /* Keys remain in memory for this visit. */ } };
  const base = (window.CLUEGRID_API_URL || location.origin).replace(/\/$/, '') + '/api/imposter/rooms';
  let room = new URLSearchParams(location.hash.slice(1)).get('room');
  let playerKey = room && read('imposter:player:' + room) || key();
  let hostKey = room && read('imposter:host:' + room);
  let current = null, timer, busy = false, online = false, shown = false, stopped = false;
  const message = text => { $('message').textContent = text; };

  async function request(path, body = {}, timeout = 15000) {
    const controller = new AbortController();
    const deadline = setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetch(base + path, { method: 'POST', cache: 'no-store', signal: controller.signal,
        headers: { 'Content-Type': 'application/json', ...(hostKey ? { Authorization: 'Bearer ' + hostKey } : {}) },
        body: JSON.stringify({ room, playerKey, ...body }) });
      const data = response.headers.get('content-type')?.includes('application/json') ? await response.json() : {};
      if (!response.ok || !Object.keys(data).length) {
        const error = new Error(data.error || 'The room service is unavailable. Try again.'); error.status = response.status; throw error;
      }
      return data;
    } catch (error) {
      if (!error.status) error.message = 'Connection interrupted. Your action is not confirmed. Wait for reconnection before trying again.';
      throw error;
    } finally { clearTimeout(deadline); }
  }

  function cover() {
    shown = false;
    $('secret').hidden = true; $('covered').hidden = false;
    $('secret-word').textContent = ''; $('secret-meaning').textContent = '';
    $('peek').textContent = 'Show my secret';
  }

  function accept(state) {
    if (current && state.revision < current.revision) return;
    if (!current || state.round !== current.round || state.phase !== current.phase || state.me !== current.me) cover();
    current = state;
  }

  function render() {
    $('welcome').hidden = !!room; $('room-panel').hidden = !room;
    if (!room) return;
    const s = current;
    $('phase').textContent = s ? `${s.host ? 'HOST · ' : ''}${s.phase === 'lobby' ? 'LOBBY' : 'ROUND ' + s.round}` : 'YOUR ROOM';
    $('connection').textContent = online ? 'Connected' : stopped ? 'Room unavailable' : 'Reconnecting…';
    $('room-title').textContent = s?.phase === 'playing' ? 'Keep your secret close.' : s?.phase === 'ended' ? 'Round complete.' : 'Gather your suspects.';
    $('join-form').hidden = !s || !!s.me || s.phase !== 'lobby';
    $('spectating').hidden = !s || !!s.me || s.phase === 'lobby';
    $('lobby').hidden = !s || s.phase !== 'lobby';
    $('playing').hidden = !s || s.phase !== 'playing' || !s.me;
    $('results').hidden = !s || s.phase !== 'ended';
    $('settings').hidden = !s?.host;
    $('wait-host').hidden = !!s?.host;
    $('end').hidden = !s?.host;
    $('next').hidden = !s?.host;
    for (const id of ['start', 'join', 'end', 'next', 'mode', 'imposter-count']) $(id).disabled = busy || !online;
    $('peek').disabled = !online;
    if (!s) return;
    const n = s.players.length;
    $('player-count').textContent = `${n} / 20 players`;
    $('players').replaceChildren(...s.players.map(p => {
      const li = document.createElement('li');
      const label = document.createElement('span'); label.textContent = p.name + (p.id === s.me ? ' (you)' : ''); li.append(label);
      if (s.host && s.phase === 'lobby' && p.id !== s.me) {
        const button = document.createElement('button'); button.textContent = '×'; button.ariaLabel = 'Remove ' + p.name;
        button.disabled = busy || !online; button.onclick = () => action('remove', { target: p.id }); li.append(button);
      }
      return li;
    }));
    const choice = $('imposter-count').value;
    const max = Math.max(1, Math.floor((n - 1) / 2));
    $('imposter-count').replaceChildren(...['auto', ...Array.from({length:max}, (_, i) => String(i + 1))].map(value => {
      const option = document.createElement('option'); option.value = value;
      option.textContent = value === 'auto' ? `Recommended (${s.recommended})` : value; return option;
    }));
    $('imposter-count').value = choice === 'auto' || Number(choice) <= max ? choice : 'auto';
    $('recommendation').textContent = n < 3 ? 'At least 3 players are needed to deal.' : `${s.recommended} recommended for ${n} players. Imposters must be fewer than half the room.`;
    $('start').disabled = busy || !online || n < 3;
    $('round-info').textContent = `${n} players · ${s.imposters} imposter${s.imposters === 1 ? '' : 's'} · ${s.mode === 'blank' ? 'No-word mode' : 'Different-word mode'}`;
    if (s.phase === 'ended') {
      $('word-pair').replaceChildren(...s.words.map((w, i) => {
        const p = document.createElement('p'); p.textContent = `${i === 0 ? 'Ordinary word' : 'Imposter word'}: ${w.word} — ${w.meaning}`; return p;
      }));
      $('result-list').replaceChildren(...s.results.map(p => {
        const li = document.createElement('li'); const strong = document.createElement('strong');
        strong.textContent = p.imposter ? 'Imposter' : 'Ordinary player';
        li.append(document.createTextNode(p.name + ' · '), strong, document.createTextNode(' · ' + (p.word || 'No word'))); return li;
      }));
    } else { $('result-list').replaceChildren(); $('word-pair').replaceChildren(); }
  }

  async function poll() {
    clearTimeout(timer);
    if (!room || stopped) return;
    try {
      const { state } = await request('/state');
      if (!busy) { const recovered = !online; accept(state); online = true; render(); if (recovered) message('Room connected.'); }
    } catch (error) {
      if (!busy) {
        online = false; cover(); message(error.message);
        if (error.status === 404) { stopped = true; current = null; }
        render();
      }
    } finally { if (!stopped) timer = setTimeout(poll, 1500); }
  }

  async function action(actionName, extra = {}) {
    if (busy || !online || !current) return;
    busy = true; render();
    try {
      const {state} = await request('/action', { action: actionName, revision: current.revision, ...extra });
      accept(state); message(actionName === 'start' ? 'Secrets dealt. Look privately, then play out loud.' : 'Room updated.');
    } catch (error) { cover(); message(error.message); }
    finally { busy = false; render(); await poll(); }
  }

  $('create-form').onsubmit = async event => {
    event.preventDefault(); if (busy) return;
    busy = true; $('create').disabled = true; message('Creating your room. The first connection may take a minute.');
    try {
      const result = await request('', {name: $('host-name').value}, 90000);
      room = result.room; hostKey = result.hostKey;
      save('imposter:host:' + room, hostKey); save('imposter:player:' + room, playerKey);
      location.hash = new URLSearchParams({room});
      busy = false; render(); await poll(); message('Room ready. Copy the invitation and send it to your players.');
    } catch (error) { message(error.message); }
    finally { busy = false; $('create').disabled = false; }
  };
  $('join-form').onsubmit = async event => {
    event.preventDefault(); if (busy || !online) return;
    busy = true; render();
    try { const {state} = await request('/join', {name: $('player-name').value}); accept(state); message('You are at the table.'); }
    catch (error) { message(error.message); }
    finally { busy = false; render(); await poll(); }
  };
  $('invite-form').onsubmit = event => {
    event.preventDefault();
    try {
      const raw = $('invite').value.trim();
      const id = /^[A-Za-z0-9_-]{43}$/.test(raw) ? raw : new URLSearchParams(new URL(raw).hash.slice(1)).get('room');
      if (!/^[A-Za-z0-9_-]{43}$/.test(id || '')) throw new Error();
      location.hash = new URLSearchParams({room:id}); location.reload();
    } catch { message('Paste a valid Imposter room invitation.'); }
  };
  $('start').onclick = () => action('start', {mode:$('mode').value, imposters:$('imposter-count').value === 'auto' ? current.recommended : Number($('imposter-count').value)});
  $('mode').onchange = () => { $('mode-note').textContent = $('mode').value === 'blank' ? 'Ordinary players see the same word and meaning. Imposters are told to bluff without a word.' : 'Everyone sees a word and its meaning. Imposters get a related word; nobody is told their role.'; };
  $('peek').onclick = () => {
    if (shown) { cover(); return; }
    if (!current?.secret || !online) return;
    shown = true; $('covered').hidden = true; $('secret').hidden = false;
    $('secret-word').textContent = current.secret.word || 'You are the imposter.';
    $('secret-meaning').textContent = current.secret.meaning || 'You have no word. Listen carefully and bluff your way through.';
    $('peek').textContent = 'Hide my secret';
  };
  document.addEventListener('visibilitychange', () => { if (document.hidden) cover(); });
  window.addEventListener('pagehide', cover);
  $('end').onclick = () => $('end-dialog').showModal();
  $('cancel-end').onclick = () => $('end-dialog').close();
  $('confirm-end').onclick = () => { $('end-dialog').close(); action('end'); };
  $('next').onclick = () => action('lobby');
  $('share').onclick = async () => {
    try { await navigator.clipboard.writeText(location.href); message('Invitation copied. Send it to your players.'); }
    catch { $('copy-link').value = location.href; $('copy-dialog').showModal(); $('copy-link').select(); }
  };
  $('close-copy').onclick = () => $('copy-dialog').close();
  if (room) { save('imposter:player:' + room, playerKey); render(); poll(); } else render();
})();
