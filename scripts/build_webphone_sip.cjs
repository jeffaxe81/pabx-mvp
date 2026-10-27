/* Reproduz o cliente SIP local com dependências fixadas em package-lock.json. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const esbuild = require('esbuild');

async function main() {
  const root = path.resolve(__dirname, '..');
  const version = require('jssip/package.json').version;
  if (version !== '3.10.1') throw new Error('versão SIP inesperada');
  const result = await esbuild.build({
    entryPoints: [require.resolve('jssip')], bundle: true, minify: true,
    format: 'iife', globalName: 'JsSIP', platform: 'browser', target: 'es2018',
    write: false, legalComments: 'eof',
    banner: { js: '/*! JsSIP 3.10.1 | MIT | https://jssip.net/ */' },
  });
  const code = Buffer.from(result.outputFiles[0].contents);
  const license = fs.readFileSync(path.join(path.dirname(require.resolve('jssip/package.json')), 'LICENSE'));
  const asset = 'vendor/jssip-3.10.1.min.js';
  const integrity = 'sha384-' + crypto.createHash('sha384').update(code).digest('base64');
  const tag = `<script src="${asset}" integrity="${integrity}" crossorigin="anonymous"></script>`;
  const htmlPath = path.join(root, 'webphone/index.html');
  const html = fs.readFileSync(htmlPath, 'utf8');
  const outputs = [[path.join(root, 'webphone', asset), code],
                   [path.join(root, 'webphone/vendor/JsSIP-LICENSE.txt'), license]];
  if (process.argv.includes('--check')) {
    for (const [filename, body] of outputs) {
      if (!fs.readFileSync(filename).equals(body)) throw new Error('bundle SIP divergente');
    }
    if (!html.includes(tag)) throw new Error('SRI do cliente SIP divergente');
    console.log('Bundle SIP local e SRI verificados.');
    return;
  }
  const pattern = /<script src="[^"]*jssip[^"]*"[^>]*><\/script>/i;
  if (!pattern.test(html)) throw new Error('referência SIP ausente');
  for (const [filename, body] of outputs) {
    fs.mkdirSync(path.dirname(filename), { recursive: true });
    fs.writeFileSync(filename, body);
  }
  fs.writeFileSync(htmlPath, html.replace(pattern, tag));
  console.log('Bundle SIP local gerado com licença e SRI.');
}

main().catch(() => { console.error('Falha ao construir/verificar cliente SIP.'); process.exitCode = 1; });
