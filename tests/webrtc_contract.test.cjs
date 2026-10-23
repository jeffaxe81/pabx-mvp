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
  assert.equal(valid.cipher,'SRTP_AES128_CM_HMAC_SHA1_80');
  assert.equal(valid.rtp, true);
  assert.equal(valid.packets_sent, 100);
  assert.equal(valid.packets_received, 90);
  assert.equal(assessStats([]).rtp, false);
  for (const cipher of ['SRTP_AES128_CM_HMAC_SHA1_80','SRTP_AEAD_AES_128_GCM','SRTP_AEAD_AES_256_GCM']) {
    const rows = stats(); rows.find(row => row.id === 'transport').srtpCipher = cipher;
    assert.equal(assessStats(rows).cipher,cipher);
    assert.equal(assessStats(rows).srtp,true);
  }
  for (const [id, key, value, failing] of [
    ['transport','dtlsState','new','dtls'], ['transport','srtpCipher','NONE','srtp'],
    ['transport','srtpCipher','SRTP_NULL_HMAC_SHA1_80','srtp'],
    ['pair','state','failed','dtls'], ['remoteCert','fingerprintAlgorithm','sha-1','dtls'],
    ['in','packetsReceived',0,'rtp'], ['in','transportId','another','dtls'],
  ]) {
    const rows = stats();
    rows.find(row => row.id === id)[key] = value;
    assert.equal(assessStats(rows)[failing], false);
  }
});

test('UI audio proof rejects a local/wrong track and disabled playback', () => {
  const { isRemoteAudioPlaying } = require('../lab/webrtc_browser.cjs');
  const track = { id:'remote',kind:'audio',readyState:'live',enabled:true };
  const valid = () => ({ srcObject:{ getAudioTracks:() => [track] },paused:false,readyState:4,muted:false,volume:1 });
  assert.equal(isRemoteAudioPlaying(valid(),track),true);
  assert.equal(isRemoteAudioPlaying({ ...valid(),srcObject:{getAudioTracks:() => [{...track,id:'local'}]} },track),false);
  for (const change of [{muted:true},{volume:0},{paused:true},{readyState:1}])
    assert.equal(isRemoteAudioPlaying({...valid(),...change},track),false);
  track.enabled = false;
  assert.equal(isRemoteAudioPlaying(valid(),track),false);
});

test('transport diagnostics expose only fixed states and booleans', () => {
  const { describeStats } = require('../lab/webrtc_browser.cjs');
  assert.deepEqual(describeStats(stats()),{ outbound:true,inbound:true,dtls:'connected',pair:'succeeded',
    nominated:true,local_sha256:true,remote_sha256:true,cipher_supported:true,
    local_algorithm:'sha-256',remote_algorithm:'sha-256',remote_certificate_verified:false });
  const rows = stats(); rows.find(row => row.id === 'transport').dtlsState = 'private-value';
  assert.equal(describeStats(rows).dtls,'unknown');
  assert.equal(JSON.stringify(describeStats(rows)).includes('private-value'),false);
});

test('missing remote certificate stats require a native certificate fingerprint proof', () => {
  const { assessStats } = require('../lab/webrtc_browser.cjs');
  const rows = stats().filter(row => row.id !== 'remoteCert');
  assert.equal(assessStats(rows).dtls,false);
  assert.equal(assessStats(rows,true).dtls,true);
  assert.equal(assessStats(rows,'true').dtls,false);
  const wrong = stats(); wrong.find(row => row.id === 'remoteCert').fingerprintAlgorithm = 'sha-1';
  assert.equal(assessStats(wrong,true).dtls,false);
});

test('native remote certificate proof hashes DER and matches the audio SDP fingerprint', async () => {
  const { verifyRemoteCertificate } = require('../lab/webrtc_browser.cjs');
  const certificate = new TextEncoder().encode('abc').buffer;
  const fingerprint = 'BA:78:16:BF:8F:01:CF:EA:41:41:40:DE:5D:AE:22:23:B0:03:61:A3:96:17:7A:9C:B4:10:FF:61:F2:00:15:AD';
  const header = 'v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 0\r\n';
  const line = 'a=fingerprint:sha-256 '+fingerprint+'\r\n';
  assert.equal(await verifyRemoteCertificate(certificate,header+line),true);
  assert.equal(await verifyRemoteCertificate(certificate,'v=0\r\n'+line+'m=audio 9 UDP/TLS/RTP/SAVPF 0\r\n'),true);
  for (const invalid of [header+line.replace('sha-256','sha-1'),header+line.replace('BA:78','BA:79'),
    header+line+line,header.replace('audio','video')+line,header+line.replace(':AD',':ZZ')])
    assert.equal(await verifyRemoteCertificate(certificate,invalid),false);
  assert.equal(await verifyRemoteCertificate(new ArrayBuffer(0),header+line),false);
  assert.equal(await verifyRemoteCertificate(new TextEncoder().encode('wrong').buffer,header+line),false);
});
