// Headless page runner (DESIGN.md 3.14).
//
//   node tools/uirun.js < scenario.json
//
// Runs the REAL src/chatbook/core/static/cb.js and the given feature ui.js files in a Node vm
// context whose only non-built-in global is __CB_HOST__ (a fake host: fake DOM, in-memory
// storage, a clock that moves only on "tick", timers that fire only on "tick", fetch answered
// from the scenario's "api" table). Each feature file is wrapped exactly as the server wraps
// /ui/<feature>.js. Prints one JSON result on stdout (exit 0); a runner crash prints a stack
// trace on stderr (exit 1). Scenario problems are reported as "scenario: ..." entries in
// "errors". Nothing is written to disk.
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const START_MS = 1700000000000;
const DEFAULT_CB = path.join(__dirname, '..', 'src', 'chatbook', 'core', 'static', 'cb.js');
const INLINE_TAGS = new Set(['b', 'strong', 'i', 'em', 'code']);
const WRAP_LINES = 2; // "(() => {" and "'use strict';" come before a feature file's text
const SCENARIO_KEYS = ['cb', 'files', 'me', 'token', 'page', 'params', 'api', 'steps',
  'load_all'];
const STEP_KINDS = ['click', 'click_id', 'fill', 'submit', 'tick', 'go'];
const STEP_EXTRA = {
  click: ['nth'],
  click_id: ['nth'],
  fill: ['values', 'nth'],
  submit: ['values', 'nth'],
  tick: [],
  go: ['params'],
};

// Recorded for the result. Module level: unhandled rejections land here too.
const rec = {
  calls: [],
  unmatched: [],
  nav: [],
  toasts: [],
  badges: {},
  session: [],
  errors: [],
};

function hasOwn(obj, key) {
  return obj !== null && typeof obj === 'object' && Object.prototype.hasOwnProperty.call(obj, key);
}

function isObject(x) {
  return x !== null && typeof x === 'object' && !Array.isArray(x);
}

function messageOf(err) {
  if (err !== null && typeof err === 'object' && typeof err.message === 'string') {
    return err.message;
  }
  return String(err);
}

// An "errors" entry: the message plus, when the stack passes through a feature file, where
// ("... (at /ui/page_chat.js:14:22)"), so a failing test names the line to fix. Stack lines
// count the served (wrapped) code, which has WRAP_LINES lines before the file's first line.
function errorText(err, message) {
  const text = message === undefined ? messageOf(err) : String(message);
  const stack = err !== null && typeof err === 'object' && typeof err.stack === 'string'
    ? err.stack : '';
  const m = /(\/ui\/[\w.-]+\.js):(\d+)(?::(\d+))?/.exec(stack);
  if (m === null) return text;
  const at = m[1] + ':' + Math.max(1, Number(m[2]) - WRAP_LINES) +
    (m[3] === undefined ? '' : ':' + m[3]);
  return text.includes(at) ? text : text + ' (at ' + at + ')';
}

function scenarioError(message) {
  rec.errors.push('scenario: ' + message);
}

// ------------------------------------------------------------------------------------ fake DOM

class FakeNode {
  constructor(doc, nodeType) {
    this.ownerDocument = doc;
    this.nodeType = nodeType;
    this.parentNode = null;
  }

  get parentElement() {
    return this.parentNode;
  }

  get isConnected() {
    for (let n = this; n !== null; n = n.parentNode) {
      if (n === this.ownerDocument.body) return true;
    }
    return false;
  }

  remove() {
    if (this.parentNode !== null) this.parentNode.removeChild(this);
  }
}

class FakeText extends FakeNode {
  constructor(doc, data) {
    super(doc, 3);
    this.data = String(data);
  }

  get nodeValue() {
    return this.data;
  }

  get textContent() {
    return this.data;
  }

  set textContent(value) {
    this.data = value === null || value === undefined ? '' : String(value);
  }
}

