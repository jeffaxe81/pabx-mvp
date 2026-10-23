/* Navegador real contra Asterisk: somente o microfone fornece um tom sintético. */
const fs = require('node:fs');
const path = require('node:path');
const https = require('node:https');
const { chromium } = require('playwright');

const METRICS = ['register','established','dtls','srtp','rtp','tone','audio_attached','ended'];
// RTCTransportStats usa nomes IANA DTLS-SRTP; versões antigas usavam SDES.
const CIPHERS = new Map([
  ['AES_CM_128_HMAC_SHA1_80','SRTP_AES128_CM_HMAC_SHA1_80'],
  ['AEAD_AES_128_GCM','SRTP_AEAD_AES_128_GCM'],
  ['AEAD_AES_256_GCM','SRTP_AEAD_AES_256_GCM'],
  ...['SRTP_AES128_CM_HMAC_SHA1_80','SRTP_AEAD_AES_128_GCM','SRTP_AEAD_AES_256_GCM'].map(name => [name,name]),
]);

function isRemoteAudioPlaying(audio, track) {
  return Boolean(track?.kind === 'audio' && track.readyState === 'live' && track.enabled
    && audio?.srcObject?.getAudioTracks().includes(track)
    && !audio.paused && audio.readyState >= 2 && !audio.muted && audio.volume > 0);
}

async function verifyRemoteCertificate(certificate, sdp) {
  if (!(certificate instanceof ArrayBuffer) || certificate.byteLength === 0 || certificate.byteLength > 65536
      || typeof sdp !== 'string' || sdp.length > 65536) return false;
  const sections = sdp.replace(/\r/g,'').split('\nm=');
  const audio = sections.slice(1).filter(section => section.startsWith('audio '));
  if (audio.length !== 1) return false;
  const fingerprints = audio[0].match(/^a=fingerprint:.*$/gm) || sections[0].match(/^a=fingerprint:.*$/gm) || [];
  if (fingerprints.length !== 1) return false;
  const match = fingerprints[0].match(/^a=fingerprint:sha-256[ \t]+((?:[0-9a-f]{2}:){31}[0-9a-f]{2})[ \t]*$/i);
  if (!match) return false;
  try {
    const digest = new Uint8Array(await crypto.subtle.digest('SHA-256',certificate));
    const actual = [...digest].map(byte => byte.toString(16).padStart(2,'0')).join('');
    return actual === match[1].replace(/:/g,'').toLowerCase();
  } catch (_) { return false; }
}

function describeStats(rows,remoteFingerprintVerified=false) {
  const reports = new Map(rows.map(row => [row.id,row]));
  const outbound = rows.find(row => row.type === 'outbound-rtp' && row.kind === 'audio');
  const inbound = rows.find(row => row.type === 'inbound-rtp' && row.kind === 'audio');
  const transport = reports.get(outbound?.transportId);
  const pair = reports.get(transport?.selectedCandidatePairId);
  const state = (value,allowed) => allowed.includes(value) ? value : 'unknown';
  const algorithm = id => {
    const value = reports.get(id)?.fingerprintAlgorithm;
    return value === undefined ? 'missing' : state(value,['sha-1','sha-256','sha-384','sha-512']);
  };
  return { outbound:Boolean(outbound),inbound:Boolean(inbound),
    dtls:state(transport?.dtlsState,['new','connecting','connected','closed','failed']),
    pair:state(pair?.state,['frozen','waiting','in-progress','failed','succeeded']),
    nominated:pair?.nominated === true,
    local_sha256:reports.get(transport?.localCertificateId)?.fingerprintAlgorithm === 'sha-256',
    remote_sha256:reports.get(transport?.remoteCertificateId)?.fingerprintAlgorithm === 'sha-256',
    local_algorithm:algorithm(transport?.localCertificateId),
    remote_algorithm:algorithm(transport?.remoteCertificateId),
    remote_certificate_verified:remoteFingerprintVerified === true,
    cipher_supported:CIPHERS.has(transport?.srtpCipher) };
}

