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

test('a late track from an old peer cannot replace the current call audio', () => {
  const { bindSessionAudio } = require('../webphone/remote-audio.js');
  const session = new EventEmitter(), oldPc = new EventEmitter(), nextPc = new EventEmitter();
  const first = { id:'first',kind:'audio',readyState:'live' };
  const next = { id:'next',kind:'audio',readyState:'live' };
  for (const pc of [oldPc,nextPc]) {
    pc.addEventListener = pc.on.bind(pc);
    pc.getReceivers = () => [];
  }
  const audio = { srcObject:new Stream([next]), play:() => Promise.resolve() };
  session.connection = oldPc;
  bindSessionAudio(session,audio,()=>true,Stream);
  session.connection = nextPc;
  session.emit('peerconnection',{ peerconnection:nextPc });
  oldPc.emit('track',{track:first});
  assert.equal(audio.srcObject.getAudioTracks()[0], next);
});

test('a synchronous autoplay failure never crashes the SIP track handler', () => {
  const { bindSessionAudio } = require('../webphone/remote-audio.js');
  const session = new EventEmitter(), pc = new EventEmitter();
  const track = { kind:'audio',readyState:'live' };
  pc.addEventListener = pc.on.bind(pc);
  pc.getReceivers = () => [{ track }];
  session.connection = pc;
  const audio = {play:() => { throw new Error('autoplay blocked'); }};
  assert.doesNotThrow(() => bindSessionAudio(session,audio,()=>true,Stream));
  assert.equal(audio.srcObject.getAudioTracks()[0],track);
});

function mediaPeer(track) {
  const pc = new EventEmitter();
  pc.addEventListener = pc.on.bind(pc);
  pc.getReceivers = () => [{ track }];
  return pc;
}

test('WebRTC termination clears only the media owned by that call', () => {
  const { bindSessionAudio } = require('../webphone/remote-audio.js');
  const audio = { play: () => Promise.resolve() };
  const first = { kind:'audio', readyState:'live', id:'first' };
  const second = { kind:'audio', readyState:'live', id:'second' };
  const a = new EventEmitter(), b = new EventEmitter();
  a.connection = mediaPeer(first); b.connection = mediaPeer(second);
  bindSessionAudio(a, audio, () => true, Stream);
  bindSessionAudio(b, audio, () => true, Stream);
  assert.equal(audio.srcObject.getAudioTracks()[0], second);
  a.emit('ended');
  assert.equal(audio.srcObject.getAudioTracks()[0], second);
  b.emit('failed');
  assert.equal(audio.srcObject, null);
});

test('late peer events cannot restore audio after termination', () => {
  const { bindSessionAudio } = require('../webphone/remote-audio.js');
  const track = { kind:'audio', readyState:'live' }, pc = mediaPeer(track);
  const session = new EventEmitter(), audio = { play: () => Promise.resolve() };
  session.connection = pc;
  const refresh = bindSessionAudio(session,audio,()=>true,Stream);
  session.emit('ended');
  session.connection = null;
  pc.emit('track',{track});
  refresh();
  assert.equal(audio.srcObject, null);
});

test('ended track clears itself, but cannot erase a replacement track', () => {
  const { bindSessionAudio } = require('../webphone/remote-audio.js');
  const oldTrack = new EventEmitter(), newTrack = new EventEmitter();
  for (const track of [oldTrack,newTrack]) {
    track.kind='audio'; track.readyState='live';
    track.addEventListener=track.on.bind(track);
  }
  const session = new EventEmitter();
  session.connection = mediaPeer(oldTrack);
  const audio = { play: () => Promise.resolve() };
  bindSessionAudio(session,audio,()=>true,Stream);
  const nextPc = mediaPeer(newTrack);
  session.connection = nextPc;
  session.emit('peerconnection',{peerconnection:nextPc});
  oldTrack.emit('ended');
  assert.equal(audio.srcObject.getAudioTracks()[0],newTrack);
  newTrack.emit('ended');
  assert.equal(audio.srcObject,null);
});

test('a disconnected old peer event cannot replay stale media', () => {
  const { bindSessionAudio } = require('../webphone/remote-audio.js');
  const session = new EventEmitter(), oldTrack = {kind:'audio',readyState:'live'};
  const oldPc = mediaPeer(oldTrack), audio = {play:() => Promise.resolve()};
  session.connection = oldPc;
  bindSessionAudio(session,audio,()=>true,Stream);
  session.connection = null;
  audio.srcObject = null;
  oldPc.emit('track',{track:oldTrack});
  assert.equal(audio.srcObject,null);
});
