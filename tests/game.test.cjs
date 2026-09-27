const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const Game = require('../scripts/game.js');
const rng = require('../scripts/seedrandom.js');
function parseWords(path) {
  const rows = fs.readFileSync(path, 'utf8').trim().split(/\r?\n/).map(line => line.split('\t'));
  const languages = rows[0][0] === 'gu' && rows[0][1] === 'en' ? rows.shift() : ['gu', 'en'];
  return rows.map(columns => {
    const translations = Object.fromEntries(languages.map((code, index) => [code, columns[index]]));
    return { term: translations.gu, meaning: translations.en, translations };
  });
}
const words = parseWords('data/words.tsv');
const board = Game.generate('namaste', words, rng);
const fresh = () => ({ revealed: [], turn: board.startingTeam, winner: null });
test('seeds normalize, reproduce, and vary boards without mutating vocabulary', () => {
  const snapshot = JSON.stringify(words);
  assert.deepEqual(board, Game.generate(' NAMASTE ', words, rng));
  assert.notDeepEqual(board, Game.generate('different', words, rng));
  assert.equal(snapshot, JSON.stringify(words));
});
test('100 seeds each produce 25 distinct cards and the correct team distribution', () => {
  for (let i = 0; i < 100; i++) {
    const b = Game.generate(i, words, rng);
    assert.equal(new Set(b.cards.map(c => c.term)).size, 25);
    const count = team => b.cards.filter(c => c.team === team).length;
    assert.equal(count(b.startingTeam), 9);
    assert.equal(count(b.startingTeam === 'red' ? 'blue' : 'red'), 8);
    assert.equal(count('neutral'), 7); assert.equal(count('assassin'), 1);
  }
});
test('reveals count either team without tracking turns', () => {
  let state = { revealed: [], winner: null };
  for (const team of ['red', 'neutral', 'blue']) {
    const index = board.cards.findIndex(c => c.team === team);
    state = Game.reveal(board, state, index);
    assert.ok(state.revealed.includes(index));
    assert.equal(state.turn, undefined);
    assert.equal(state.winner, null);
  }
});
test('assassin ends play without assigning a winner to an untracked turn', () => {
  const result = Game.reveal(board, fresh(), board.cards.findIndex(c => c.team === 'assassin'));
  assert.equal(result.winner, 'assassin');
  assert.equal(Game.reveal(board, result, 0), result);
});
test('all agents revealed wins, duplicate and invalid guesses do nothing', () => {
  let state = fresh();
  for (const [index, card] of board.cards.entries()) if (card.team === 'red') state = Game.reveal(board, state, index);
  assert.equal(state.winner, 'red'); assert.equal(Game.remaining(board, state.revealed, 'red'), 0);
  const initial = fresh();
  assert.equal(Game.reveal(board, initial, -1), initial);
  assert.equal(Game.reveal(board, initial, 1.5), initial);
  const once = Game.reveal(board, initial, 0);
  assert.equal(Game.reveal(board, once, 0), once);
});
test('reference seedrandom fixture stays stable', () => {
  assert.equal(new rng('hello.')(), 0.9282578795792454);
});
test('expanded bank greatly reduces measured overlap across new seeds', () => {
  const oldWords = words.slice(0, 180);
  const overlap = (bank) => {
    let total = 0;
    for (let i = 0; i < 500; i++) {
      const first = new Set(Game.generate(`overlap-a-${i}`, bank, rng).cards.map(c => c.term));
      total += Game.generate(`overlap-b-${i}`, bank, rng).cards.filter(c => first.has(c.term)).length;
    }
    return total / 500;
  };
  const before = overlap(oldWords), after = overlap(words);
  assert.ok(after < 0.6, `Average overlap too high: ${after}`);
  assert.ok(after < before / 5, `Expected a substantial improvement: ${before} -> ${after}`);
  console.log(`Average shared words between boards (500 pairs): ${before} -> ${after}`);
});
test('generated versioned banks match both TSV sources', () => {
  const context = { window: {} };
  vm.runInNewContext(fs.readFileSync('data/words.js', 'utf8'), context);
  const banks = JSON.parse(JSON.stringify(context.window.GUJARATI_WORD_BANKS));
  assert.deepEqual(banks['gu-v2'], words);
  assert.deepEqual(banks['gu-v1'], words.slice(0, 180));
  assert.equal(banks['gu-v1'].length, 180);
});
test('every card has exactly one nonempty translation per advertised language', () => {
  const context = { window: {} };
  vm.runInNewContext(fs.readFileSync('data/words.js', 'utf8'), context);
  const languages = JSON.parse(JSON.stringify(context.window.LANGUAGES));
  for (const [version, bank] of Object.entries(context.window.WORD_BANKS)) {
    for (const card of bank) {
      assert.deepEqual(Object.keys(card.translations).sort(), ['en', 'gu']);
      assert.ok(card.translations.gu.length > 0 && card.translations.en.length > 0);
      assert.ok(Object.values(card.translations).every(value => !/[;|]/.test(value)));
    }
  }
  assert.deepEqual(Object.keys(languages).sort(), ['en', 'gu']);
});
test('matches original selection, key, and row order for a known seed', () => {
  // Independent upstream procedure with a local Math to avoid polluting global RNG.
  const math = Object.create(Math); math.random = new rng('namaste');
  const context = { Math: math, sessionData: words.slice(), data: Array(980), wordsSelected: [], teams: [] };
  vm.createContext(context);
  vm.runInContext(`
    for (var i=0;i<25;i++) { var n=Math.floor(Math.random()*sessionData.length); wordsSelected.push(sessionData[n]); sessionData.splice(n,1); }
    for(var k=0;k<8;k++){ teams.push('red');teams.push('blue'); }
    teams.push(Math.floor(Math.random()*data.length)%2===0?'red':'blue');
    for(var l=0;l<7;l++)teams.push('neutral');teams.push('assassin');
    var count=teams.length;while(count!==0){var index=Math.floor(Math.random()*count);count--;var temp=teams[count];teams[count]=teams[index];teams[index]=temp;}
  `, context);
  for (let position=0;position<25;position++) {
    const index = (position % 5) * 5 + Math.floor(position / 5);
    assert.equal(board.cards[position].term, context.wordsSelected[index].term);
    assert.equal(board.cards[position].team, context.teams[index]);
  }
});