function assessStats(rows,remoteFingerprintVerified=false) {
  const reports = new Map(rows.map(row => [row.id,row]));
  const outbound = rows.find(row => row.type === 'outbound-rtp' && row.kind === 'audio');
  const inbound = rows.find(row => row.type === 'inbound-rtp' && row.kind === 'audio');
  const transport = reports.get(outbound?.transportId);
  const pair = reports.get(transport?.selectedCandidatePairId);
  const local = reports.get(transport?.localCertificateId),remote = reports.get(transport?.remoteCertificateId);
  // O certificado remoto pode faltar no getStats. Só usar a prova nativa
  // DER/SDP nesse caso; uma estatística presente com outro hash reprova.
  const remoteSha256 = remote ? remote.fingerprintAlgorithm === 'sha-256' : remoteFingerprintVerified === true;
  const dtls = Boolean(transport?.dtlsState === 'connected' && inbound?.transportId === outbound?.transportId
    && pair?.state === 'succeeded' && pair?.nominated === true
    && local?.fingerprintAlgorithm === 'sha-256' && remoteSha256);
  const cipher = CIPHERS.get(transport?.srtpCipher) || '';
  const sent = Number.isFinite(outbound?.packetsSent) ? outbound.packetsSent : 0;
  const received = Number.isFinite(inbound?.packetsReceived) ? inbound.packetsReceived : 0;
  return { dtls, srtp:dtls && Boolean(cipher), rtp:dtls && sent >= 25 && received >= 25,
           cipher, packets_sent:sent, packets_received:received };
}

function requiredChecks() {
  const result = {};
  for (const tenant of ['t1','t2','t3']) {
    for (const direction of ['forward','reverse']) {
      for (const metric of METRICS) result[`webrtc_${metric}:${tenant}:${direction}`] = false;
    }
    result['webrtc_unregistered:'+tenant] = false;
  }
  for (const key of ['bundle','browser_closed','https_closed','no_page_errors']) result['webrtc_'+key] = false;
  return result;
}

function watchWebSocket(page, expected) {
  const result = { registered:0, unregistered:0, wss:false };
  const pending = new Map();
  const header = (text,key) => text.match(new RegExp('^'+key+':\\s*([^\\r\\n]+)','im'))?.[1]?.trim();
  page.on('websocket', socket => {
    if (socket.url() !== expected) return;
    result.wss = true;
    socket.on('framesent', frame => {
      const text = String(frame.payload);
      if (!text.startsWith('REGISTER ') || text.length > 65536) return;
      const id = header(text,'Call-ID'), cseq = header(text,'CSeq');
      if (id && cseq) pending.set(id+'|'+cseq,/^(?:Expires:\s*0\s*$|Contact:.*;expires=0(?:;|\s|$))/im.test(text));
    });
    socket.on('framereceived', frame => {
      const text = String(frame.payload);
      if (!text.startsWith('SIP/2.0 200 ') || text.length > 65536) return;
      const key = header(text,'Call-ID')+'|'+header(text,'CSeq');
      if (!pending.has(key)) return;
      if (pending.get(key)) result.unregistered += 1; else result.registered += 1;
      pending.delete(key);
    });
  });
  return result;
}

async function instrument(page, hz) {
  await page.addInitScript('window.__axeRemoteAudioPlaying = '+isRemoteAudioPlaying.toString()+';');
  await page.addInitScript('window.__axeVerifyRemoteCertificate = '+verifyRemoteCertificate.toString()+';');
  await page.addInitScript(({ hz }) => {
    const state = window.__axeLab = { pcs:[], contexts:[] };
    const NativePC = window.RTCPeerConnection;
    window.RTCPeerConnection = new Proxy(NativePC, { construct(Target,args) {
      const pc = new Target(...args);
      state.pcs.push(pc);
      return pc;
    }});
    navigator.mediaDevices.getUserMedia = async constraints => {
      if (!constraints.audio || constraints.video) throw new Error('audio-only lab');
      const context = new AudioContext({ sampleRate:48000 });
      const tone = context.createOscillator(), gain = context.createGain();
      const output = context.createMediaStreamDestination();
      tone.frequency.value = hz; gain.gain.value = 0.2;
      tone.connect(gain); gain.connect(output); tone.start();
      await context.resume(); state.contexts.push(context);
      return output.stream;
    };
  },{ hz });
}