class FakeElement extends FakeNode {
  constructor(doc, tag) {
    super(doc, 1);
    this.localName = tag;
    this.tagName = tag.toUpperCase();
    this.childNodes = [];
    this.attrs = new Map();
    this.listeners = new Map();
    this.checked = false;
    this.disabled = false;
    this.scrollTop = 0;
    this.clientHeight = 0;
    this.selectionStart = 0;
    this.selectionEnd = 0;
    this.ownValue = undefined;
    this.handler = null; // the onclick property
  }

  // attributes
  setAttribute(name, value) {
    this.attrs.set(String(name).toLowerCase(), String(value));
  }

  getAttribute(name) {
    const v = this.attrs.get(String(name).toLowerCase());
    return v === undefined ? null : v;
  }

  hasAttribute(name) {
    return this.attrs.has(String(name).toLowerCase());
  }

  removeAttribute(name) {
    this.attrs.delete(String(name).toLowerCase());
  }

  get className() {
    return this.getAttribute('class') || '';
  }

  set className(value) {
    this.setAttribute('class', value);
  }

  get id() {
    return this.getAttribute('id') || '';
  }

  set id(value) {
    this.setAttribute('id', value);
  }

  get hidden() {
    return this.hasAttribute('hidden');
  }

  set hidden(value) {
    if (value) this.setAttribute('hidden', '');
    else this.removeAttribute('hidden');
  }

  get title() {
    return this.getAttribute('title') || '';
  }

  set title(value) {
    this.setAttribute('title', value);
  }

  get type() {
    const t = this.getAttribute('type');
    if (t !== null) return t.toLowerCase();
    if (this.localName === 'button') return 'submit';
    return this.localName === 'input' ? 'text' : '';
  }

  set type(value) {
    this.setAttribute('type', value);
  }

  get name() {
    return this.getAttribute('name') || '';
  }

  set name(value) {
    this.setAttribute('name', value);
  }

  // tree
  get children() {
    return this.childNodes.filter((n) => n.nodeType === 1);
  }

  get firstChild() {
    return this.childNodes.length ? this.childNodes[0] : null;
  }

  get lastChild() {
    return this.childNodes.length ? this.childNodes[this.childNodes.length - 1] : null;
  }

  coerce(node) {
    if (node instanceof FakeNode) return node;
    return new FakeText(this.ownerDocument, node);
  }

  insert(node) {
    if (node instanceof FakeElement && node.contains(this)) {
      throw new Error('HierarchyRequestError: a node cannot contain itself');
    }
    if (node.parentNode !== null) node.parentNode.removeChild(node);
    node.parentNode = this;
    this.childNodes.push(node);
  }

  append(...nodes) {
    for (const n of nodes) this.insert(this.coerce(n));
  }

  appendChild(node) {
    this.insert(this.coerce(node));
    return node;
  }

  removeChild(node) {
    const i = this.childNodes.indexOf(node);
    if (i < 0) throw new Error('NotFoundError: the node is not a child of this element');
    this.childNodes.splice(i, 1);
    node.parentNode = null;
    return node;
  }

  replaceChildren(...nodes) {
    const list = nodes.map((n) => this.coerce(n));
    for (const c of this.childNodes) c.parentNode = null;
    this.childNodes = [];
    for (const n of list) this.insert(n);
  }

  contains(node) {
    for (let n = node; n !== null && n !== undefined; n = n.parentNode) {
      if (n === this) return true;
    }
    return false;
  }

  // text
  get textContent() {
    return this.childNodes.map((c) => c.textContent).join('');
  }

  set textContent(value) {
    this.replaceChildren();
    const s = value === null || value === undefined ? '' : String(value);
    if (s !== '') this.append(s);
  }

  get innerText() {
    return this.textContent;
  }

  set innerText(value) {
    this.textContent = value;
  }

  // form controls
  optionElements() {
    return descendants(this).filter((e) => e.localName === 'option');
  }

  get value() {
    if (this.localName === 'select') {
      const values = this.optionElements().map((o) => o.value);
      if (this.ownValue !== undefined && values.includes(this.ownValue)) return this.ownValue;
      return values.length ? values[0] : '';
    }
    if (this.ownValue !== undefined) return this.ownValue;
    const attr = this.getAttribute('value');
    if (attr !== null) return attr;
    if (this.localName === 'option' || this.localName === 'textarea') return this.textContent;
    if (this.localName === 'input' && (this.type === 'checkbox' || this.type === 'radio')) {
      return 'on';
    }
    return '';
  }

