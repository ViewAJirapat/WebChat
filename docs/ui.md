# Browser pages: the CB toolkit

A page is one file src/chatbook/features/<name>/ui.js, loaded after cb.js in its own function
scope. Use only CB.* and plain JavaScript (no modules, no browser objects).

## A page
CB.page('people', {
  title: 'People',            // browser tab title
  nav: 'People',              // top-bar label; leave out for pages opened by links
  order: 30,                  // top-bar position
  load: async (params) => {   // optional: fetch data with CB.api and return it
    return await CB.api('GET', '/api/users' + CB.qs({q: params.q}));
  },
  render: (data, params) => CB.el('div', {class: 'stack'}, ...),   // return the page
  poll: 3000,                 // optional: run load + render again every 3000 ms
});
params: the URL parameters of the page, always strings ({} when none).
The app runs load, then render, and shows the result. CB.refresh() runs both again.
Text typed into form fields survives refresh and poll.

## Nodes
CB.el(tag, props, ...children) -> node
  props: class, testid, title, type, value, placeholder, disabled, checked, name, onclick
  children: strings, numbers, nodes, arrays of them; null is skipped. Text is shown as text.
  onclick may be async: onclick: async () => { await CB.api(...); CB.refresh(); }
After creating a node you may only use: node.append(...), node.replaceChildren(...),
node.textContent = '...', node.disabled = true/false. To change the page, call CB.refresh().

CB.form({fields, submit, reset, onsubmit}) -> form node
  fields: [{name, label, type, value, options}]
    type: 'text' (default), 'password', 'textarea', 'select', 'checkboxes'
    options (select, checkboxes): [{value: '2', label: 'Bob'}]   values are strings
    value: initial text (text, password, textarea) or selected value (select)
  submit: the button label; reset: true clears the text fields after a successful onsubmit
  onsubmit: async (values) => { ... }   values.name is a string; checkboxes give a string array

## Server
await CB.api(method, path, body) -> the JSON answer. An error answer is shown to the user and
stops your function; the app handles it, so never write try/catch. 401 logs the user out.
CB.qs({q: 'bo', limit: 20}) -> '?q=bo&limit=20' (empty values are skipped)

## Navigation and session
CB.go(name, params)  opens a page: CB.go('chat', {id: 5}) gives params {id: '5'}
CB.refresh()         CB.me (the logged-in user: {id, username, display_name})
CB.login(token, user) stores the session and opens 'inbox'    CB.logout()    CB.reloadMe()
CB.every(ms, fn)     runs fn now and every ms while logged in; call it at the top of the file

## Helpers
CB.avatar(user) -> node          CB.userLink(user) -> node (click opens the profile)
CB.time(ms) -> '14:05'           CB.plural(3, 'friend') -> '3 friends'
CB.short(text, 60) -> the first 60 characters + '...' when longer
CB.toast(text)                   CB.badge(pageName, n)  (n <= 0 hides it)

## CSS classes
stack (column with gaps), row (side by side), item (list row), unread, card, muted, badge,
messages (chat list), msg (bubble), mine (my bubble), danger (red button), narrow (thin column)

## Rejected by the gate
document, window, globalThis, fetch, XMLHttpRequest, innerHTML, outerHTML,
insertAdjacentHTML, eval, new Function, setTimeout, setInterval, localStorage, sessionStorage,
addEventListener, classList, style, setAttribute, querySelector, getElementById, import, require

## Example
CB.page('notes', {
  title: 'Notes', nav: 'Notes', order: 60,
  load: () => CB.api('GET', '/api/notes'),
  render: (data) => CB.el('div', {class: 'stack'},
    CB.el('h2', {}, 'Notes (' + data.notes.length + ')'),
    data.notes.length
      ? data.notes.map((n) => CB.el('div', {class: 'item'},
          CB.el('span', {}, n.text),
          CB.el('button', {testid: 'del-' + n.id, onclick: async () => {
            await CB.api('DELETE', '/api/notes/' + n.id);
            CB.refresh();
          }}, 'Delete')))
      : CB.el('p', {class: 'muted'}, 'No notes yet'),
    CB.form({fields: [{name: 'text', label: 'New note'}], submit: 'Add', reset: true,
      onsubmit: async (v) => {
        await CB.api('POST', '/api/notes', {text: v.text});
        CB.refresh();
      }})),
});