async function mediaProof(page) {
  const raw = await page.evaluate(async () => {
    const state = window.__axeLab, pc = state.pcs.at(-1);
    if (!pc) return { stats:[], peak_hz:0, rms:0, audio_attached:false, local_ice:false };
    const stats = [...(await pc.getStats()).values()];
    const receiver = pc.getReceivers().find(receiver => receiver.track?.kind === 'audio');
    const track = receiver?.track;
    let remote_fingerprint_verified = false;
    if (receiver?.transport?.state === 'connected') {
      try {
        remote_fingerprint_verified = await window.__axeVerifyRemoteCertificate(
          receiver.transport.getRemoteCertificates()[0],pc.remoteDescription?.sdp);
      } catch (_) {}
    }
    const audio = document.querySelector('#remoteAudio');
    const audio_attached = window.__axeRemoteAudioPlaying(audio,track);
    if (audio_attached && state.analyserTrack !== track.id) {
      const context = new AudioContext({ sampleRate:48000 });
      const analyser = context.createAnalyser(), mute = context.createGain();
      analyser.fftSize = 2048; mute.gain.value = 0;
      context.createMediaStreamSource(new MediaStream(audio.srcObject.getAudioTracks())).connect(analyser);
      analyser.connect(mute); mute.connect(context.destination); await context.resume();
      state.analyser = analyser; state.analyserTrack = track.id; state.contexts.push(context);
    }
    let peak_hz = 0, rms = 0;
    if (audio_attached && state.analyserTrack === track.id && state.analyser) {
      const frequencies = new Float32Array(state.analyser.frequencyBinCount);
      const samples = new Float32Array(state.analyser.fftSize);
      state.analyser.getFloatFrequencyData(frequencies); state.analyser.getFloatTimeDomainData(samples);
      let peak = 1;
      for (let i=2;i<frequencies.length;i++) if (frequencies[i] > frequencies[peak]) peak = i;
      peak_hz = peak*state.analyser.context.sampleRate/state.analyser.fftSize;
      rms = Math.sqrt(samples.reduce((sum,value) => sum+value*value,0)/samples.length);
    }
    return { stats, peak_hz, rms, audio_attached,remote_fingerprint_verified,
      local_ice:(pc.getConfiguration().iceServers || []).length === 0 };
  });
  return { ...assessStats(raw.stats,raw.remote_fingerprint_verified), peak_hz:raw.peak_hz, rms:raw.rms,
           audio_attached:raw.audio_attached, local_ice:raw.local_ice,
           diagnostics:describeStats(raw.stats,raw.remote_fingerprint_verified) };
}

