/* "Try new features" section (style/try-features.js, wizard-os#627): render, hide, flip, vote, errors. */
const assert = require('node:assert/strict');
const T = require('./try-features.js');

const listing = (extra = {}) => ({ contract: 'wizard.app-switches/1', switches: [
  { id: 'drag-events', name: 'Drag events', description: 'Move events <by> dragging', on: false, default: false, vote: null, tried: false, issues: ['humanitylabs-org/wizard-calendar#1'], ...extra },
  { id: 'old-app', name: 'No votes here', on: true },
] });

// Render: standard title + note, one row per switch, thumbs only where the app keeps votes, escaped text.
const h = T.html(listing());
assert.match(h, /Try new features/);
assert.match(h, /Approved ones become part of the app; the rest go away\. Thumbs up the ones you like\./);
assert.equal((h.match(/data-try-id=/g) || []).length, 2);
assert.equal((h.match(/data-try-vote=/g) || []).length, 2, 'only the switch with a vote field gets thumbs');
assert.match(h, /&lt;by&gt;/); assert.doesNotMatch(h, /<by>/);
assert.match(h, /data-try-id="old-app"[\s\S]*aria-checked="true"/);
// Hidden when the app has no switches or the listing is broken.
for (const bad of [null, {}, { switches: [] }, { switches: [{}, { id: '' }] }]) assert.equal(T.html(bad), '');

// Tap bodies: flip, vote, tapping the active thumb clears it, no vote for apps without votes.
assert.deepEqual(T.body(listing(), 'drag-events', 'toggle'), { id: 'drag-events', on: true });
assert.deepEqual(T.body(listing(), 'drag-events', 'up'), { id: 'drag-events', vote: 'up' });
assert.deepEqual(T.body(listing({ vote: 'up' }), 'drag-events', 'up'), { id: 'drag-events', vote: null });
assert.deepEqual(T.body(listing({ vote: 'up' }), 'drag-events', 'down'), { id: 'drag-events', vote: 'down' });
assert.equal(T.body(listing(), 'old-app', 'up'), null);
assert.equal(T.body(listing(), 'missing', 'toggle'), null);

// Mount with a fake element, document and fetch.
function fakeEl() {
  const listeners = {}; const classes = new Set();
  return { innerHTML: '', hidden: false, classList: { add: (...c) => c.forEach(x => classes.add(x)) }, classes,
    addEventListener: (n, fn) => { listeners[n] = fn; }, listeners, querySelectorAll: () => [] };
}
function fakeDoc() {
  const listeners = {}; const head = { kids: [], appendChild: n => head.kids.push(n) };
  return { head, visibilityState: 'visible', listeners, getElementById: id => head.kids.find(k => k.id === id) || null,
    createElement: () => ({}), addEventListener: (n, fn) => { (listeners[n] = listeners[n] || []).push(fn); } };
}
const res = (status, data) => ({ ok: status >= 200 && status < 300, status, json: async () => data });
function tap(el, id, attrs) { const row = { getAttribute: () => id }; const b = { hasAttribute: a => a in attrs, getAttribute: a => attrs[a] }; b.closest = sel => (sel === 'button' ? b : row); el.listeners.click({ target: b }); }

