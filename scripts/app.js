(() => {
  const $ = (id) => document.getElementById(id);
  const title = (value) => value[0].toUpperCase() + value.slice(1);
  const latestVersion = 'gu-v2';
  const params = new URLSearchParams(location.search);
  const invitedRoom = new URLSearchParams(location.hash.slice(1)).get('room');
  let room = null, roomRound = null, joiningRoom = !!invitedRoom;
  let version = Object.hasOwn(WORD_BANKS, params.get('v')) ? params.get('v') : latestVersion;
  let seed, board, state, spy = false, history = [];
  let announcementTimer;
  function announceResult(message) {
    clearTimeout(announcementTimer);
    $('game-result').textContent = message;
    $('game-result').hidden = false;
    $('status').textContent = message;
    announcementTimer = setTimeout(() => { $('game-result').hidden = true; }, 3000);
  }
  const supportedLanguages = WORD_BANK_LANGUAGES[version].filter(code => Object.hasOwn(LANGUAGES, code));
  let preferences = {};
  try {
    preferences = JSON.parse(localStorage.getItem('kodenames:preferences')) || {};
    if (typeof preferences?.meanings === 'boolean') $('meanings').checked = preferences.meanings;
    if (typeof preferences?.confirm === 'boolean') $('confirm').checked = preferences.confirm;
  } catch { /* Use defaults when browser storage is unavailable. */ }
  let mainLanguage = supportedLanguages.includes(params.get('lang'))
    ? params.get('lang')
    : (supportedLanguages.includes(preferences.mainLanguage) ? preferences.mainLanguage : 'gu');
  let meaningLanguage = supportedLanguages.includes(params.get('meaning'))
    ? params.get('meaning')
    : (supportedLanguages.includes(preferences.meaningLanguage) ? preferences.meaningLanguage : 'en');
  if (mainLanguage === meaningLanguage) meaningLanguage = supportedLanguages.find(code => code !== mainLanguage);
  function languageLabel(code) {
    const language = LANGUAGES[code];
    return language.name.toLowerCase() === language.native.toLowerCase()
      ? language.name
      : `${language.name} · ${language.native}`;
  }
  function addLanguageOptions(select) {
    for (const code of supportedLanguages) {
      const option = document.createElement('option');
      option.value = code;
      option.textContent = languageLabel(code);
      select.append(option);
    }
  }
  addLanguageOptions($('main-language'));
  addLanguageOptions($('meaning-language'));
  $('main-language').value = mainLanguage;
  $('meaning-language').value = meaningLanguage;
  document.documentElement.lang = mainLanguage;
  function savePreferences() {
    try { localStorage.setItem('kodenames:preferences', JSON.stringify({ meanings: $('meanings').checked, confirm: $('confirm').checked, mainLanguage, meaningLanguage })); }
    catch { /* Preferences are optional; gameplay still works without storage. */ }
  }
  const freshState = () => ({ revealed: [], winner: null });
  const storageKey = () => `kodenames:${version}:${seed}`;
  function save() {
    if (room) return;
    try { localStorage.setItem(storageKey(), JSON.stringify({ history })); }
    catch { $('status').textContent = 'Browser storage is unavailable. Keep this tab open to retain progress.'; }
  }
  function load(value, restore = true) {
    clearTimeout(announcementTimer);
    $('game-result').hidden = true;
    seed = value.trim().toLowerCase().slice(0, 80) || 'namaste';
    const words = WORD_BANKS[version];
    board = Game.generate(seed, words, Math.seedrandom);
    $('word-bank-size').textContent = `${words.length.toLocaleString('en-US')} words to explore`;
    state = freshState(); history = []; spy = false;
    if (restore) {
      try {
        const saved = JSON.parse(localStorage.getItem(storageKey()));
        if (Array.isArray(saved?.history)) {
          for (const action of saved.history.slice(0, 1000)) {
            if (state.winner) break;
            if (action === 'end') continue; // Older saves included manual turn changes.
            else if (Number.isInteger(action) && action >= 0 && action < 25) state = Game.reveal(board, state, action);
            else continue;
            history.push(action);
          }
        }
      } catch { /* Invalid or unavailable storage starts a clean board. */ }
    }
    $('seed').value = seed;
    const url = new URL(location.href); url.searchParams.set('seed', seed); url.searchParams.set('v', version);
    url.searchParams.set('lang', mainLanguage); url.searchParams.set('meaning', meaningLanguage);
    window.history.replaceState(null, '', url);
    render();
    $('status').textContent = `Seed “${seed}” · Share this seed to get the same board. Moves stay on this device.`;
  }
  function render() {
    const active = document.activeElement?.dataset?.index;
    $('board').replaceChildren();
    board.cards.forEach((card, index) => {
      const revealed = state.revealed.includes(index);
      const visible = spy || revealed;
      const word = card.translations[mainLanguage];
      const translation = card.translations[meaningLanguage];
      const button = document.createElement('button');
      button.className = `card${visible ? ` ${card.team}` : ''}${revealed ? ' revealed' : ''}`;
      if (word.length > 14) button.classList.add('long-word');
      button.dataset.index = index;
      button.disabled = revealed || !!state.winner || spy || joiningRoom || !!(room && (!room.hostKey || !room.connected || room.busy));
      const name = document.createElement('span'); name.className = 'term'; name.lang = mainLanguage; name.textContent = word;
      const meaning = document.createElement('span'); meaning.className = 'meaning'; meaning.lang = meaningLanguage; meaning.textContent = translation; meaning.hidden = !$('meanings').checked;
      const number = document.createElement('span'); number.className = 'number'; number.textContent = String(index + 1).padStart(2, '0');
      const identity = document.createElement('span'); identity.className = 'identity';
      identity.textContent = visible ? `${revealed ? '✓ ' : ''}${card.team === 'neutral' ? 'Civilian' : card.team}` : '';
      button.append(number, name, meaning, identity);
      button.addEventListener('click', () => {
        if ($('confirm').checked) ask('Reveal this word?', word, 'Reveal card', () => reveal(index), mainLanguage === 'gu', $('meanings').checked ? translation : '');
        else reveal(index);
      });
      $('board').append(button);
    });
    if (active !== undefined) $('board').querySelector(`[data-index="${active}"]`)?.focus();
    ['red', 'blue'].forEach(team => {
      $(`${team}-score`).textContent = Game.remaining(board, state.revealed, team);
      $(`${team}-score`).setAttribute('aria-label', `${title(team)}: ${Game.remaining(board, state.revealed, team)} words remaining`);
    });
    $('player').setAttribute('aria-pressed', String(!spy)); $('spymaster').setAttribute('aria-pressed', String(spy));
    $('spy-notice').hidden = !spy;
    $('mode-caption').textContent = spy ? 'SPYMASTER VIEW' : 'PLAYER VIEW';
    const readOnly = joiningRoom || !!(room && (!room.hostKey || !room.connected || room.busy));
    for (const id of ['new-game', 'reset', 'seed']) $(id).disabled = readOnly;
    $('seed-form').querySelector('button').disabled = readOnly;
    $('leave-room').hidden = !room && !joiningRoom;
    $('room-status').hidden = !room && !joiningRoom;
    $('room-status').textContent = joiningRoom ? (room?.stopped ? 'Unavailable' : 'Joining…') : room ? `${room.hostKey ? 'Host' : 'Guest'} · ${room.connected ? 'Live' : 'Offline'}` : '';
  }
  function reveal(index) {
    if (joiningRoom || spy) return;
    if (room) { room.act('reveal', { index }); return; }
    const next = Game.reveal(board, state, index);
    if (next === state || spy) return;
    state = next; history.push(index); render();
    const card = board.cards[index];
    $('status').textContent = `${card.translations[meaningLanguage]}: ${card.team === 'neutral' ? 'civilian' : card.team}. ${state.winner === 'assassin' ? 'Assassin revealed. Game over.' : state.winner ? `${title(state.winner)} team wins!` : ''}`;
    save();
    if (state.winner === 'assassin') {
      announceResult('Game over');
    } else if (state.winner) {
      announceResult(`Game over — ${title(state.winner)} team wins!`);
    }
  }
  function roomGame(value = seed, bank = version, moves = history) {
    const generated = Game.generate(value, WORD_BANKS[bank], Math.seedrandom);
    return { seed: value, version: bank, teams: generated.cards.map(card => card.team), history: moves };
  }
  function roomConnection(connected, message = '') {
    if (message) $('status').textContent = message;
    else if (connected && room) $('status').textContent = state.winner
      ? (state.winner === 'assassin' ? 'Game over' : `Game over — ${title(state.winner)} team wins!`)
      : room.hostKey ? 'You are the host. Your reveals are shared with everyone in this room.'
        : 'Live room. The host reveals cards for everyone.';
    render();
  }
  function applyRoomState(snapshot, first) {
    const previousWinner = state.winner;
    const changedRound = roomRound !== snapshot.round;
    joiningRoom = false;
    if (changedRound && !first && $('modal').open) $('modal').close();
    if (seed !== snapshot.seed || version !== snapshot.version || changedRound) {
      version = snapshot.version;
      load(snapshot.seed, false);
    }
    roomRound = snapshot.round;
    history = snapshot.history;
    state = history.reduce((current, index) => Game.reveal(board, current, index), freshState());
    const url = new URL(location.href);
    url.hash = new URLSearchParams({ room: room.id }).toString();
    window.history.replaceState(null, '', url);
    roomConnection(room.connected);
    if (!first && state.winner && (changedRound || state.winner !== previousWinner)) {
      announceResult(state.winner === 'assassin' ? 'Game over' : `Game over — ${title(state.winner)} team wins!`);
    }
  }
  function ask(heading, message, actionLabel, action, gujarati = false, meaning = '') {
    $('modal-title').textContent = heading;
    const text = document.createElement('p'); text.textContent = message;
    if (gujarati) { text.lang = 'gu'; text.className = 'dialog-word'; }
    $('modal-content').replaceChildren(text); $('modal-actions').replaceChildren();
    if (meaning) {
      const gloss = document.createElement('p'); gloss.className = 'dialog-meaning'; gloss.textContent = meaning;
      $('modal-content').append(gloss);
    }
    const cancel = document.createElement('button'); cancel.className = 'secondary'; cancel.textContent = 'Cancel'; cancel.onclick = () => $('modal').close();
    const accept = document.createElement('button'); accept.className = 'primary'; accept.textContent = actionLabel;
    accept.onclick = () => { $('modal').close(); action(); };
    $('modal-actions').append(cancel, accept); $('modal').showModal(); cancel.focus();
  }
  $('seed-form').onsubmit = (event) => {
    event.preventDefault(); const next = $('seed').value;
    if (next.trim().toLowerCase() === seed) return;
    if (joiningRoom) return;
    if (room) {
      room.act('new', { game: roomGame(next.trim().toLowerCase().slice(0, 80), version, []) });
      return;
    }
    load(next);
    $('seed').blur();
  };
  $('new-game').onclick = () => {
    const start = () => {
      if (joiningRoom) return;
      if (room) {
        room.act('new', { game: roomGame(String(crypto.getRandomValues(new Uint32Array(1))[0]), latestVersion, []) });
        return;
      }
      version = latestVersion;
      load(String(crypto.getRandomValues(new Uint32Array(1))[0]));
    };
    if (history.length && !state.winner) ask('Start a new game?', room ? 'This starts a new board for everyone in the room.' : 'Your current game is saved on this device. You can return using its seed.', 'New game', start);
    else start();
  };
  $('reset').onclick = () => ask('Restart this board?', room ? 'This clears guesses for everyone in the room. Words and the key stay the same.' : 'This clears all guesses. Words and the key stay the same.', 'Restart board', () => {
    if (joiningRoom) return;
    if (room) { room.act('reset'); return; }
    load(seed, false); save();
  });
  $('leave-room').onclick = () => {
    const url = new URL(location.href);
    url.hash = '';
    window.history.replaceState(null, '', url);
    location.reload();
  };
  $('player').onclick = () => { spy = false; render(); };
  $('spymaster').onclick = () => {
    if (!spy) ask('For spymasters only', 'This reveals every card’s identity. Make sure guessers cannot see your screen.', 'Show key', () => { spy = true; render(); });
  };
  $('main-language').onchange = () => {
    const previous = mainLanguage;
    mainLanguage = $('main-language').value;
    if (meaningLanguage === mainLanguage) meaningLanguage = previous;
    $('meaning-language').value = meaningLanguage;
    document.documentElement.lang = mainLanguage;
    applyLanguages();
  };
  $('meaning-language').onchange = () => {
    const selected = $('meaning-language').value;
    if (selected === mainLanguage) mainLanguage = meaningLanguage;
    meaningLanguage = selected;
    $('main-language').value = mainLanguage;
    document.documentElement.lang = mainLanguage;
    applyLanguages();
  };
  $('meanings').onchange = () => { savePreferences(); render(); };
  $('confirm').onchange = savePreferences;
  function applyLanguages() {
    $('main-language').value = mainLanguage;
    $('meaning-language').value = meaningLanguage;
    document.documentElement.lang = mainLanguage;
    const url = new URL(location.href);
    url.searchParams.set('lang', mainLanguage);
    url.searchParams.set('meaning', meaningLanguage);
    window.history.replaceState(null, '', url);
    savePreferences(); render();
  }
  $('swap-languages').onclick = () => {
    [mainLanguage, meaningLanguage] = [meaningLanguage, mainLanguage];
    applyLanguages();
  };
  let orientationLocked = false;
  const fullscreenElement = () => document.fullscreenElement || document.webkitFullscreenElement;
  function updateFocusMode(enabled) {
    document.body.classList.toggle('game-focus', enabled);
    $('focus-exit').hidden = !enabled;
    const exitLabel = fullscreenElement() ? 'Exit full screen' : 'Exit grid view';
    $('focus-exit').setAttribute('aria-label', exitLabel);
    $('focus-exit').title = exitLabel;
    $('focus-mode').setAttribute('aria-pressed', String(enabled));
    if (enabled) {
      $('focus-mode').blur();
    } else {
      if (orientationLocked) {
        try { screen.orientation.unlock(); } catch { /* Some browsers unlock automatically. */ }
        orientationLocked = false;
      }
      $('focus-mode').focus({ preventScroll: true });
    }
  }
  $('focus-mode').onclick = async () => {
    const root = document.documentElement;
    try {
      if (root.requestFullscreen) await root.requestFullscreen({ navigationUI: 'hide' });
      else if (root.webkitRequestFullscreen) await root.webkitRequestFullscreen();
      else throw new Error('Fullscreen unavailable');
      updateFocusMode(!!fullscreenElement());
      if (fullscreenElement() && navigator.maxTouchPoints > 0 && screen.orientation?.lock) {
        try {
          await screen.orientation.lock('landscape');
          orientationLocked = true;
          if (!fullscreenElement()) {
            screen.orientation.unlock();
            orientationLocked = false;
          }
        } catch { /* Rotate the device manually when orientation locking is unavailable. */ }
      }
    } catch {
      // iPhone Safari and restricted embeds may not expose native element fullscreen.
      // Keep the same fitted board without pretending to hide browser-owned controls.
      updateFocusMode(true);
      $('status').textContent = 'This browser does not allow native fullscreen. The grid fits the browser window; rotate your phone for landscape.';
    }
  };
  $('focus-exit').onclick = async () => {
    if (!fullscreenElement()) { updateFocusMode(false); return; }
    try {
      if (document.exitFullscreen) await document.exitFullscreen();
      else if (document.webkitExitFullscreen) await document.webkitExitFullscreen();
    } catch { $('focus-exit').focus(); }
  };
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && document.body.classList.contains('game-focus') && !fullscreenElement() && !$('modal').open) updateFocusMode(false);
  });
  for (const event of ['fullscreenchange', 'webkitfullscreenchange']) {
    document.addEventListener(event, () => updateFocusMode(!!fullscreenElement()));
  }
  $('share').onclick = async () => {
    if (joiningRoom || (room && !room.connected)) {
      $('status').textContent = 'Wait for the room to connect before sharing its link.';
      return;
    }
    if (!room) {
      $('share').disabled = true;
      $('status').textContent = 'Creating your private room…';
      room = new RoomClient(applyRoomState, roomConnection);
      render();
      try { await room.create(roomGame()); }
      catch (error) {
        room = null;
        render();
        // Plain static hosting still supports the original seed-only links.
        if (window.CLUEGRID_API_URL || ![404, 405, 501].includes(error.status)) {
          $('status').textContent = error.name === 'AbortError' ? 'The room server is taking too long. Please try sharing again.' : error.status ? error.message : 'Could not connect to the room service. Please try sharing again.';
          return;
        }
      } finally { $('share').disabled = false; }
    }
    if (navigator.share && window.matchMedia('(pointer: coarse)').matches) {
      try {
        await navigator.share({ title: 'ClueGrid', text: `Join my board. Seed: ${seed}`, url: location.href });
        return;
      } catch (error) { if (error.name === 'AbortError') return; }
    }
    try {
      await navigator.clipboard.writeText(location.href);
      $('status').textContent = room ? 'Room link copied. Everyone with this link sees the host’s reveals.' : 'Board link copied. Live sharing is not configured on this site; this link shares the words only.';
    }
    catch {
      $('modal-title').textContent = room ? 'Share this live room' : 'Share this board (local play only)';
      const input = document.createElement('input'); input.value = location.href; input.readOnly = true; input.style.width = '100%'; input.setAttribute('aria-label', 'Invite link');
      $('modal-content').replaceChildren(input); $('modal-actions').replaceChildren(); $('modal').showModal(); input.select();
    }
  };
  $('help').onclick = () => {
    $('modal-title').textContent = 'One clue. Make it count.';
    $('modal-content').innerHTML = '<ol><li>Split into red and blue teams. Pick one spymaster for each team. Share the invite link so everyone has the same board.</li><li>Spymasters open the key privately. The starting team has 9 agents; the other has 8.</li><li>Give a one-word clue and a number, such as “Nature, 3”. Say clues aloud or over your call. Do not use a word visible on the board.</li><li>Guessers select words. A correct agent lets you keep guessing, up to the clue number plus one. Keep track of turns together; the board only counts remaining words.</li><li>A civilian or opposing agent ends your turn. Reveal the assassin and your team loses. Find all your agents to win.</li></ol><p>English meanings can be hidden for an extra challenge. Share game creates a private live room. The host reveals cards, restarts, and starts new boards for everyone with the room link. Guests can choose their own languages and view. A seed without a room link is an independent local game. Spymaster view is a trust-based screen, not a private account.</p>';
    $('modal-actions').replaceChildren(); $('modal').showModal();
  };
  load(params.get('seed') || String(crypto.getRandomValues(new Uint32Array(1))[0]), !joiningRoom);
  if (invitedRoom) {
    room = new RoomClient(applyRoomState, roomConnection);
    $('status').textContent = 'Joining the shared room…';
    room.join(invitedRoom);
  }
  if (params.has('v') && params.get('v') !== version) $('status').textContent = 'This link uses an unsupported vocabulary version. The current Gujarati word set has been loaded; boards may differ.';
})();