async function run(inputFile, outputFile) {
  const report = { schema_version:1,success:false,checks:requiredChecks(),cases:[],browser_version:'',phase:'setup' };
  const diagnostics = {};
  let context, server, pageErrors = 0;
  try {
    const cfg = JSON.parse(fs.readFileSync(inputFile,'utf8'));
    const target = new URL(cfg.wss_url);
    if (target.href !== 'wss://127.0.0.1:8089/ws' || !/^[A-Za-z0-9+/]{43}=$/.test(cfg.spki)) throw new Error('config');
    const root = fs.realpathSync(cfg.web_root);
    server = https.createServer({ cert:fs.readFileSync(cfg.cert),key:fs.readFileSync(cfg.key) },(req,res) => {
      try {
        const url = new URL(req.url,'https://127.0.0.1');
        const filename = path.resolve(root,'.'+decodeURIComponent(url.pathname === '/' ? '/index.html' : url.pathname));
        if (!filename.startsWith(root+path.sep) || !fs.statSync(filename).isFile()) throw new Error('path');
        const types = { '.html':'text/html','.js':'text/javascript','.json':'application/json','.png':'image/png' };
        res.writeHead(200,{ 'Content-Type':types[path.extname(filename)] || 'application/octet-stream','Cache-Control':'no-store' });
        res.end(fs.readFileSync(filename));
      } catch (_) { res.writeHead(404);res.end(); }
    });
    await new Promise((resolve,reject) => { server.once('error',reject);server.listen(0,'127.0.0.1',resolve); });
    const origin = 'https://127.0.0.1:'+server.address().port;
    const profile = fs.mkdtempSync(path.join(path.dirname(inputFile),'chromium-'));
    report.phase = 'browser_open';
    context = await chromium.launchPersistentContext(profile,{
      headless:true, executablePath:process.env.PABX_BROWSER_EXECUTABLE || undefined,
      ignoreHTTPSErrors:false,serviceWorkers:'block',
      args:['--no-sandbox','--disable-dev-shm-usage','--autoplay-policy=no-user-gesture-required',
            '--ignore-certificate-errors-spki-list='+cfg.spki],
    });
    report.browser_version = 'Chromium/'+context.browser().version();
    // Equivalente à permissão dada pelo operador ao getUserMedia real.
    // O microfone sintético não deve suprimir a permissão usada pelo ICE.
    await context.grantPermissions(['microphone'],{ origin });
    await context.route('**/*',route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
    let bundle = true;
    for (const tenant of ['t1','t2','t3']) {
      const pages = [await context.newPage(),await context.newPage()];
      const wires = pages.map(page => watchWebSocket(page,cfg.wss_url));
      for (let i=0;i<2;i++) {
        const page = pages[i]; page.setDefaultTimeout(15000); page.on('pageerror',() => { pageErrors += 1; });
        await instrument(page,i ? 880 : 440); await page.goto(origin+'/index.html');
        bundle = bundle && await page.evaluate(() => window.JsSIP?.version === '3.10.1');
        const endpoint = tenant+(i ? '-recepcao-2' : '-recepcao');
        await page.locator('#wssUrl').fill(cfg.wss_url); await page.locator('#extNumber').fill(endpoint);
        await page.locator('#extPassword').fill(cfg.credentials[endpoint]);
        await page.locator('#queueApiUrl').fill('');
        report.phase = 'register:'+tenant+':forward';
        await page.locator('#connectBtn').click();
        await page.waitForFunction(() => document.querySelector('#statusText').textContent.startsWith('Conectado como'));
      }
      for (const direction of ['forward','reverse']) {
        const suffix = ':'+tenant+':'+direction;
        const caller = pages[direction === 'forward' ? 0 : 1],callee = pages[direction === 'forward' ? 1 : 0];
        report.phase = 'dial'+suffix;
        report.checks['webrtc_register'+suffix] = wires.every(w => w.wss && w.registered > 0);
        for (const key of (direction === 'forward' ? '1011' : '1010')) await caller.locator('.key[data-key="'+key+'"]').click();
        await caller.locator('#callBtn').click(); await callee.locator('#answerBtn').waitFor({ state:'visible' });
        await callee.locator('#answerBtn').click();
        for (const page of pages) await page.waitForFunction(() => document.querySelector('#activeState').textContent === 'Em chamada');
        report.checks['webrtc_established'+suffix] = true;
        const establishedAt = performance.now();
        report.phase = 'media'+suffix;
        let left, right;
        // Confirmação SIP precede ICE/DTLS. O runner pode atrasar os callbacks;
        // aguardar o estado real de mídia, sempre com prazo máximo explícito.
        const mediaDeadline = performance.now()+20000;
        do {
          [left,right] = await Promise.all(pages.map(mediaProof));
          if ([left,right].every(p => p.rtp && p.audio_attached && p.rms > 0.015)
              && Math.abs(left.peak_hz-880)<70 && Math.abs(right.peak_hz-440)<70) break;
          await new Promise(resolve => setTimeout(resolve,100));
        } while (performance.now()<mediaDeadline);
        diagnostics[tenant+':'+direction] = {left:left.diagnostics,right:right.diagnostics};
        delete left.diagnostics; delete right.diagnostics;
        const proofs = [left,right];
        report.checks['webrtc_dtls'+suffix] = proofs.every(p => p.dtls);
        report.checks['webrtc_srtp'+suffix] = proofs.every(p => p.srtp);
        report.checks['webrtc_rtp'+suffix] = proofs.every(p => p.rtp && p.local_ice);
        report.checks['webrtc_tone'+suffix] = Math.abs(left.peak_hz-880)<70 && Math.abs(right.peak_hz-440)<70 && proofs.every(p => p.rms>0.015);
        report.checks['webrtc_audio_attached'+suffix] = proofs.every(p => p.audio_attached);
        report.cases.push({ tenant,direction,left,right });
        // CDR exige billsec >= 1: conservar a chamada por pelo menos 2 s.
        await new Promise(resolve => setTimeout(resolve,Math.max(0,2000-(performance.now()-establishedAt))));
        report.phase = 'hangup'+suffix;
        await caller.locator('#hangupBtn').click();
        for (const page of pages) await page.locator('#idleView').waitFor({ state:'visible' });
        report.checks['webrtc_ended'+suffix] = true;
      }
      for (const page of pages) await page.locator('#disconnectBtn').click();
      for (let attempt=0;attempt<50 && !wires.every(w => w.unregistered>0);attempt++) await new Promise(resolve => setTimeout(resolve,100));
      report.checks['webrtc_unregistered:'+tenant] = wires.every(w => w.unregistered>0);
      for (const page of pages) await page.close();
    }
    report.checks.webrtc_bundle = bundle;
  } catch (error) {
    report.error_type = ['TimeoutError','TypeError','Error'].includes(error.name) ? error.name : 'Error';
  } finally {
    if (context) {
      try { await context.close(); report.checks.webrtc_browser_closed = true; } catch (_) {}
    }
    if (server) {
      try { server.closeAllConnections(); await new Promise(resolve => server.close(resolve));report.checks.webrtc_https_closed = true; } catch (_) {}
    }
    report.checks.webrtc_no_page_errors = pageErrors === 0;
    report.success = !report.error_type && Object.values(report.checks).every(value => value === true) && report.cases.length === 6;
    if (!report.success) report.diagnostics = diagnostics;
    fs.writeFileSync(outputFile,JSON.stringify(report),{ mode:0o600 });
  }
  return report.success;
}

module.exports = { assessStats, isRemoteAudioPlaying, describeStats, verifyRemoteCertificate };
if (require.main === module) {
  run(process.argv[2],process.argv[3]).then(success => { process.exitCode = success ? 0 : 1; })
    .catch(() => { process.exitCode = 1; });
}
