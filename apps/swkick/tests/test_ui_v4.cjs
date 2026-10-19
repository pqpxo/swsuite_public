// version 2
// Test the real SWKick client script with a small DOM stub (no browser dependency).
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '..', 'app', 'static', 'app.js'), 'utf8');

function newEnvironment(elements = {}, groups = [], fetchFn = async () => {
  throw Error('Unexpected fetch');
}) {
  const notices = [];
  let reloads = 0;
  const document = {
    getElementById: id => elements[id] ?? null,
    querySelectorAll: selector => selector === '[data-quick-credential-type]' ? groups : [],
    addEventListener: () => {},
    createElement: () => ({ textContent: '', className: '' }),
    body: { appendChild: node => notices.push(node) },
    documentElement: { dataset: { theme: 'dark' } },
  };
  // Frontend uses document.documentElement, not documentElement global.
  const ctx = {
    document, fetch: fetchFn, console,
    location: { reload: () => { reloads++; } },
    setTimeout: () => {},
    Option: function Option(text, value, defaultSelected, selected) {
      Object.assign(this, { text, value, defaultSelected, selected });
    },
    FormData: function FormData(form) { return { formMarker: form.marker }; },
  };
  vm.createContext(ctx);
  vm.runInContext(source, ctx);
  return { ctx, notices, get reloads() { return reloads; } };
}

function busyButton() {
  const attrs = { 'aria-busy': 'false' };
  return {
    disabled: false,
    getAttribute: key => attrs[key],
    setAttribute: (key, value) => { attrs[key] = value; },
  };
}

test('individual Check Updates button is busy until the remote check finishes', async () => {
  let complete;
  const remoteCheck = new Promise(resolve => { complete = resolve; });
  const button = busyButton();
  let calls = 0;
  const env = newEnvironment({}, [], async url => {
    calls++;
    if (url.endsWith('/check')) await remoteCheck;
    return {
      ok: true,
      json: async () => url.endsWith('/check')
        ? { job_id: 44 } : { status: 'success' },
    };
  });
  const work = env.ctx.checkHost(7, 'server-7', button);
  assert.equal(button.disabled, true);
  assert.equal(button.getAttribute('aria-busy'), 'true');
  // A repeated click should not schedule a second update check.
  await env.ctx.checkHost(7, 'server-7', button);
  assert.equal(calls, 1);
  complete();
  await work;
  assert.equal(calls, 2);
  assert.equal(button.disabled, false);
  assert.equal(button.getAttribute('aria-busy'), 'false');
  assert.equal(env.reloads, 1);
});

test('a failed individual host check stops the loading indicator', async () => {
  const button = busyButton();
  const env = newEnvironment({}, [], async () => ({
    ok: false, status: 503, json: async () => ({ detail: 'SSH unavailable' }),
  }));
  await env.ctx.checkHost(1, 'server', button);
  assert.equal(button.disabled, false);
  assert.equal(button.getAttribute('aria-busy'), 'false');
  assert.equal(env.reloads, 0);
  assert.equal(env.notices.at(-1).textContent, 'SSH unavailable');
});

test('creating a credential in the dialog keeps the unfinished host unchanged', async () => {
  let hostResets = 0;
  let credentialResets = 0;
  const host = { name: 'unsaved-host', hostname: '10.0.0.50',
    reset: () => { hostResets++; } };
  const typeField = { value: 'password' };
  const loginPassword = { name: 'password', disabled: false, required: true };
  const sshPrivateKey = { name: 'private_key', disabled: true, required: false };
  const sshPassphrase = { name: 'passphrase', disabled: true, required: false };
  const passwordGroup = {
    dataset: { quickCredentialType: 'password' },
    hidden: false,
    querySelectorAll: () => [loginPassword],
  };
  const keyGroup = {
    dataset: { quickCredentialType: 'ssh_key' },
    hidden: true,
    querySelectorAll: () => [sshPrivateKey, sshPassphrase],
  };
  const select = {
    options: [],
    add(option) { this.options.push(option); },
    value: '',
  };
  const dialog = {
    open: false,
    showModal() { this.open = true; },
    close() { this.open = false; },
  };
  const credentialForm = {
    action: '/credentials/quick-create', marker: 'credential-only',
    reset() { credentialResets++; },
  };
  const save = busyButton();
  const error = { hidden: true, textContent: '' };
  const elems = {
    'host-form': host,
    'host-credential': select,
    'quick-credential-dialog': dialog,
    'quick-credential-error': error,
    'quick-credential-form': credentialForm,
    'quick-credential-save': save,
    'quick-credential-type': typeField,
    'quick-credential-name': { focus: () => {} },
  };
  let request;
  const env = newEnvironment(elems, [passwordGroup, keyGroup], async (url, opts) => {
    request = { url, opts };
    return {
      ok: true,
      json: async () => ({ id: 50, name: 'New key', type: 'password' }),
    };
  });
  env.ctx.openCredentialDialog();
  assert.equal(dialog.open, true);
  let prevented = false;
  await env.ctx.saveQuickCredential({ preventDefault: () => { prevented = true; } });
  assert.equal(prevented, true);
  assert.equal(request.url, '/credentials/quick-create');
  assert.equal(request.opts.method, 'POST');
  assert.equal(request.opts.body.formMarker, 'credential-only');
  assert.equal(credentialResets, 1);
  assert.equal(hostResets, 0);
  assert.equal(host.name, 'unsaved-host');
  assert.equal(host.hostname, '10.0.0.50');
  assert.equal(select.value, '50');
  assert.equal(select.options[0].text, 'New key');
  assert.equal(dialog.open, false);

  typeField.value = 'ssh_key';
  env.ctx.syncQuickCredentialFields();
  assert.equal(loginPassword.disabled, true);
  assert.equal(loginPassword.required, false);
  assert.equal(sshPrivateKey.disabled, false);
  assert.equal(sshPrivateKey.required, true);
});

test('modal failure keeps entered credentials and host form intact', async () => {
  let resets = 0;
  const save = busyButton();
  const error = { hidden: true, textContent: '' };
  const form = { action: '/credentials/quick-create', marker: 'draft',
    reset: () => { resets++; } };
  const elems = {
    'quick-credential-form': form,
    'quick-credential-save': save,
    'quick-credential-error': error,
  };
  const env = newEnvironment(elems, [], async () => ({
    ok: false, status: 422,
    json: async () => ({ detail: 'Enter an SSH login password' }),
  }));
  await env.ctx.saveQuickCredential({ preventDefault: () => {} });
  assert.equal(resets, 0);
  assert.equal(error.hidden, false);
  assert.equal(error.textContent, 'Enter an SSH login password');
  assert.equal(save.disabled, false);
});

test('requests stay under the SWSuite mount path from <html data-base>', async () => {
  const urls = [];
  const env = newEnvironment({}, [], async url => {
    urls.push(url);
    return { ok: true, json: async () => url.endsWith('/check') ? { job_id: 9 } : { status: 'success' } };
  });
  env.ctx.document.documentElement.dataset.base = '/kick';
  await env.ctx.checkHost(3, 'server-3');
  assert.deepEqual(urls, ['/kick/hosts/3/check', '/kick/jobs/9/output']);
  // Standalone (no data-base): unchanged root-relative paths.
  delete env.ctx.document.documentElement.dataset.base;
  assert.equal(env.ctx.url('/check-all'), '/check-all');
});
