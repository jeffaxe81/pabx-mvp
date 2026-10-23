const test = require('node:test');
const assert = require('node:assert/strict');

function stats() {
  return [
    { id: 'out', type: 'outbound-rtp', kind: 'audio', transportId: 'transport', packetsSent: 100 },
    { id: 'in', type: 'inbound-rtp', kind: 'audio', transportId: 'transport', packetsReceived: 90 },
    { id: 'transport', type: 'transport', dtlsState: 'connected', srtpCipher: 'AES_CM_128_HMAC_SHA1_80',
      selectedCandidatePairId: 'pair', localCertificateId: 'localCert', remoteCertificateId: 'remoteCert' },
    { id: 'pair', type: 'candidate-pair', state: 'succeeded', nominated: true },
    { id: 'localCert', type: 'certificate', fingerprintAlgorithm: 'sha-256' },
    { id: 'remoteCert', type: 'certificate', fingerprintAlgorithm: 'sha-256' },
  ];
}

test('WebRTC evidence requires correlated DTLS, fingerprints, SRTP and both RTP directions', () => {
  const { assessStats } = require('../lab/webrtc_browser.cjs');
  const valid = assessStats(stats());
  assert.equal(valid.dtls, true);
  assert.equal(valid.srtp, true);
  assert.equal(valid.rtp, true);
  assert.equal(valid.packets_sent, 100);
  assert.equal(valid.packets_received, 90);
  assert.equal(assessStats([]).rtp, false);
  for (const [id, key, value, failing] of [
    ['transport','dtlsState','new','dtls'], ['transport','srtpCipher','NONE','srtp'],
    ['pair','state','failed','dtls'], ['remoteCert','fingerprintAlgorithm','sha-1','dtls'],
    ['in','packetsReceived',0,'rtp'], ['in','transportId','another','dtls'],
  ]) {
    const rows = stats();
    rows.find(row => row.id === id)[key] = value;
    assert.equal(assessStats(rows)[failing], false);
  }
});
