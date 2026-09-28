(() => {
  const $ = id => document.getElementById(id);
  const randomKey = () => btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(32)))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  const read = (kind, key) => { try { return window[kind].getItem(key); } catch { return null; } };
  const write = (kind, key, value) => { try { window[kind].setItem(key, value); } catch { /* Keep keys in memory if storage is blocked. */ } };
  let room = new URLSearchParams(location.hash.slice(1)).get('room');
  let hostKey, playerKey, viewerKey, current, online = false, busy = false, timer;
  let words = null, attemptedRecovery = false;
  const message = text => { $('message').textContent = text; };
  const base = window.CLUEGRID_API_URL || location.origin;

  async function request(path, body = {}, timeout = 12000) {
    const controller = new AbortController();
    const deadline = setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetch(base.replace(/\/$/, '') + '/api/empire/rooms' + path, {
        method: 'POST', cache: 'no-store', signal: controller.signal,
        headers: { 'Content-Type': 'application/json', ...(hostKey ? { Authorization: 'Bearer ' + hostKey } : {}) },
        body: JSON.stringify({ room, ...body })
      });
      const result = response.headers.get('content-type')?.includes('application/json') ? await response.json() : {};
      if (!response.ok || !Object.keys(result).length) {
        const error = new Error(result.error || 'The room service is unavailable. Please try again.');
        error.status = response.status; throw error;
      }
      return result;
    } catch (error) {
      if (!error.status) error.message = 'Could not reach the room. Keep this tab open and try again; your action has not been confirmed.';
      throw error;
    } finally { clearTimeout(deadline); }
  }

  function render() {
    $('welcome').hidden = !!room;
    $('room-panel').hidden = !room;
    if (!room) return;
    const host = !!current?.host;
    const closed = !!current?.closed;
    $('role').textContent = host ? 'HOST’S ROOM' : 'PLAYER’S ROOM';
    $('connection').textContent = !online ? 'Connecting…' : closed ? 'Entries closed' : 'Collecting words';
    $('connection').dataset.offline = String(!online);
    $('count').textContent = current?.count ?? '—';
    $('room-title').textContent = host ? 'Your room. Their secrets.' : 'A word only you know.';
    $('room-description').textContent = host ? 'Share the invitation. Show the words when everyone is ready.' : 'Submit your word and wait for the host.';
    $('host-controls').hidden = !host;
    $('show').disabled = busy || !online || !current?.count || (closed && !viewerKey);
    $('show').textContent = closed ? (viewerKey ? 'View words' : 'Shown in another tab') : 'Show words';
    $('show-note').textContent = closed ? 'Entries are closed. The list stays in the host tab that first showed it.' : 'Showing the words closes submissions. Only this host tab will see the list.';
    $('word-form').hidden = !current || closed || current.submitted;
    $('submit').disabled = busy || !online;
    $('word').disabled = busy || !online;
    $('waiting').hidden = !current || (!closed && !current.submitted) || !$('reveal').hidden;
    $('waiting-title').textContent = closed ? 'The game is on.' : 'Your word is in.';
    $('waiting-description').textContent = closed ? 'Submissions are closed. Listen as the host reads the words aloud.' : 'Keep it secret. Wait for the host to start the game.';
  }

  function displayWords(list) {
    words = list;
    $('words').replaceChildren(...list.map(word => { const item = document.createElement('li'); item.textContent = word; return item; }));
    $('reveal').hidden = false;
    $('waiting').hidden = true;
  }

  function acceptState(next) {
    current = { ...next, closed: next.closed || !!current?.closed,
      submitted: next.submitted || !!current?.submitted, count: Math.max(next.count, current?.count || 0) };
  }

  async function poll() {
    if (!room) return;
    try {
      const result = await request('/state', { playerKey });
      // An older poll cannot undo a successful submission or close.
      if (!busy) {
        const reconnected = !online;
        acceptState(result.state); online = true; render();
        if (reconnected) message(current.closed ? 'Entries are closed. The host has the word list.' : 'Room connected. Choose your secret word.');
        if (current.host && current.closed && viewerKey && !attemptedRecovery) {
          attemptedRecovery = true;
          await showWords();
        }
      }
    } catch (error) {
      online = false; render(); message(error.message);
      if (error.status === 404) { $('connection').textContent = 'Room unavailable'; return; }
    } finally { clearTimeout(timer); }
    timer = setTimeout(poll, 1500);
  }

  function enterRoom() {
    hostKey = read('localStorage', 'empire:host:' + room);
    playerKey = read('localStorage', 'empire:player:' + room) || randomKey();
    write('localStorage', 'empire:player:' + room, playerKey);
    viewerKey = read('sessionStorage', 'empire:viewer:' + room);
    render(); message('Connecting to your room. The first connection may take a minute.');
    poll();
  }

  $('create').onclick = async () => {
    $('create').disabled = true; message('Creating your room. The first connection may take a minute.');
    try {
      const result = await request('', {}, 90000);
      room = result.room; hostKey = result.hostKey;
      write('localStorage', 'empire:host:' + room, hostKey);
      const url = new URL(location.href); url.hash = new URLSearchParams({ room }); history.replaceState(null, '', url);
      playerKey = randomKey(); write('localStorage', 'empire:player:' + room, playerKey);
      render(); await poll(); message('Room ready. Copy the invitation to bring your players in.');
    } catch (error) { message(error.message); }
    finally { $('create').disabled = false; }
  };

  $('join-form').onsubmit = event => {
    event.preventDefault();
    try {
      const input = $('invite').value.trim();
      const id = /^[A-Za-z0-9_-]{43}$/.test(input) ? input : new URLSearchParams(new URL(input).hash.slice(1)).get('room');
      if (!id || !/^[A-Za-z0-9_-]{43}$/.test(id)) throw new Error();
      const url = new URL(location.href); url.hash = new URLSearchParams({ room: id });
      history.replaceState(null, '', url); location.reload();
    } catch { message('Paste a valid Empire room invitation.'); }
  };

  $('word-form').onsubmit = async event => {
    event.preventDefault(); if (busy || !online) return;
    busy = true; render(); message('Submitting your word…');
    try {
      const result = await request('/submit', { playerKey, word: $('word').value });
      acceptState(result.state); $('word').value = ''; message('Submitted. Your word stays secret until the host shows the list.');
    } catch (error) { message(error.message); }
    finally { busy = false; render(); }
  };

  async function showWords() {
    if (busy) return;
    if (words) { displayWords(words); return; }
    viewerKey ||= randomKey();
    write('sessionStorage', 'empire:viewer:' + room, viewerKey);
    busy = true; render(); message('Opening the word list…');
    try {
      const result = await request('/show', { viewerKey });
      acceptState(result.state); render(); displayWords(result.words); message('Entries closed. These words are visible only in this host tab.');
    } catch (error) { message(error.message); }
    finally { busy = false; render(); }
  }
  $('show').onclick = () => { if (current.closed) showWords(); else $('confirm-show').showModal(); };
  $('cancel-show').onclick = () => $('confirm-show').close();
  $('confirm-reveal').onclick = () => { $('confirm-show').close(); showWords(); };
  $('hide-words').onclick = () => { $('reveal').hidden = true; render(); };
  $('share').onclick = async () => {
    try { await navigator.clipboard.writeText(location.href); message('Invitation copied. Share it with your players.'); }
    catch { $('copy-link').value = location.href; $('copy-dialog').showModal(); $('copy-link').select(); }
  };
  $('close-copy').onclick = () => $('copy-dialog').close();
  if (room) enterRoom(); else render();
})();
