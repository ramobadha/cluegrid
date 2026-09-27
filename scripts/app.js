(() => {
  const $ = (id) => document.getElementById(id);
  const title = (value) => value[0].toUpperCase() + value.slice(1);
  const latestVersion = 'gu-v2';
  const params = new URLSearchParams(location.search);
  let version = Object.hasOwn(WORD_BANKS, params.get('v')) ? params.get('v') : latestVersion;
  let seed, board, state, spy = false, history = [];
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
  const freshState = () => ({ revealed: [], turn: board.startingTeam, winner: null });
  const storageKey = () => `kodenames:${version}:${seed}`;
  function save() {
    try { localStorage.setItem(storageKey(), JSON.stringify({ history })); }
    catch { $('status').textContent = 'Browser storage is unavailable. Keep this tab open to retain progress.'; }
  }
  function load(value, restore = true) {
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
            if (action === 'end') state.turn = state.turn === 'red' ? 'blue' : 'red';
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
    $('status').textContent = `Seed “${seed}” · ${title(board.startingTeam)} starts. Share this seed to get the same board. Moves stay on this device.`;
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
      button.disabled = revealed || !!state.winner || spy;
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
      document.querySelector(`.team-score.${team}`).classList.toggle('active', !state.winner && state.turn === team);
    });
    $('turn-heading').textContent = state.winner ? `${title(state.winner)} team wins!` : `${title(state.turn)} team's turn`;
    $('turn-description').textContent = state.winner ? 'Mission complete. Start a new game to play again.' : 'Listen to your spymaster. Find your agents.';
    $('end-turn').disabled = !!state.winner || spy;
    $('mobile-end-turn').disabled = !!state.winner || spy;
    $('mobile-turn').textContent = spy ? 'Spymaster view' : $('turn-heading').textContent;
    $('mobile-red').textContent = $('red-score').textContent;
    $('mobile-blue').textContent = $('blue-score').textContent;
    document.querySelector('.mobile-turnbar').dataset.team = state.winner || state.turn;
    $('player').setAttribute('aria-pressed', String(!spy)); $('spymaster').setAttribute('aria-pressed', String(spy));
    $('spy-notice').hidden = !spy;
    $('mode-caption').textContent = spy ? 'SPYMASTER VIEW' : 'PLAYER VIEW';
    document.querySelector('.mission-label span').textContent = `${String(state.revealed.length).padStart(2, '0')} / 25`;
  }
  function reveal(index) {
    const next = Game.reveal(board, state, index);
    if (next === state || spy) return;
    state = next; history.push(index); render();
    const card = board.cards[index];
    $('status').textContent = `${card.translations[meaningLanguage]}: ${card.team === 'neutral' ? 'civilian' : card.team}. ${state.winner ? `${title(state.winner)} team wins!` : `${title(state.turn)} team's turn.`}`;
    save();
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
    load(next);
    $('seed').blur();
  };
  $('new-game').onclick = () => {
    const start = () => {
      version = latestVersion;
      load(String(crypto.getRandomValues(new Uint32Array(1))[0]));
    };
    if (history.length && !state.winner) ask('Start a new game?', 'Your current game is saved on this device. You can return using its seed.', 'New game', start);
    else start();
  };
  $('reset').onclick = () => ask('Restart this board?', 'This clears all guesses and returns to the starting team. Words and the key stay the same.', 'Restart board', () => { load(seed, false); save(); });
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
    savePreferences(); load(seed);
  };
  $('meaning-language').onchange = () => {
    const selected = $('meaning-language').value;
    if (selected === mainLanguage) mainLanguage = meaningLanguage;
    meaningLanguage = selected;
    $('main-language').value = mainLanguage;
    document.documentElement.lang = mainLanguage;
    savePreferences(); load(seed);
  };
  $('meanings').onchange = () => { savePreferences(); render(); };
  $('confirm').onchange = savePreferences;
  $('end-turn').onclick = () => {
    if (state.winner || spy) return;
    state.turn = state.turn === 'red' ? 'blue' : 'red'; history.push('end'); render();
    $('status').textContent = `${title(state.turn)} team's turn. Ask your spymaster for a new clue.`; save();
  };
  $('mobile-end-turn').onclick = () => $('end-turn').click();
  function updateFocusMode(enabled) {
    document.body.classList.toggle('game-focus', enabled);
    $('focus-exit').hidden = !enabled;
    $('focus-mode').setAttribute('aria-label', enabled ? 'Exit full screen game view' : 'Enter full screen game view');
    $('focus-mode').setAttribute('aria-pressed', String(enabled));
  }
  $('focus-mode').onclick = async () => {
    if (document.body.classList.contains('game-focus')) {
      if (document.fullscreenElement && document.exitFullscreen) {
        try { await document.exitFullscreen(); } catch { updateFocusMode(false); }
      } else updateFocusMode(false);
      return;
    }
    updateFocusMode(true);
    try {
      if (document.documentElement.requestFullscreen) await document.documentElement.requestFullscreen();
    } catch { /* Keep the focused game layout when native fullscreen is unavailable. */ }
  };
  $('focus-exit').onclick = async () => {
    if (document.fullscreenElement && document.exitFullscreen) {
      try { await document.exitFullscreen(); } catch { updateFocusMode(false); }
    } else updateFocusMode(false);
  };
  document.addEventListener('fullscreenchange', () => updateFocusMode(!!document.fullscreenElement));
  $('share').onclick = async () => {
    if (navigator.share && window.matchMedia('(pointer: coarse)').matches) {
      try {
        await navigator.share({ title: 'ClueGrid', text: `Join my board. Seed: ${seed}`, url: location.href });
        return;
      } catch (error) { if (error.name === 'AbortError') return; }
    }
    try { await navigator.clipboard.writeText(location.href); $('status').textContent = 'Invite link copied. Your friends will get the same words and key; guesses are tracked separately.'; }
    catch {
      $('modal-title').textContent = 'Share this game';
      const input = document.createElement('input'); input.value = location.href; input.readOnly = true; input.style.width = '100%'; input.setAttribute('aria-label', 'Invite link');
      $('modal-content').replaceChildren(input); $('modal-actions').replaceChildren(); $('modal').showModal(); input.select();
    }
  };
  $('help').onclick = () => {
    $('modal-title').textContent = 'One clue. Make it count.';
    $('modal-content').innerHTML = '<ol><li>Split into red and blue teams. Pick one spymaster for each team. Share the invite link so everyone has the same board.</li><li>Spymasters open the key privately. The starting team has 9 agents; the other has 8.</li><li>Give a one-word clue and a number, such as “Nature, 3”. Say clues aloud or over your call. Do not use a word visible on the board.</li><li>Guessers select words. A correct agent lets you keep guessing, up to the clue number plus one. Enforce this limit together, then choose End turn.</li><li>A civilian or opposing agent ends your turn. Reveal the assassin and your team loses. Find all your agents to win.</li></ol><p>English meanings can be hidden for an extra challenge. Seed links share the initial board, not live moves. Each device tracks its own progress. Spymaster view is a trust-based screen, not a private account.</p>';
    $('modal-actions').replaceChildren(); $('modal').showModal();
  };
  load(params.get('seed') || String(crypto.getRandomValues(new Uint32Array(1))[0]));
  if (params.has('v') && params.get('v') !== version) $('status').textContent = 'This link uses an unsupported vocabulary version. The current Gujarati word set has been loaded; boards may differ.';
})();