  set value(v) {
    this.ownValue = v === null || v === undefined ? '' : String(v);
  }

  get scrollHeight() {
    return 20 * this.childNodes.length;
  }

  focus() {
    this.ownerDocument.activeElement = this;
  }

  blur() {
    if (this.ownerDocument.activeElement === this) this.ownerDocument.activeElement = null;
  }

  setSelectionRange(start, end) {
    this.selectionStart = Number(start) || 0;
    this.selectionEnd = Number(end) || 0;
  }

  // events
  addEventListener(type, fn) {
    if (typeof fn !== 'function') return;
    const list = this.listeners.get(type) || [];
    if (!list.includes(fn)) list.push(fn);
    this.listeners.set(type, list);
  }

  removeEventListener(type, fn) {
    const list = this.listeners.get(type) || [];
    this.listeners.set(type, list.filter((f) => f !== fn));
  }

  get onclick() {
    return this.handler;
  }

  set onclick(fn) {
    this.handler = typeof fn === 'function' ? fn : null;
  }

  click() {
    dispatchClick(this);
  }

  isClickable() {
    return this.localName === 'button' || this.handler !== null ||
      (this.listeners.get('click') || []).length > 0;
  }
}

class FakeDocument {
  constructor() {
    this.activeElement = null;
    this.body = new FakeElement(this, 'body');
  }

  createElement(tag) {
    return new FakeElement(this, String(tag).toLowerCase());
  }

  createTextNode(data) {
    return new FakeText(this, data);
  }
}

// Elements below `root` in tree order (pre-order), `root` excluded.
function descendants(root) {
  const out = [];
  const visit = (n) => {
    for (const c of n.childNodes) {
      if (c.nodeType !== 1) continue;
      out.push(c);
      visit(c);
    }
  };
  visit(root);
  return out;
}

function closest(node, tag) {
  for (let n = node.parentNode; n !== null; n = n.parentNode) {
    if (n.localName === tag) return n;
  }
  return null;
}

function makeEvent(type, target) {
  return {
    type,
    target,
    currentTarget: null,
    bubbles: true,
    cancelable: true,
    defaultPrevented: false,
    stopped: false,
    stoppedNow: false,
    key: undefined,
    button: 0,
    ctrlKey: false,
    metaKey: false,
    shiftKey: false,
    altKey: false,
    preventDefault() {
      this.defaultPrevented = true;
    },
    stopPropagation() {
      this.stopped = true;
    },
    stopImmediatePropagation() {
      this.stopped = true;
      this.stoppedNow = true;
    },
  };
}

// Dispatches a bubbling event like the browser: listeners of the target, then of each ancestor.
function dispatch(target, type) {
  const ev = makeEvent(type, target);
  for (let node = target; node !== null; node = node.parentNode) {
    ev.currentTarget = node;
    const fns = (node.listeners.get(type) || []).slice();
    if (type === 'click' && node.handler !== null) fns.push(node.handler);
    for (const fn of fns) {
      try {
        fn.call(node, ev);
      } catch (err) {
        rec.errors.push(errorText(err));
      }
      if (ev.stoppedNow) break;
    }
    if (ev.stopped) break;
  }
  return ev;
}

// A click, then the browser's default action: a submit button submits its form.
function dispatchClick(target) {
  const ev = dispatch(target, 'click');
  if (ev.defaultPrevented) return;
  if (target.localName === 'button' && target.type === 'submit' && !target.disabled) {
    const form = closest(target, 'form');
    if (form !== null) dispatch(form, 'submit');
  }
}

// ------------------------------------------------------------------------------------ reading

// Collapsed text: text nodes in tree order; every element except b/strong/i/em/code adds a
// space before and after; aria-hidden="true" subtrees are skipped; whitespace runs collapse.
function collect(node, out) {
  if (node.nodeType === 3) {
    out.push(node.data);
    return;
  }
  if (node.nodeType !== 1) return;
  if (node.getAttribute('aria-hidden') === 'true') return;
  const inline = INLINE_TAGS.has(node.localName);
  if (!inline) out.push(' ');
  for (const c of node.childNodes) collect(c, out);
  if (!inline) out.push(' ');
}

