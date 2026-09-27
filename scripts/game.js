/* Board selection and shuffle adapted from ninjabunny/KodeNames (MIT). */
(function (root) {
  const api = {};
  api.generate = function (seed, vocabulary, seedrandom) {
    const random = new seedrandom(String(seed).trim().toLowerCase());
    const pool = vocabulary.slice();
    if (pool.length < 25) throw new Error('At least 25 words are required.');
    const selected = Array.from({ length: 25 }, () => pool.splice(Math.floor(random() * pool.length), 1)[0]);
    const teams = Array.from({ length: 16 }, (_, i) => i % 2 ? 'blue' : 'red');
    // Upstream uses the length of its 980-entry base noun list here, even for other word sets.
    const startingTeam = Math.floor(random() * 980) % 2 === 0 ? 'red' : 'blue';
    teams.push(startingTeam, ...Array(7).fill('neutral'), 'assassin');
    for (let count = teams.length; count > 0;) {
      const index = Math.floor(random() * count--);
      [teams[count], teams[index]] = [teams[index], teams[count]];
    }
    // Preserve the original's column-first selection order in a row-first CSS grid.
    const cards = Array.from({ length: 25 }, (_, position) => {
      const index = (position % 5) * 5 + Math.floor(position / 5);
      return { ...selected[index], team: teams[index] };
    });
    return { cards, startingTeam };
  };
  api.remaining = (board, revealed, team) => board.cards.filter((card, i) => card.team === team && !revealed.includes(i)).length;
  api.reveal = function (board, state, index) {
    if (state.winner || state.revealed.includes(index) || !Number.isInteger(index) || !board.cards[index]) return state;
    const next = { ...state, revealed: [...state.revealed, index] };
    const team = board.cards[index].team;
    if (team === 'assassin') next.winner = state.turn === 'red' ? 'blue' : 'red';
    else if (!api.remaining(board, next.revealed, 'red')) next.winner = 'red';
    else if (!api.remaining(board, next.revealed, 'blue')) next.winner = 'blue';
    else if (team !== state.turn) next.turn = state.turn === 'red' ? 'blue' : 'red';
    return next;
  };
  if (typeof module === 'object') module.exports = api;
  else root.Game = api;
})(typeof window === 'object' ? window : globalThis);
