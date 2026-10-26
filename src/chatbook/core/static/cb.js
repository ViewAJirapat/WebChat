// ChatBook UI runtime: the CB toolkit and the hash router (DESIGN.md 3.13).
//
// One platform-independent core talks to a host object: DOM factory, storage, HTTP, timers,
// hash location, clock and an event hook. In the browser the host wraps document, fetch,
// localStorage, timers and location.hash. tools/uirun.js defines the global __CB_HOST__ with a
// fake host, so the tests run this same code. The worker-facing API is documented in
// docs/ui.md; CB.start (called by start.js) is the only other public name.
(function (root) {
  'use strict';

  const TOKEN_KEY = 'cb.token';
  const BANNED_TAGS = ['script', 'style', 'iframe', 'object', 'embed', 'link', 'meta'];
  const EL_PROPS = ['class', 'testid', 'title', 'type', 'value', 'placeholder', 'disabled',
    'checked', 'name', 'onclick'];
  const PAGE_KEYS = ['title', 'nav', 'order', 'public', 'load', 'render', 'poll'];
  const FORM_KEYS = ['fields', 'submit', 'reset', 'onsubmit'];
  const FIELD_KEYS = ['name', 'label', 'type', 'value', 'options'];
  const FIELD_TYPES = ['text', 'password', 'textarea', 'select', 'checkboxes'];
  const TEXT_TYPES = ['text', 'password', 'textarea'];
  const INLINE_TYPES = ['text', 'password', 'select'];
  const SKIP_INPUTS = ['submit', 'button', 'reset', 'image', 'file', 'hidden'];
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov',
    'Dec'];
  const NOT_FOUND = 'Page not found';
  const TOAST_MS = 4000;
  const MAX_TOASTS = 3;
  const MAX_ROUNDS = 20;

  class ApiError extends Error {
    constructor(status, message) {
      super(message);
      this.status = status;
    }
  }
  ApiError.prototype.name = 'ApiError';

  const host = typeof __CB_HOST__ !== 'undefined' ? __CB_HOST__ : browserHost();

  const pages = new Map(); // name -> page record
  const jobs = []; // CB.every jobs
  const badges = new Map(); // page name -> number
  const initial = new WeakMap(); // field element -> its value right after mounting
  const formInfo = new WeakMap(); // CB.form element -> {submit, button, controls, reset}
  const flights = new WeakMap(); // CB.form element -> in-flight submit {forms}
  const state = {
    started: false,
    token: null,
    me: null,
    view: null, // the page instance being shown
    lastHash: null,
    navLinks: new Map(), // page name -> {link, badge}
  };

  // ---------------------------------------------------------------- small helpers

  function lower(s) {
    return String(s === null || s === undefined ? '' : s).toLowerCase();
  }

  function tagOf(node) {
    return lower(node.tagName);
  }

  function present(v) {
    return v !== null && v !== undefined && v !== false;
  }

  function isPlainObject(x) {
    if (x === null || typeof x !== 'object') return false;
    const proto = Object.getPrototypeOf(x);
    return proto === Object.prototype || proto === null;
  }

  function isNode(x) {
    return x !== null && typeof x === 'object' && typeof x.nodeType === 'number';
  }

  function isThenable(x) {
    return x !== null && (typeof x === 'object' || typeof x === 'function') &&
      typeof x.then === 'function';
  }

  function describe(x) {
    if (typeof x === 'function') return 'a function';
    if (isThenable(x)) return 'a Promise (forgot await? render must not be async)';
    if (typeof x === 'object') return 'a plain object (show its fields as text)';
    return 'a value of type ' + typeof x;
  }

  function checkKeys(obj, allowed, prefix) {
    for (const key of Object.keys(obj)) {
      if (!allowed.includes(key)) {
        throw new Error(prefix + ' "' + key + '"; allowed: ' + allowed.join(', '));
      }
    }
  }

  function pad(n) {
    return n < 10 ? '0' + n : String(n);
  }

  function rootEl(id) {
    return host.root(id);
  }

  function text(s) {
    return host.createText(String(s));
  }

  function hasClass(node, name) {
    const cls = node.getAttribute('class');
    return cls !== null && cls.split(/\s+/).includes(name);
  }

  // ---------------------------------------------------------------- errors

  function messageOf(err) {
    if (err !== null && typeof err === 'object' && typeof err.message === 'string') {
      return err.message;
    }
    return String(err);
  }

  function reportError(err) {
    host.event('error', messageOf(err), err);
  }

  function handleError(err) {
    if (!(err instanceof ApiError)) reportError(err);
  }

  // Runs a worker callback (sync or async). The promise never rejects: it gives true on
  // success and false on failure. ApiErrors are already toasted; other errors are reported.
  function invoke(fn, args) {
    let result;
    try {
      result = fn(...(args || []));
    } catch (err) {
      handleError(err);
      return Promise.resolve(false);
    }
    return Promise.resolve(result).then(() => true, (err) => {
      handleError(err);
      return false;
    });
  }

  // ---------------------------------------------------------------- nodes

  function toNodes(child, out, where) {
    if (child === null || child === undefined || typeof child === 'boolean') return out;
    if (Array.isArray(child)) {
      for (const c of child) toNodes(c, out, where);
      return out;
    }
    const type = typeof child;
    if (type === 'string' || type === 'number' || type === 'bigint') {
      out.push(text(child));
      return out;
    }
    if (isNode(child)) {
      out.push(child);
      return out;
    }
    if (isThenable(child)) Promise.resolve(child).catch(() => {});
    throw new Error(where + ': cannot show ' + describe(child) +
      '; use text, numbers, nodes from CB.el or CB.form, or arrays of them');
  }

  function el(tag, props, ...children) {
    const name = lower(tag);
    if (typeof tag !== 'string' || !/^[a-z][a-z0-9]*$/.test(name)) {
      throw new Error('CB.el: bad tag ' + JSON.stringify(String(tag)) +
        '; use an HTML tag name such as "div"');
    }
    // A hand-built form would reload the page on submit (and put the fields in the URL).
    if (name === 'form') throw new Error('CB.el: tag "form" is not allowed; use CB.form');
    if (BANNED_TAGS.includes(name)) throw new Error('CB.el: tag "' + name + '" is not allowed');
    let p = props;
    if (p !== null && p !== undefined && !isPlainObject(p)) {
      children.unshift(p); // CB.el('p', 'text'): the second argument is a child
      p = null;
    }
    if (p) checkKeys(p, EL_PROPS, 'CB.el: unknown prop');
    const node = host.createElement(name);
    if (name === 'button') node.setAttribute('type', 'button');
    if (p) {
      if (present(p.class) && String(p.class) !== '') node.setAttribute('class', String(p.class));
      if (present(p.testid)) node.setAttribute('data-testid', String(p.testid));
      for (const key of ['title', 'name', 'type', 'placeholder']) {
        if (present(p[key])) node.setAttribute(key, String(p[key]));
      }
    }
    const kids = toNodes(children, [], 'CB.el');
    if (kids.length) node.append(...kids);
    if (p) {
      // Live properties go after the children (a select needs its options first).
      if (p.value !== null && p.value !== undefined) node.value = String(p.value);
      if (p.checked !== null && p.checked !== undefined) node.checked = Boolean(p.checked);
      if (p.disabled !== null && p.disabled !== undefined) node.disabled = Boolean(p.disabled);
      if (present(p.onclick)) {
        if (typeof p.onclick !== 'function') throw new Error('CB.el: onclick must be a function');
        onClick(node, p.onclick);
      }
    }
    return node;
  }

  function onClick(node, fn) {
    node.addEventListener('click', () => {
      invoke(fn);
    });
    const tag = tagOf(node);
    if (tag !== 'button' && tag !== 'input' && tag !== 'select' && tag !== 'textarea') {
      // Keyboard access for clickable rows and spans.
      node.setAttribute('role', 'button');
      node.setAttribute('tabindex', '0');
      node.addEventListener('keydown', (ev) => {
        if (ev.target === node && (ev.key === 'Enter' || ev.key === ' ')) {
          ev.preventDefault();
          invoke(fn);
        }
      });
    }
  }

  // ---------------------------------------------------------------- forms

  function form(spec) {
    if (!isPlainObject(spec)) throw new Error('CB.form: pass {fields, submit, reset, onsubmit}');
    checkKeys(spec, FORM_KEYS, 'CB.form: unknown option');
    if (!Array.isArray(spec.fields)) {
      throw new Error('CB.form: fields must be a list of {name, label, type, value, options}');
    }
    if (typeof spec.submit !== 'string' || spec.submit === '') {
      throw new Error('CB.form: submit must be the button label');
    }
    if (typeof spec.onsubmit !== 'function') {
      throw new Error('CB.form: onsubmit must be a function');
    }
    const controls = [];
    for (const field of spec.fields) controls.push(buildField(field, controls));
    const node = host.createElement('form');
    node.setAttribute('novalidate', '');
    if (controls.length === 1 && INLINE_TYPES.includes(controls[0].type)) {
      // One field and the button on one line; cb.css shows the label to screen readers only,
      // so a text field also shows it as its placeholder.
      node.setAttribute('data-inline', '');
      const only = controls[0];
      if (only.type !== 'select') only.input.setAttribute('placeholder', only.label);
    }
    const button = host.createElement('button');
    button.setAttribute('type', 'submit');
    button.append(text(spec.submit));
    node.append(...controls.map((c) => c.wrap), button);
    formInfo.set(node, {submit: spec.submit, button, controls, reset: Boolean(spec.reset)});
    node.addEventListener('submit', (ev) => {
      if (ev) ev.preventDefault();
      submitForm(node, spec.onsubmit);
    });
    return node;
  }

  function optionList(field, name) {
    const list = field.options === undefined || field.options === null ? [] : field.options;
    if (!Array.isArray(list)) {
      throw new Error('CB.form: options of field "' + name + '" must be a list of {value, label}');
    }
    return list.map((o) => {
      if (!isPlainObject(o)) {
        throw new Error('CB.form: each option of field "' + name + '" must be {value, label}');
      }
      const value = String(o.value);
      return {value, label: o.label === undefined || o.label === null ? value : String(o.label)};
    });
  }

  function buildField(field, controls) {
    if (!isPlainObject(field)) {
      throw new Error('CB.form: each field must be {name, label, type, value, options}');
    }
    checkKeys(field, FIELD_KEYS, 'CB.form: unknown field option');
    const name = field.name;
    if (typeof name !== 'string' || name === '') {
      throw new Error('CB.form: every field needs a name');
    }
    if (controls.some((c) => c.name === name)) {
      throw new Error('CB.form: field name "' + name + '" is used twice');
    }
    const type = field.type === undefined || field.type === null ? 'text' : field.type;
    if (!FIELD_TYPES.includes(type)) {
      throw new Error('CB.form: field "' + name + '" has unknown type ' +
        JSON.stringify(String(type)) + '; allowed: ' + FIELD_TYPES.join(', '));
    }
    const label = field.label === undefined || field.label === null ? name : String(field.label);
    if (type === 'checkboxes') {
      const wrap = host.createElement('fieldset');
      const legend = host.createElement('legend');
      legend.append(text(label));
      wrap.append(legend);
      const chosen = Array.isArray(field.value) ? field.value.map(String) : [];
      const boxes = [];
      for (const o of optionList(field, name)) {
        const lab = host.createElement('label');
        const box = host.createElement('input');
        box.setAttribute('type', 'checkbox');
        box.setAttribute('name', name);
        box.value = o.value;
        const span = host.createElement('span');
        span.append(text(o.label));
        lab.append(box, span);
        wrap.append(lab);
        box.checked = chosen.includes(o.value);
        boxes.push(box);
      }
      return {name, type, label, wrap, boxes, input: null};
    }
    const wrap = host.createElement('label');
    const span = host.createElement('span');
    span.append(text(label));
    let input;
    if (type === 'textarea' || type === 'select') {
      input = host.createElement(type);
    } else {
      input = host.createElement('input');
      input.setAttribute('type', type);
      if (type === 'password') input.setAttribute('autocomplete', 'current-password');
    }
    input.setAttribute('name', name);
    wrap.append(span, input);
    if (type === 'select') {
      const values = [];
      for (const o of optionList(field, name)) {
        const opt = host.createElement('option');
        opt.value = o.value;
        opt.append(text(o.label));
        input.append(opt);
        values.push(o.value);
      }
      const want = field.value === undefined || field.value === null ? null : String(field.value);
      const first = values.length ? values[0] : '';
      input.value = want !== null && values.includes(want) ? want : first;
    } else {
      input.value = field.value === undefined || field.value === null ? '' : String(field.value);
    }
    return {name, type, label, wrap, boxes: null, input};
  }

  function submitForm(node, onsubmit) {
    if (flights.has(node)) return; // already submitting
    const info = formInfo.get(node);
    const values = {};
    for (const c of info.controls) {
      values[c.name] = c.type === 'checkboxes'
        ? c.boxes.filter((b) => b.checked).map((b) => String(b.value))
        : String(c.input.value);
    }
    const flight = {forms: []};
    joinFlight(node, flight);
    invoke(onsubmit, [values]).then((ok) => {
      // A re-render during the submit may have replaced the form: finish every copy.
      for (const f of flight.forms) {
        flights.delete(f);
        const fi = formInfo.get(f);
        fi.button.disabled = false;
        if (ok && fi.reset) {
          for (const c of fi.controls) if (TEXT_TYPES.includes(c.type)) c.input.value = '';
        }
      }
    });
  }

  function joinFlight(node, flight) {
    flight.forms.push(node);
    flights.set(node, flight);
    formInfo.get(node).button.disabled = true;
  }

  // ---------------------------------------------------------------- mounting a page

  // Walks a mounted tree: forms in order, named fields keyed by form index + name, and the
  // elements with class "messages".
  function scan(top) {
    const out = {forms: [], fields: [], messages: [], seen: new Map()};
    walk(top, -1, out);
    return out;
  }

  function walk(node, formIndex, out) {
    const kids = node.childNodes;
    for (let i = 0; i < kids.length; i++) {
      const c = kids[i];
      if (c.nodeType !== 1) continue;
      const tag = tagOf(c);
      let fi = formIndex;
      if (tag === 'form') {
        fi = out.forms.length;
        out.forms.push(c);
      }
      if (hasClass(c, 'messages')) out.messages.push(c);
      if (tag === 'input' || tag === 'textarea' || tag === 'select') {
        const name = c.getAttribute('name');
        const type = tag === 'input' ? lower(c.getAttribute('type') || 'text') : tag;
        if (name && !SKIP_INPUTS.includes(type)) {
          const check = type === 'checkbox' || type === 'radio';
          let key = fi + '|' + name + (check ? '|' + c.value : '');
          const n = out.seen.get(key) || 0;
          out.seen.set(key, n + 1);
          if (n) key += '#' + n;
          out.fields.push({el: c, key, check, type});
        }
        continue;
      }
      walk(c, fi, out);
    }
  }

  function capture(before) {
    const values = new Map();
    for (const f of before.fields) {
      const now = f.check ? f.el.checked : f.el.value;
      const init = initial.get(f.el);
      const changed = init === undefined ? (f.check ? now : now !== '') : now !== init;
      if (changed) values.set(f.key, now);
    }
    let focus = null;
    const active = host.activeElement();
    for (const f of before.fields) {
      if (f.el !== active) continue;
      focus = {key: f.key, start: null, end: null};
      try {
        focus.start = active.selectionStart;
        focus.end = active.selectionEnd;
      } catch (err) {
        // this input type has no text selection
      }
    }
    return {values, focus};
  }

  function optionValues(select) {
    const out = [];
    const visit = (n) => {
      const kids = n.childNodes;
      for (let i = 0; i < kids.length; i++) {
        const c = kids[i];
        if (c.nodeType !== 1) continue;
        if (tagOf(c) === 'option') out.push(c.value);
        else visit(c);
      }
    };
    visit(select);
    return out;
  }

  function restore(after, saved) {
    for (const f of after.fields) {
      if (!saved.values.has(f.key)) continue;
      const v = saved.values.get(f.key);
      if (f.check) f.el.checked = v;
      else if (f.type !== 'select' || optionValues(f.el).includes(v)) f.el.value = v;
    }
    if (saved.focus === null) return;
    const f = after.fields.find((x) => x.key === saved.focus.key);
    if (!f) return;
    try {
      f.el.focus({preventScroll: true});
      if (typeof saved.focus.start === 'number' && typeof f.el.setSelectionRange === 'function') {
        f.el.setSelectionRange(saved.focus.start, saved.focus.end);
      }
    } catch (err) {
      // focus is best effort
    }
  }

  // A form that is still submitting keeps its state in the matching form of the new tree.
  function linkForms(oldForms, newForms) {
    for (let i = 0; i < oldForms.length && i < newForms.length; i++) {
      const flight = flights.get(oldForms[i]);
      const a = formInfo.get(oldForms[i]);
      const b = formInfo.get(newForms[i]);
      if (!flight || !a || !b || a.submit !== b.submit || flights.has(newForms[i])) continue;
      joinFlight(newForms[i], flight);
    }
  }

  // Replaces the page. preserve: keep typed field text and focus (refresh and poll);
  // first: the first render of this page instance (".messages" scroll to the bottom).
  function mount(nodes, preserve, first) {
    const main = rootEl('cb-main');
    const before = scan(main);
    const saved = preserve ? capture(before) : null;
    const pos = before.messages.map((m) => ({
      top: m.scrollTop,
      bottom: m.scrollTop + m.clientHeight >= m.scrollHeight - 8,
    }));
    main.replaceChildren(...nodes);
    const after = scan(main);
    for (const f of after.fields) initial.set(f.el, f.check ? f.el.checked : f.el.value);
    if (saved) {
      linkForms(before.forms, after.forms);
      restore(after, saved);
    }
    after.messages.forEach((m, i) => {
      const old = pos[i];
      m.scrollTop = first || !old || old.bottom ? m.scrollHeight : old.top;
    });
  }

  // A fingerprint of a list of nodes: tags, attributes, text, and the state a page sets
  // (disabled, option and checkbox values), not the state the user changes (typed text,
  // ticked boxes, the selected option). Equal fingerprints: a re-mount would show the same.
  function fingerprint(list) {
    const out = [];
    const visit = (n) => {
      if (n.nodeType === 3) {
        out.push('#' + n.data);
        return;
      }
      if (n.nodeType !== 1) return;
      const tag = tagOf(n);
      out.push('<' + tag);
      for (const a of n.getAttributeNames().slice().sort()) {
        out.push('@' + a + '=' + n.getAttribute(a));
      }
      if (n.disabled === true) out.push('!disabled');
      const type = lower(n.getAttribute('type'));
      if (tag === 'option' || (tag === 'input' && (type === 'checkbox' || type === 'radio'))) {
        out.push('=' + n.value);
      }
      const kids = n.childNodes;
      for (let i = 0; i < kids.length; i++) visit(kids[i]);
      out.push('>');
    };
    for (const n of list) visit(n);
    return JSON.stringify(out);
  }

  function mountedNodes() {
    const kids = rootEl('cb-main').childNodes;
    const out = [];
    for (let i = 0; i < kids.length; i++) out.push(kids[i]);
    return out;
  }

  // What a render showed: its data and the user it was rendered for (null if not JSON).
  function dataKey(data) {
    try {
      return JSON.stringify([data === undefined ? null : data, state.me]);
    } catch (err) {
      return null;
    }
  }

  function loadingNode() {
    return el('p', {class: 'muted'}, 'Loading...');
  }

  function errorNode() {
    return el('div', {class: 'card'},
      el('p', {}, 'Could not load this page.'),
      el('button', {onclick: refresh}, 'Retry'));
  }

  function notFoundNode() {
    return el('div', {class: 'card'}, el('h2', {}, NOT_FOUND));
  }

  // ---------------------------------------------------------------- pages and the render cycle

  function page(name, spec) {
    if (typeof name !== 'string' || !/^[a-z][a-z0-9_]*$/.test(name)) {
      throw new Error('CB.page: bad page name ' + JSON.stringify(String(name)) +
        '; use lower-case letters, digits and _');
    }
    if (pages.has(name)) throw new Error('page "' + name + '" registered twice');
    const where = 'CB.page("' + name + '")';
    if (!isPlainObject(spec)) throw new Error(where + ': pass {title, render, ...}');
    checkKeys(spec, PAGE_KEYS, where + ': unknown option');
    if (typeof spec.title !== 'string' || spec.title === '') {
      throw new Error(where + ': title must be a string');
    }
    if (typeof spec.render !== 'function') throw new Error(where + ': render must be a function');
    const load = spec.load === undefined || spec.load === null ? null : spec.load;
    if (load !== null && typeof load !== 'function') {
      throw new Error(where + ': load must be a function');
    }
    let nav = null;
    if (spec.nav !== undefined && spec.nav !== null) {
      if (typeof spec.nav !== 'string' || spec.nav === '') {
        throw new Error(where + ': nav must be the top-bar label');
      }
      nav = spec.nav;
    }
    let order = 100;
    if (spec.order !== undefined && spec.order !== null) {
      order = Number(spec.order);
      if (!Number.isFinite(order)) throw new Error(where + ': order must be a number');
    }
    let poll = 0;
    if (spec.poll !== undefined && spec.poll !== null && spec.poll !== 0) {
      poll = Number(spec.poll);
      if (!(poll > 0)) throw new Error(where + ': poll must be a number of milliseconds');
    }
    pages.set(name, {
      name,
      title: spec.title,
      nav,
      order,
      public: Boolean(spec.public),
      load,
      render: spec.render,
      poll,
    });
    if (state.started) renderHeader();
  }

  function show(name, params, record) {
    if (state.view) stopView(state.view);
    const view = {
      name,
      params,
      page: record,
      alive: true,
      busy: false,
      again: false,
      first: true,
      timer: null,
      shown: null, // dataKey() of the render that is mounted
    };
    state.view = view;
    updateTitle();
    markNav();
    if (!record) {
      mount([notFoundNode()], false, true);
      return;
    }
    cycle(view);
    if (record.poll) view.timer = host.setInterval(() => poll(view), record.poll);
  }

  function stopView(view) {
    view.alive = false;
    if (view.timer !== null) host.clearInterval(view.timer);
    view.timer = null;
  }

  function poll(view) {
    if (!view.alive || view.busy || host.hidden()) return;
    cycle(view);
  }

  // Runs load + render. One at a time per page instance; a request during a run runs once
  // afterwards.
  async function cycle(view) {
    if (!view.alive) return;
    if (view.busy) {
      view.again = true;
      return;
    }
    view.busy = true;
    try {
      let rounds = 0;
      do {
        view.again = false;
        rounds += 1;
        if (rounds > MAX_ROUNDS) {
          reportError(new Error('page "' + view.name +
            '" keeps refreshing itself: do not call CB.refresh() from load or render'));
          break;
        }
        await renderOnce(view);
      } while (view.again && view.alive);
    } catch (err) {
      reportError(err);
    } finally {
      view.busy = false;
    }
  }

  async function renderOnce(view) {
    const record = view.page;
    let data = {};
    if (record.load) {
      if (view.first) mount([loadingNode()], false, true);
      try {
        data = await record.load(view.params);
      } catch (err) {
        if (!view.alive) return;
        handleError(err);
        // A failed first load shows the error card. A failed poll or refresh keeps the page
        // that is shown, with its typed text: the toast (or the error record) tells.
        if (view.first) mount([errorNode()], false, true);
        return;
      }
      if (!view.alive) return;
    }
    let nodes;
    try {
      const child = record.render(data, view.params);
      if (isThenable(child)) {
        Promise.resolve(child).catch(() => {});
        throw new Error('render of page "' + view.name +
          '" returned a Promise; render must not be async (fetch data in load)');
      }
      nodes = toNodes(child, [], 'render of page "' + view.name + '"');
    } catch (err) {
      handleError(err);
      view.shown = null;
      mount([errorNode()], false, true);
      return;
    }
    const key = dataKey(data);
    // Same data, same user and the same tree as the one mounted: leave the page alone, so
    // a poll does not drop a click in progress, the text selection or the focus.
    if (!view.first && key !== null && key === view.shown &&
        fingerprint(nodes) === fingerprint(mountedNodes())) {
      return;
    }
    mount(nodes, !view.first, view.first);
    view.shown = key;
    view.first = false;
  }

  function refresh() {
    const view = state.view;
    if (view && view.page && view.alive) cycle(view);
  }

  // ---------------------------------------------------------------- router

  function decode(s) {
    try {
      return decodeURIComponent(s);
    } catch (err) {
      return s;
    }
  }

  function parseHash(hash) {
    let h = String(hash || '');
    if (h.charAt(0) === '#') h = h.slice(1);
    if (h.charAt(0) === '/') h = h.slice(1);
    const q = h.indexOf('?');
    const name = decode(q < 0 ? h : h.slice(0, q));
    const params = {};
    if (q >= 0) {
      for (const part of h.slice(q + 1).split('&')) {
        if (part === '') continue;
        const eq = part.indexOf('=');
        const key = decode(eq < 0 ? part : part.slice(0, eq));
        if (key !== '' && key !== '__proto__') {
          params[key] = decode(eq < 0 ? '' : part.slice(eq + 1));
        }
      }
    }
    return {name, params};
  }

  function buildHash(name, params) {
    const parts = Object.keys(params).map((k) =>
      encodeURIComponent(k) + '=' + encodeURIComponent(params[k]));
    return '#/' + encodeURIComponent(name) + (parts.length ? '?' + parts.join('&') : '');
  }

  function normParams(params, where) {
    const out = {};
    if (params === null || params === undefined) return out;
    if (typeof params !== 'object' || Array.isArray(params)) {
      throw new Error(where + ': params must be an object such as {id: 5}');
    }
    for (const key of Object.keys(params)) {
      const v = params[key];
      if (v !== null && v !== undefined && key !== '__proto__') out[key] = String(v);
    }
    return out;
  }

  function home() {
    return state.me ? 'inbox' : 'login';
  }

  function go(name, params) {
    if (typeof name !== 'string' || name === '') {
      throw new Error('CB.go: the first argument must be a page name');
    }
    const p = normParams(params, 'CB.go');
    host.event('go', name, Object.assign({}, p));
    navigate(name, p, false);
  }

  function navigate(name, params, replace) {
    const hash = buildHash(name, params);
    if (replace) host.replaceHash(hash);
    else host.setHash(hash);
    state.lastHash = host.getHash();
    route(name, params);
  }

  function routeHash() {
    state.lastHash = host.getHash();
    const r = parseHash(state.lastHash);
    route(r.name, r.params);
  }

  function route(name, params) {
    if (name === '') {
      navigate(home(), {}, true);
      return;
    }
    const record = pages.get(name) || null;
    if (!state.me && name !== 'login' && !(record && record.public)) {
      navigate('login', {}, true);
      return;
    }
    if (state.me && name === 'login') {
      navigate('inbox', {}, true);
      return;
    }
    show(name, params, record);
  }

  // ---------------------------------------------------------------- header, title, badges

  function navPages() {
    return Array.from(pages.values())
      .filter((p) => p.nav !== null)
      .sort((a, b) => a.order - b.order || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
  }

  // A real link (middle click and ctrl+click open a new tab); a plain click routes in place.
  // stopBubble: a name link inside a clickable row opens only the profile.
  function link(label, href, onActivate, stopBubble) {
    const a = host.createElement('a');
    a.setAttribute('href', href);
    a.append(text(label));
    a.addEventListener('click', (ev) => {
      if (ev && stopBubble) ev.stopPropagation();
      if (ev && (ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey)) return; // new tab
      if (ev) ev.preventDefault();
      invoke(onActivate);
    });
    return a;
  }

  function showBadge(node, n) {
    node.textContent = n > 0 ? (n > 99 ? '99+' : String(n)) : '';
    if (n > 0) node.removeAttribute('hidden');
    else node.setAttribute('hidden', '');
  }

  function renderHeader() {
    const header = rootEl('cb-header');
    state.navLinks = new Map();
    if (!state.me) {
      header.replaceChildren();
      header.setAttribute('hidden', '');
      return;
    }
    header.removeAttribute('hidden');
    const logo = link('chatbook', '#/inbox', () => go('inbox'), false);
    logo.setAttribute('class', 'logo');
    logo.setAttribute('data-testid', 'nav-logo');
    const search = host.createElement('form');
    search.setAttribute('role', 'search');
    const input = host.createElement('input');
    input.setAttribute('type', 'search');
    input.setAttribute('placeholder', 'Search people');
    input.setAttribute('aria-label', 'Search people');
    input.setAttribute('data-testid', 'nav-search');
    search.append(input);
    search.addEventListener('submit', (ev) => {
      if (ev) ev.preventDefault();
      const q = String(input.value).trim();
      if (q !== '') go('people', {q});
    });
    const nav = host.createElement('nav');
    for (const p of navPages()) {
      const navLink = link(p.nav, '#/' + encodeURIComponent(p.name), () => go(p.name), false);
      navLink.setAttribute('class', 'nav-link');
      navLink.setAttribute('data-testid', 'nav-' + p.name);
      const badgeEl = host.createElement('span');
      badgeEl.setAttribute('class', 'badge');
      showBadge(badgeEl, badges.get(p.name) || 0);
      navLink.append(badgeEl);
      nav.append(navLink);
      state.navLinks.set(p.name, {link: navLink, badge: badgeEl});
    }
    const meName = String(state.me.display_name || state.me.username || 'Me');
    const meLink = link(meName, '#/profile', () => go('profile'), false);
    meLink.setAttribute('class', 'nav-me');
    meLink.setAttribute('data-testid', 'nav-me');
    const out = host.createElement('button');
    out.setAttribute('type', 'button');
    out.setAttribute('class', 'nav-logout');
    out.setAttribute('data-testid', 'nav-logout');
    out.append(text('Log out'));
    out.addEventListener('click', () => logout());
    header.replaceChildren(logo, search, nav, meLink, out);
    markNav();
  }

  function markNav() {
    const current = state.view ? state.view.name : null;
    for (const [name, item] of state.navLinks) {
      if (name === current) item.link.setAttribute('aria-current', 'page');
      else item.link.removeAttribute('aria-current');
    }
  }

  function updateTitle() {
    let sum = 0;
    for (const n of badges.values()) if (n > 0) sum += n;
    const view = state.view;
    const title = view ? (view.page ? view.page.title : NOT_FOUND) : 'ChatBook';
    host.setTitle((sum > 0 ? '(' + sum + ') ' : '') + title);
  }

  function badge(name, n) {
    if (typeof name !== 'string' || name === '') {
      throw new Error('CB.badge: the first argument must be a page name');
    }
    const value = Number(n) || 0;
    badges.set(name, value);
    host.event('badge', name, value);
    const item = state.navLinks.get(name);
    if (item) showBadge(item.badge, value);
    updateTitle();
  }

  function toast(message) {
    const msg = String(message);
    host.event('toast', msg);
    const box = rootEl('cb-toasts');
    const node = host.createElement('div');
    node.setAttribute('class', 'toast');
    node.append(text(msg));
    box.append(node);
    while (box.childNodes.length > MAX_TOASTS) box.childNodes[0].remove();
    host.setTimeout(() => node.remove(), TOAST_MS);
  }

  // ---------------------------------------------------------------- server

  async function request(method, path, body, token) {
    const headers = {Accept: 'application/json'};
    let payload;
    if (body !== undefined) {
      headers['Content-Type'] = 'application/json';
      payload = JSON.stringify(body);
    }
    if (token) headers.Authorization = 'Bearer ' + token;
    let res;
    try {
      res = await host.fetch(method, path, headers, payload);
    } catch (err) {
      return {status: 0, data: null};
    }
    let data = null;
    if (res && typeof res.text === 'string' && res.text !== '') {
      try {
        data = JSON.parse(res.text);
      } catch (err) {
        data = null;
      }
    }
    return {status: res ? Number(res.status) : 0, data};
  }

  function failMessage(res) {
    const d = res.data;
    if (d !== null && typeof d === 'object' && typeof d.error === 'string' && d.error !== '') {
      return d.error;
    }
    return res.status ? 'Request failed (' + res.status + ')' : 'Network error';
  }

  async function api(method, path, body) {
    const verb = String(method).toUpperCase();
    if (typeof path !== 'string' || path.indexOf('/api/') !== 0) {
      throw new Error('CB.api: the path must start with /api/, got ' + JSON.stringify(path));
    }
    if ((verb === 'GET' || verb === 'HEAD') && body !== undefined) {
      throw new Error('CB.api: a GET request has no body; put parameters in the path with CB.qs');
    }
    const res = await request(verb, path, body, state.token);
    if (res.status >= 200 && res.status < 300) return res.data;
    const message = failMessage(res);
    toast(message);
    if (res.status === 401 && state.me) logout();
    throw new ApiError(res.status, message);
  }

  // ---------------------------------------------------------------- session and jobs

  function runJob(job) {
    if (job.busy) return;
    job.busy = true;
    invoke(job.fn).then(() => {
      job.busy = false;
    });
  }

  function startJob(job) {
    stopJob(job);
    runJob(job);
    job.timer = host.setInterval(() => runJob(job), job.ms);
  }

  function stopJob(job) {
    if (job.timer !== null) host.clearInterval(job.timer);
    job.timer = null;
  }

  function every(ms, fn) {
    if (typeof fn !== 'function') throw new Error('CB.every: pass (ms, fn) with fn a function');
    const n = Number(ms);
    if (!(n > 0)) throw new Error('CB.every: ms must be a positive number of milliseconds');
    const job = {ms: n, fn, timer: null, busy: false};
    jobs.push(job);
    if (state.started && state.me) startJob(job);
  }

  function login(token, user) {
    if (typeof token !== 'string' || token === '') {
      throw new Error('CB.login: the token must be a non-empty string (CB.login(token, user))');
    }
    if (user === null || typeof user !== 'object' || user.id === undefined) {
      throw new Error('CB.login: user must be the user object {id, username, display_name}');
    }
    state.token = token;
    state.me = user;
    host.setItem(TOKEN_KEY, token);
    host.event('login', token, user);
    renderHeader();
    for (const job of jobs) startJob(job);
    go('inbox');
  }

  function logout() {
    if (state.token !== null || state.me !== null) {
      const token = state.token;
      host.event('logout');
      if (token) request('DELETE', '/api/session', undefined, token); // best effort
      state.token = null;
      state.me = null;
      host.removeItem(TOKEN_KEY);
      for (const job of jobs) stopJob(job);
      badges.clear();
      renderHeader();
    }
    go('login');
  }

  async function reloadMe() {
    const r = await api('GET', '/api/session');
    if (r !== null && typeof r === 'object' && r.user && state.me) {
      state.me = r.user;
      renderHeader();
    }
    return state.me;
  }

  function prepareRoots() {
    const box = rootEl('cb-toasts');
    box.setAttribute('role', 'status');
    box.setAttribute('aria-live', 'polite');
  }

  // Browser start (start.js): restore the session, start the jobs, route the current hash.
  async function start() {
    if (state.started) return;
    state.started = true;
    prepareRoots();
    host.onHashChange(() => {
      if (host.getHash() !== state.lastHash) routeHash();
    });
    const token = host.getItem(TOKEN_KEY);
    if (token) {
      mount([loadingNode()], false, true);
      const res = await request('GET', '/api/session', undefined, token);
      const d = res.data;
      if (res.status === 200 && d !== null && typeof d === 'object' && d.user) {
        state.token = token;
        state.me = d.user;
      } else if (res.status === 401) {
        host.removeItem(TOKEN_KEY);
      } else {
        toast(failMessage(res));
      }
    }
    renderHeader();
    if (state.me) for (const job of jobs) startJob(job);
    routeHash();
  }

  // Runner start (tools/uirun.js): the session is given, no /api/session call.
  function startWith(opts) {
    state.started = true;
    prepareRoots();
    if (opts.me) {
      state.token = opts.token ? String(opts.token) : 't0';
      state.me = opts.me;
      host.setItem(TOKEN_KEY, state.token);
    }
    renderHeader();
    if (state.me) for (const job of jobs) startJob(job);
    if (opts.page !== null && opts.page !== undefined) {
      navigate(String(opts.page), normParams(opts.params, 'page params'), true);
    }
  }

  // ---------------------------------------------------------------- helpers for pages

  function initials(user) {
    const name = String(user.display_name || user.username || '?').trim();
    const words = name.split(/\s+/).filter((w) => w !== '');
    if (!words.length) return '?';
    let s = Array.from(words[0])[0];
    if (words.length > 1) s += Array.from(words[words.length - 1])[0];
    return s.toUpperCase();
  }

  function avatar(user) {
    const u = user !== null && typeof user === 'object' ? user : {};
    const node = host.createElement('span');
    node.setAttribute('class', 'avatar');
    node.setAttribute('aria-hidden', 'true');
    node.setAttribute('data-color', String(Math.abs(Math.trunc(Number(u.id) || 0)) % 8));
    node.append(text(initials(u)));
    return node;
  }

  function userLink(user) {
    if (user === null || typeof user !== 'object') {
      throw new Error('CB.userLink: pass a user {id, username, display_name}');
    }
    const label = user.display_name !== undefined && user.display_name !== null
      ? user.display_name : (user.username !== undefined ? user.username : '');
    const href = '#/profile?id=' + encodeURIComponent(String(user.id));
    const node = link(String(label), href, () => go('profile', {id: user.id}), true);
    node.setAttribute('class', 'user-link');
    return node;
  }

  function time(ms) {
    const d = new Date(Number(ms));
    if (Number.isNaN(d.getTime())) return '';
    const now = new Date(host.now());
    if (d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() &&
        d.getDate() === now.getDate()) {
      return pad(d.getHours()) + ':' + pad(d.getMinutes());
    }
    return d.getDate() + ' ' + MONTHS[d.getMonth()];
  }

  function plural(n, word) {
    return n + ' ' + word + (n === 1 ? '' : 's');
  }

  function short(value, n) {
    let s = value;
    if (typeof s !== 'string') s = s === null || s === undefined ? '' : String(s);
    return s.length <= n ? s : s.slice(0, n) + '...';
  }

  function qs(obj) {
    if (obj === null || obj === undefined) return '';
    const parts = [];
    for (const key of Object.keys(obj)) {
      const v = obj[key];
      if (v === null || v === undefined || v === '') continue;
      parts.push(encodeURIComponent(key) + '=' + encodeURIComponent(String(v)));
    }
    return parts.length ? '?' + parts.join('&') : '';
  }

  // ---------------------------------------------------------------- browser host

  function browserHost() {
    const win = root;
    const doc = win.document;
    win.addEventListener('unhandledrejection', (ev) => {
      if (ev.reason instanceof ApiError) ev.preventDefault(); // already shown as a toast
    });
    return {
      createElement: (tag) => doc.createElement(tag),
      createText: (s) => doc.createTextNode(s),
      root: (id) => doc.getElementById(id),
      activeElement: () => doc.activeElement,
      getItem: (key) => {
        try {
          return win.localStorage.getItem(key);
        } catch (err) {
          return null;
        }
      },
      setItem: (key, value) => {
        try {
          win.localStorage.setItem(key, value);
        } catch (err) {
          // storage disabled: the session lasts until the tab closes
        }
      },
      removeItem: (key) => {
        try {
          win.localStorage.removeItem(key);
        } catch (err) {
          // storage disabled
        }
      },
      fetch: async (method, path, headers, body) => {
        const res = await win.fetch(path, {
          method,
          headers,
          body,
          credentials: 'same-origin',
          cache: 'no-store',
        });
        return {status: res.status, text: await res.text()};
      },
      setInterval: (fn, ms) => win.setInterval(fn, ms),
      clearInterval: (id) => win.clearInterval(id),
      setTimeout: (fn, ms) => win.setTimeout(fn, ms),
      clearTimeout: (id) => win.clearTimeout(id),
      getHash: () => win.location.hash,
      setHash: (hash) => {
        win.location.hash = hash;
      },
      replaceHash: (hash) => {
        win.history.replaceState(null, '', hash);
      },
      onHashChange: (fn) => {
        win.addEventListener('hashchange', fn);
      },
      now: () => Date.now(),
      hidden: () => doc.hidden === true,
      setTitle: (title) => {
        doc.title = title;
      },
      event: (name, message, err) => {
        if (name === 'error') win.console.error(err !== undefined ? err : message);
      },
    };
  }

  // ---------------------------------------------------------------- publish

  const CB = Object.freeze({
    page,
    api,
    el,
    form,
    go,
    refresh,
    every,
    get me() {
      return state.me;
    },
    login,
    logout,
    reloadMe,
    avatar,
    userLink,
    time,
    plural,
    short,
    toast,
    badge,
    qs,
    start,
  });

  if (typeof host.attach === 'function') {
    host.attach({
      pages: () => Array.from(pages.values(), (p) => ({
        name: p.name,
        title: p.title,
        nav: p.nav,
        order: p.order,
        public: p.public,
      })),
      startWith,
      current: () => (state.view
        ? {name: state.view.name, title: state.view.page ? state.view.page.title : NOT_FOUND}
        : null),
    });
  }

  root.CB = CB;
})(globalThis);
