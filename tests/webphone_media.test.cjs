const test = require('node:test');
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const fs = require('node:fs');
const vm = require('node:vm');

class Stream {
  constructor(tracks) { this.tracks = tracks; }
  getAudioTracks() { return this.tracks; }
}

for (const existing of [false,true]) {
  test(`remote track before confirmed reaches the UI (existing PC: ${existing})`, () => {
    const { bindSessionAudio } = require('../webphone/remote-audio.js');
    const session = new EventEmitter(), pc = new EventEmitter(), audio = { play:() => Promise.resolve() };
    const track = { id:'remote',kind:'audio',readyState:'live' };
    pc.addEventListener = pc.on.bind(pc); pc.getReceivers = () => [{ track }];
    if (existing) session.connection = pc;
    const refresh = bindSessionAudio(session,audio,() => true,Stream);
    session.connection = pc;
    session.emit('peerconnection',{ peerconnection:pc });
    pc.emit('track',{ track,streams:[] });
    assert.equal(audio.srcObject.getAudioTracks()[0],track);
    session.emit('confirmed');
    refresh();
    assert.equal(audio.srcObject.getAudioTracks().length,1);
  });
}

test('inactive call cannot replace focused audio, then focus attaches existing receiver', () => {
  const { bindSessionAudio } = require('../webphone/remote-audio.js');
  const session = new EventEmitter(), pc = new EventEmitter();
  const track = { id:'second',kind:'audio',readyState:'live' };
  pc.addEventListener = pc.on.bind(pc); pc.getReceivers = () => [{ track }];
  session.connection = pc;
  const audio = { srcObject:new Stream([{ id:'first' }]),play:() => Promise.resolve() };
  let focused = false;
  const refresh = bindSessionAudio(session,audio,() => focused,Stream);
  pc.emit('track',{ track,streams:[new Stream([track])] });
  assert.equal(audio.srcObject.getAudioTracks()[0].id,'first');
  focused = true; refresh();
  assert.equal(audio.srcObject.getAudioTracks()[0],track);
});

test('registration does not throw when the pinned JsSIP lacks the optional Subscriber API', () => {
  const source = fs.readFileSync(require.resolve('../webphone/index.html'),'utf8');
  const start = source.indexOf('  function startPresenceMonitoring(');
  const end = source.indexOf('  function subscribeToPresence(',start);
  const node = { style:{} };
  const context = { JsSIP:require('jssip'),el:() => node,COLLEAGUES:[{ext:'1000'}],colleagueState:{},
    renderColleagues:() => {},subscribeToPresence:() => { throw new Error('unsupported API'); } };
  vm.runInNewContext(source.slice(start,end)+';startPresenceMonitoring("localhost");',context);
  assert.match(node.innerHTML,/indisponível/i);
});