function textOf(node) {
  const out = [];
  collect(node, out);
  return out.join('').replace(/\s+/g, ' ').trim();
}

function fieldKind(e) {
  if (e.localName === 'textarea') return 'textarea';
  if (e.localName === 'select') return 'select';
  if (e.localName !== 'input') return null;
  const t = e.type;
  if (['submit', 'button', 'reset', 'image'].includes(t)) return null;
  return t === 'checkbox' ? 'checkboxes' : t;
}

function submitButton(form) {
  return descendants(form).find((e) => e.localName === 'button' && e.type === 'submit') || null;
}

function formLabel(form) {
  const b = submitButton(form);
  return b === null ? null : textOf(b);
}

function describeForm(form) {
  const fields = [];
  const types = {};
  const options = {};
  const values = {};
  for (const e of descendants(form)) {
    const kind = fieldKind(e);
    const name = e.getAttribute('name');
    if (kind === null || !name) continue;
    if (!hasOwn(types, name)) {
      fields.push(name);
      types[name] = kind;
    }
    if (kind === 'checkboxes') {
      if (!hasOwn(options, name)) options[name] = [];
      if (!hasOwn(values, name)) values[name] = [];
      options[name].push(e.value);
      if (e.checked) values[name].push(e.value);
    } else if (kind === 'select') {
      options[name] = e.optionElements().map((o) => o.value);
      values[name] = e.value;
    } else if (!hasOwn(values, name)) {
      values[name] = e.value;
    }
  }
  return {submit: formLabel(form), fields, types, options, values};
}

// ------------------------------------------------------------------------------------ fake host

function makeHost(scenario) {
  const doc = new FakeDocument();
  const roots = {};
  for (const [id, tag] of [['cb-header', 'header'], ['cb-main', 'main'], ['cb-toasts', 'div']]) {
    const e = doc.createElement(tag);
    e.setAttribute('id', id);
    doc.body.append(e);
    roots[id] = e;
  }
  const api = isObject(scenario.api) ? scenario.api : {};
  const served = new Map(); // api key -> answers consumed
  const storage = new Map();
  const timers = new Map();
  const fake = {doc, roots, core: null, recording: false, now: START_MS, hash: '', title: ''};
  let timerSeq = 0;

  function answer(method, url, payload) {
    let body = null;
    if (payload !== undefined && payload !== null) {
      try {
        body = JSON.parse(payload);
      } catch (err) {
        body = String(payload);
      }
    }
    rec.calls.push([method, url, body]);
    let key = method + ' ' + url;
    if (!hasOwn(api, key)) {
      const q = url.indexOf('?');
      key = q >= 0 && hasOwn(api, method + ' ' + url.slice(0, q))
        ? method + ' ' + url.slice(0, q) : null;
    }
    if (key === null) {
      rec.unmatched.push([method, url]);
      return Promise.resolve({status: 404, text: JSON.stringify({error: 'not found'})});
    }
    let value = api[key];
    if (Array.isArray(value)) {
      const i = served.get(key) || 0;
      served.set(key, i + 1);
      value = value.length ? value[Math.min(i, value.length - 1)] : null;
    }
    let status = 200;
    if (isObject(value) && hasOwn(value, '$status')) {
      status = Number(value.$status);
      value = Object.assign({}, value);
      delete value.$status;
    }
    return Promise.resolve({status, text: JSON.stringify(value === undefined ? null : value)});
  }

  function addTimer(fn, ms, repeat) {
    timerSeq += 1;
    const every = Math.max(1, Number(ms) || 0);
    timers.set(timerSeq, {fn, every, due: fake.now + every, repeat, seq: timerSeq});
    return timerSeq;
  }

  fake.tick = async function tick(ms) {
    fake.now += Math.max(0, Number(ms) || 0);
    const due = Array.from(timers.entries())
      .filter(([, t]) => t.due <= fake.now)
      .sort((a, b) => a[1].due - b[1].due || a[1].seq - b[1].seq);
    for (const [id, t] of due) {
      if (!timers.has(id)) continue; // cleared by an earlier timer of this tick
      if (t.repeat) t.due = fake.now + t.every;
      else timers.delete(id);
      try {
        t.fn();
      } catch (err) {
        rec.errors.push(errorText(err));
      }
      await drain();
    }
  };

  fake.host = {
    createElement: (tag) => doc.createElement(tag),
    createText: (data) => doc.createTextNode(data),
    root: (id) => roots[id] || null,
    activeElement: () => {
      const a = doc.activeElement;
      return a !== null && a.isConnected ? a : null;
    },
    getItem: (key) => (storage.has(String(key)) ? storage.get(String(key)) : null),
    setItem: (key, value) => {
      storage.set(String(key), String(value));
    },
    removeItem: (key) => {
      storage.delete(String(key));
    },
    fetch: (method, url, headers, payload) => answer(String(method), String(url), payload),
    setInterval: (fn, ms) => addTimer(fn, ms, true),
    clearInterval: (id) => {
      timers.delete(id);
    },
    setTimeout: (fn, ms) => addTimer(fn, ms, false),
    clearTimeout: (id) => {
      timers.delete(id);
    },
    getHash: () => fake.hash,
    setHash: (hash) => {
      fake.hash = String(hash);
    },
    replaceHash: (hash) => {
      fake.hash = String(hash);
    },
    onHashChange: () => {}, // no back/forward in the runner
    now: () => fake.now,
    hidden: () => false,
    setTitle: (title) => {
      fake.title = String(title);
    },
    event: (name, ...args) => {
      if (name === 'go') {
        if (fake.recording) rec.nav.push([String(args[0]), plain(args[1])]);
      } else if (name === 'toast') {
        rec.toasts.push(String(args[0]));
      } else if (name === 'badge') {
        rec.badges[String(args[0])] = args[1];
      } else if (name === 'login') {
        rec.session.push(['login', args[0], plain(args[1])]);
      } else if (name === 'logout') {
        rec.session.push(['logout']);
      } else if (name === 'error') {
        rec.errors.push(errorText(args[1], args[0]));
      }
    },
    attach: (core) => {
      fake.core = core;
    },
  };
  return fake;
}

