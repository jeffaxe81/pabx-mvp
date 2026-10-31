const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

test('PWA upgrade replaces the old CDN shell and makes the pinned SIP asset available offline', async () => {
  const root = path.resolve(__dirname,'../webphone'),origin = 'https://pbx.test/webphone/';
  const stores = new Map([['telefonista-shell-v2',new Map([[origin+'index.html','old CDN shell']])], ['telefonista-shell-v3',new Map([[origin+'remote-audio.js','stale media']])]]);
  const handlers = {};
  const caches = {
    keys:async () => [...stores.keys()],delete:async key => stores.delete(key),
    open:async key => {
      if (!stores.has(key)) stores.set(key,new Map());
      return { addAll:async urls => { for (const url of urls) stores.get(key).set(new URL(url,origin).href,
        fs.readFileSync(path.join(root,url === './' ? 'index.html' : url),'utf8')); } };
    },
    match:async request => [...stores.values()].map(store => store.get(request.url)).find(Boolean),
  };
  vm.runInNewContext(fs.readFileSync(path.join(root,'service-worker.js'),'utf8'),{
    self:{ registration:{scope:origin}, addEventListener:(name,handler) => { handlers[name]=handler; },skipWaiting:() => {},clients:{ claim:() => {} } },
    caches,URL,fetch:async () => { throw new Error('offline'); },
  });
  for (const name of ['install','activate']) {
    let pending; handlers[name]({ waitUntil:promise => { pending=promise; } }); await pending;
  }
  assert.equal(stores.has('telefonista-shell-v2'),false);
  assert.equal(stores.has('telefonista-shell-v3'),false);
  assert.equal(stores.has('telefonista-shell-v4'),true);
  for (const asset of ['index.html','vendor/jssip-3.10.1.min.js','remote-audio.js']) {
    let response; handlers.fetch({ request:{url:origin+asset, method:'GET'},respondWith:promise => { response=promise; } });
    const contents = await response;
    assert.equal(typeof contents,'string');
    if (asset === 'index.html') assert.match(contents,/src="vendor\/jssip-3\.10\.1\.min\.js"/);
  }
  for (const request of [
    {url:origin+'api/recordings/', method:'GET'},
    {url:origin+'index.html', method:'POST'},
    {url:'https://other.test/webphone/index.html', method:'GET'},
    {url:origin+'index.html?live=1', method:'GET'},
  ]) {
    let intercepted = false;
    handlers.fetch({request,respondWith:() => { intercepted = true; }});
    assert.equal(intercepted,false,request.url);
  }
});
