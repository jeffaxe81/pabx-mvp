/* Liga a mídia recebida assim que o peer connection existe, antes do ACK SIP. */
(function (root) {
  'use strict';
  function bindSessionAudio(session, audio, isActive, Stream = root.MediaStream) {
    const watched = new WeakSet();
    function attach(track) {
      if (!isActive() || !track || track.kind !== 'audio' || track.readyState !== 'live') return;
      if (!audio.srcObject?.getAudioTracks().includes(track)) audio.srcObject = new Stream([track]);
      // O navegador pode bloquear autoplay ou lançar erro síncrono.
      try {
        const playing = audio.play();
        if (playing && typeof playing.catch === 'function') playing.catch(() => {});
      } catch (_) { /* mídia anexada, gesto do usuário pode iniciar depois */ }
    }
    function refresh() {
      const pc = session.connection;
      if (pc && typeof pc.getReceivers === 'function')
        pc.getReceivers().forEach(receiver => attach(receiver.track));
    }
    function watch(pc) {
      if (!pc || watched.has(pc)) return;
      watched.add(pc);
      pc.addEventListener('track', event => {
      // Eventos pendentes de uma conexão antiga não podem substituir o áudio.
      if (session.connection && session.connection !== pc) return;
      attach(event.track);
    });
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