// A JSON copy made in this realm (values from the page context are copied at record time).
function plain(value) {
  return value === undefined ? null : JSON.parse(JSON.stringify(value));
}

// Lets every pending promise settle. Nothing in the page context uses real timers, so all
// pending work is microtasks; a few macrotask turns also flush unhandled-rejection reports.
async function drain() {
  for (let i = 0; i < 5; i++) await new Promise((resolve) => setImmediate(resolve));
}

// ------------------------------------------------------------------------------------ steps

function findClickable(fake, wanted, nth, byId) {
  const what = byId ? 'data-testid "' + wanted + '"' : 'text "' + wanted + '"';
  // The page first; the top bar only when nothing in the page matches.
  for (const top of [fake.roots['cb-main'], fake.roots['cb-header']]) {
    const list = descendants(top).filter((e) => e.isClickable());
    let matches;
    if (byId) {
      matches = list.filter((e) => e.getAttribute('data-testid') === wanted);
    } else {
      const texts = list.map((e) => textOf(e));
      matches = list.filter((e, i) => texts[i] === wanted);
      if (!matches.length) matches = list.filter((e, i) => texts[i].includes(wanted));
    }
    if (!matches.length) continue;
    if (nth >= matches.length) {
      scenarioError('only ' + matches.length + ' clickable element(s) with ' + what +
        ', no nth=' + nth);
      return null;
    }
    return matches[nth];
  }
  scenarioError('no clickable element with ' + what);
  return null;
}

function clickElement(e, what) {
  if (e.localName === 'button' && e.disabled) {
    scenarioError('button ' + what + ' is disabled');
    return;
  }
  dispatchClick(e);
}

