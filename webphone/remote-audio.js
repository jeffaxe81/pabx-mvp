/* Liga a mídia recebida assim que o peer connection existe, antes do ACK SIP. */
(function (root) {
  'use strict';
  function bindSessionAudio(session, audio, isActive, Stream = root.MediaStream) {
    const watched = new WeakSet();
    function attach(track) {
      if (!isActive() || !track || track.kind !== 'audio' || track.readyState !== 'live') return;
      if (!audio.srcObject?.getAudioTracks().includes(track)) audio.srcObject = new Stream([track]);
      const playing = audio.play();
      if (playing) playing.catch(() => {});
    }
    function refresh() {
      const pc = session.connection;
      if (pc) pc.getReceivers().forEach(receiver => attach(receiver.track));
    }
    function watch(pc) {
      if (!pc || watched.has(pc)) return;
      watched.add(pc);
      pc.addEventListener('track', event => attach(event.track));
      refresh();
    }
    session.on('peerconnection', event => watch(event.peerconnection));
    session.on('accepted', refresh);
    session.on('confirmed', refresh);
    watch(session.connection);
    return refresh;
  }
  if (typeof module === 'object' && module.exports) module.exports = { bindSessionAudio };
  else root.AxeRemoteAudio = { bindSessionAudio };
})(typeof window === 'object' ? window : globalThis);
