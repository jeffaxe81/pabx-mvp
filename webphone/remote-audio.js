/* Áudio WebRTC isolado por sessão, sem reutilizar mídia de uma chamada encerrada. */
(function (root) {
  'use strict';

  function bindSessionAudio(session, audio, isActive, Stream = root.MediaStream) {
    const watchedPeers = new WeakSet();
    const watchedTracks = new WeakSet();
    let finished = false;
    let ownedTrack = null;

    function hasTrack(track) {
      const stream = audio.srcObject;
      return !!stream && typeof stream.getAudioTracks === 'function' &&
        stream.getAudioTracks().includes(track);
    }

    function clearOwnedAudio() {
      // O mesmo <audio> é compartilhado entre linhas/consulta: nunca limpar outra sessão.
      if (ownedTrack && hasTrack(ownedTrack)) audio.srcObject = null;
      ownedTrack = null;
    }

    function attach(track) {
      if (finished || !isActive() || !track ||
          track.kind !== 'audio' || track.readyState !== 'live') return;

      if (!hasTrack(track)) audio.srcObject = new Stream([track]);
      ownedTrack = track;
      if (typeof track.addEventListener === 'function' && !watchedTracks.has(track)) {
        watchedTracks.add(track);
        track.addEventListener('ended', () => {
          if (hasTrack(track)) audio.srcObject = null;
          if (ownedTrack === track) ownedTrack = null;
        }, { once: true });
      }

      // Autoplay pode falhar por política do navegador; um gesto do usuário pode retomar.
      try {
        const playing = audio.play();
        if (playing && typeof playing.catch === 'function') playing.catch(() => {});
      } catch (_) { /* preserva a trilha anexada sem interromper SIP */ }
    }

    function refresh() {
      if (finished) return;
      const pc = session.connection;
      if (pc && typeof pc.getReceivers === 'function') {
        pc.getReceivers().forEach(receiver => attach(receiver.track));
      }
    }

    function watch(pc) {
      if (!pc || watchedPeers.has(pc) || typeof pc.addEventListener !== 'function') return;
      watchedPeers.add(pc);
      pc.addEventListener('track', event => {
        // Ignorar callbacks de uma conexão já substituída ou desligada.
        if (finished || session.connection !== pc) return;
        attach(event.track);
      });
      if (session.connection === pc) refresh();
    }

    function terminate() {
      finished = true;
      clearOwnedAudio();
    }

    session.on('peerconnection', event => watch(event.peerconnection));
    session.on('accepted', refresh);
    session.on('confirmed', refresh);
    session.on('ended', terminate);
    session.on('failed', terminate);
    watch(session.connection);
    return refresh;
  }

  if (typeof module === 'object' && module.exports) module.exports = { bindSessionAudio };
  else root.AxeRemoteAudio = { bindSessionAudio };
})(typeof window === 'object' ? window : globalThis);