function findForm(fake, label, nth) {
  const forms = descendants(fake.roots['cb-main'])
    .filter((e) => e.localName === 'form' && formLabel(e) === label);
  if (!forms.length) {
    scenarioError('no form with the submit button "' + label + '"');
    return null;
  }
  if (nth >= forms.length) {
    scenarioError('only ' + forms.length + ' form(s) with the submit button "' + label +
      '", no nth=' + nth);
    return null;
  }
  return forms[nth];
}

function fillForm(form, label, values) {
  if (values === undefined || values === null) return true;
  if (!isObject(values)) {
    scenarioError('"values" of form "' + label + '" must be an object');
    return false;
  }
  const controls = descendants(form).filter((e) => fieldKind(e) !== null);
  for (const name of Object.keys(values)) {
    const els = controls.filter((e) => e.getAttribute('name') === name);
    if (!els.length) {
      scenarioError('form "' + label + '" has no field "' + name + '"');
      return false;
    }
    const kind = fieldKind(els[0]);
    const value = values[name];
    if (kind === 'checkboxes') {
      const wanted = (Array.isArray(value) ? value : [value]).map(String);
      const offered = els.map((e) => e.value);
      const bad = wanted.find((v) => !offered.includes(v));
      if (bad !== undefined) {
        scenarioError('field "' + name + '" of form "' + label + '" has no option "' + bad + '"');
        return false;
      }
      for (const e of els) e.checked = wanted.includes(e.value);
    } else if (kind === 'select') {
      const v = String(value);
      if (!els[0].optionElements().some((o) => o.value === v)) {
        scenarioError('field "' + name + '" of form "' + label + '" has no option "' + v + '"');
        return false;
      }
      els[0].value = v;
    } else {
      els[0].value = value === null || value === undefined ? '' : String(value);
    }
  }
  return true;
}

function checkStep(step) {
  if (!isObject(step)) {
    scenarioError('a step must be an object, got ' + JSON.stringify(step));
    return null;
  }
  const kinds = STEP_KINDS.filter((k) => hasOwn(step, k));
  if (kinds.length !== 1) {
    scenarioError('a step needs exactly one of ' + STEP_KINDS.join(', ') + ': ' +
      JSON.stringify(step));
    return null;
  }
  const kind = kinds[0];
  for (const key of Object.keys(step)) {
    if (key !== kind && !STEP_EXTRA[kind].includes(key)) {
      scenarioError('unknown key "' + key + '" in a ' + kind + ' step');
      return null;
    }
  }
  return kind;
}

async function runStep(fake, context, step) {
  const kind = checkStep(step);
  if (kind === null) return;
  const nth = hasOwn(step, 'nth') ? Number(step.nth) : 0;
  if (!Number.isInteger(nth) || nth < 0) {
    scenarioError('"nth" must be a non-negative integer');
    return;
  }
  if (kind === 'click' || kind === 'click_id') {
    const wanted = String(step[kind]);
    const e = findClickable(fake, wanted, nth, kind === 'click_id');
    if (e !== null) clickElement(e, JSON.stringify(wanted));
  } else if (kind === 'fill' || kind === 'submit') {
    const label = String(step[kind]);
    const form = findForm(fake, label, nth);
    if (form === null || !fillForm(form, label, step.values)) return;
    if (kind === 'submit') clickElement(submitButton(form), JSON.stringify(label));
  } else if (kind === 'tick') {
    const ms = Number(step.tick);
    if (!(ms >= 0)) {
      scenarioError('"tick" must be a number of milliseconds');
      return;
    }
    await fake.tick(ms);
  } else if (kind === 'go') {
    try {
      context.CB.go(String(step.go), inner(context, step.params || {}));
    } catch (err) {
      rec.errors.push(errorText(err));
    }
  }
}

// ------------------------------------------------------------------------------------ main

// A value copied into the page context (so page code sees its own Object and Array).
function inner(context, value) {
  if (value === undefined) return undefined;
  return vm.runInContext('JSON', context).parse(JSON.stringify(value));
}

function featureLabel(file) {
  const base = path.basename(file);
  return base === 'ui.js' ? path.basename(path.dirname(file)) : base.replace(/\.js$/, '');
}