(async () => {
  let state = listing(); const calls = [];
  const fetch = async (path, init = {}) => {
    calls.push({ path, init });
    if (init.method === 'POST') {
      const b = JSON.parse(init.body);
      if (b.id === 'boom') return res(500, { error: 'nope' });
      const s = state.switches.find(x => x.id === b.id);
      if ('on' in b) { s.on = b.on; if (b.on) s.tried = true; }
      if ('vote' in b) s.vote = b.vote;
      return res(200, state);
    }
    return res(200, state);
  };
  const el = fakeEl(), doc = fakeDoc();
  const m = T.mount(el, { path: 'api/switches', fetch, document: doc });
  assert.equal(el.hidden, true, 'hidden until the listing arrives');
  await m.ready;
  assert.equal(el.hidden, false); assert.match(el.innerHTML, /Drag events/);
  assert.ok(el.classes.has('wz-try') && el.classes.has('wz-sec'));
  assert.equal(doc.head.kids.length, 1); T.mount(fakeEl(), { fetch, document: doc }); assert.equal(doc.head.kids.length, 1, 'CSS injected once');
  assert.equal(calls[0].path, 'api/switches'); assert.equal(calls[0].init.method, undefined);

  await m.send('drag-events', 'toggle');
  const post = calls.find(c => c.init.method === 'POST');
  assert.equal(post.init.headers['X-Wizard-Switch'], '1'); assert.equal(post.init.headers['Content-Type'], 'application/json');
  assert.deepEqual(JSON.parse(post.init.body), { id: 'drag-events', on: true });
  assert.match(el.innerHTML, /data-try-id="drag-events"[\s\S]*?aria-checked="true"/);

  await m.send('drag-events', 'up');
  assert.equal(state.switches[0].vote, 'up');
  assert.match(el.innerHTML, /data-try-vote="up" aria-pressed="true"/);
  await m.send('drag-events', 'up');
  assert.equal(state.switches[0].vote, null, 'second tap clears the thumb');

  // Click delegation reaches the same path.
  const before = calls.length; tap(el, 'drag-events', { 'data-try-vote': 'down' }); await new Promise(r => setTimeout(r, 0)); await new Promise(r => setTimeout(r, 0));
  assert.equal(calls.length, before + 1); assert.equal(state.switches[0].vote, 'down');

  // A failed save keeps the last good listing and shows the error.
  state.switches.push({ id: 'boom', name: 'Boom', on: false });
  await m.reload(); await m.send('boom', 'toggle');
  assert.match(el.innerHTML, /role="alert">nope</); assert.match(el.innerHTML, /Drag events/);

  // Approving or dropping removes the switch from the listing: it leaves the section; none left hides it.
  state = { contract: 'wizard.app-switches/1', switches: [] };
  doc.listeners.visibilitychange.forEach(fn => fn()); await new Promise(r => setTimeout(r, 0)); await new Promise(r => setTimeout(r, 0));
  assert.equal(el.hidden, true); assert.equal(el.innerHTML, '');
  // wizard-os#916: a re-read that started before a save, or lands while it is in flight, never paints the old state.
  {
    let box = listing(); const gets = [], posts = [];
    const snap = () => res(200, JSON.parse(JSON.stringify(box)));
    const f2 = (p, init = {}) => {
      if (init.method === 'POST') return new Promise(r => posts.push(() => { const b = JSON.parse(init.body); box.switches.find(x => x.id === b.id).on = b.on; r(snap()); }));
      const s = snap(); return new Promise(r => gets.push(() => r(s)));
    };
    const el2 = fakeEl(), doc2 = fakeDoc();
    const m2 = T.mount(el2, { fetch: f2, document: doc2 }); gets.shift()(); await m2.ready;
    const stale = m2.reload();                        // read sent while the box still says Off
    const save = m2.send('drag-events', 'toggle');    // the flip
    doc2.listeners.visibilitychange.forEach(fn => fn()); // page visible again during the save: no second read
    assert.equal(gets.length, 1, 'no re-read is sent while a save is in flight');
    posts.shift()(); await save;
    assert.match(el2.innerHTML, /data-try-id="drag-events"[\s\S]*?aria-checked="true"/);
    gets.shift()(); await stale;                      // the older read answers last
    assert.equal(m2.listing.switches[0].on, true, 'older read dropped');
    assert.match(el2.innerHTML, /data-try-id="drag-events"[\s\S]*?aria-checked="true"/, 'switch does not look reverted');
    box.switches[0].on = false;                       // flipped from the Tracker; a later read still shows it
    const later = m2.reload(); gets.shift()(); await later;
    assert.match(el2.innerHTML, /data-try-id="drag-events"[\s\S]*?aria-checked="false"/);
  }
  console.log('PASS: try-features section renders, hides, flips, votes and re-reads');
})().catch(e => { console.error(e); process.exit(1); });