async function run(scenario) {
  if (!isObject(scenario)) throw new Error('the scenario must be a JSON object');
  if (!Array.isArray(scenario.files)) throw new Error('the scenario needs "files": [paths]');
  for (const key of Object.keys(scenario)) {
    if (!SCENARIO_KEYS.includes(key)) scenarioError('unknown key "' + key + '"');
  }
  const fake = makeHost(scenario);
  const context = vm.createContext({__CB_HOST__: fake.host});
  const cbPath = scenario.cb ? String(scenario.cb) : DEFAULT_CB;
  new vm.Script(fs.readFileSync(cbPath, 'utf8'), {filename: cbPath}).runInContext(context);
  const core = fake.core;
  if (core === null) throw new Error(cbPath + ' did not attach to __CB_HOST__');

  const fileOf = new Map();
  for (const file of scenario.files) {
    const label = featureLabel(String(file));
    const source = fs.readFileSync(String(file), 'utf8');
    const code = "(() => {\n'use strict';\n" + source + '\n})();\n//# sourceURL=/ui/' + label +
      '.js\n';
    try {
      new vm.Script(code, {filename: '/ui/' + label + '.js'}).runInContext(context);
    } catch (err) {
      rec.errors.push(errorText(err));
    }
    for (const p of core.pages()) if (!fileOf.has(p.name)) fileOf.set(p.name, label);
  }
  await drain();
  const pages = core.pages().map((p) => ({
    name: p.name,
    title: p.title,
    nav: p.nav,
    order: p.order,
    public: p.public,
    file: fileOf.has(p.name) ? fileOf.get(p.name) : null,
  }));
  if (scenario.load_all === true) return {pages, errors: rec.errors};

  try {
    core.startWith({
      me: isObject(scenario.me) ? inner(context, scenario.me) : null,
      token: scenario.token === undefined || scenario.token === null ? null : scenario.token,
      page: scenario.page === undefined ? null : scenario.page,
      params: inner(context, isObject(scenario.params) ? scenario.params : {}),
    });
  } catch (err) {
    rec.errors.push(errorText(err));
  }
  fake.recording = true;
  await drain();
  const steps = scenario.steps === undefined || scenario.steps === null ? [] : scenario.steps;
  if (!Array.isArray(steps)) {
    scenarioError('"steps" must be a list');
  } else {
    for (const step of steps) {
      await runStep(fake, context, step);
      await drain();
    }
  }

  const main = fake.roots['cb-main'];
  const elements = descendants(main);
  const current = core.current();
  return {
    pages,
    page: current ? current.name : null,
    title: current ? current.title : null,
    text: textOf(main),
    classes: elements
      .filter((e) => (e.getAttribute('class') || '') !== '')
      .map((e) => [e.getAttribute('class'), textOf(e)]),
    buttons: elements
      .filter((e) => e.localName === 'button')
      .map((e) => ({label: textOf(e), disabled: Boolean(e.disabled),
        testid: e.getAttribute('data-testid')})),
    forms: elements.filter((e) => e.localName === 'form').map(describeForm),
    calls: rec.calls,
    unmatched: rec.unmatched,
    nav: rec.nav,
    toasts: rec.toasts,
    badges: rec.badges,
    session: rec.session,
    errors: rec.errors,
  };
}

function readStdin() {
  return new Promise((resolve, reject) => {
    const chunks = [];
    process.stdin.on('data', (chunk) => chunks.push(chunk));
    process.stdin.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    process.stdin.on('error', reject);
  });
}

process.on('unhandledRejection', (reason) => {
  // ApiErrors were already shown as toasts by CB.api (as in the browser, where the frame
  // marks them handled); anything else is an uncaught error of the page.
  if (reason !== null && typeof reason === 'object' && reason.name === 'ApiError') return;
  rec.errors.push(errorText(reason));
});

async function main() {
  const input = await readStdin();
  const text = input.charCodeAt(0) === 0xfeff ? input.slice(1) : input; // a BOM
  const result = await run(JSON.parse(text));
  process.stdout.write(JSON.stringify(result) + '\n');
}

main().then(
  () => {
    process.exitCode = 0;
  },
  (err) => {
    process.stderr.write((err && err.stack ? err.stack : String(err)) + '\n');
    process.exitCode = 1;
  },
);
