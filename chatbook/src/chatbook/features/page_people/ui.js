// page_people: search people and act on each result.
// CONTRACT (keep this comment; implement exactly this):
// CB.page('people', {title: 'People', nav: 'People', order: 30, load, render})
// load(params): q = (params.q || '').trim()
//   if q === '' -> return {q: '', users: null}
//   r = await CB.api('GET', '/api/users' + CB.qs({q}));  return {q, users: r.users}
// render(d) -> CB.el('div', {class: 'stack'},
//   CB.form({fields: [{name: 'q', label: 'Search people', value: d.q}], submit: 'Search',
//            onsubmit: (v) => CB.go('people', {q: v.q.trim()})}),
//   d.users === null      -> CB.el('p', {class: 'muted'}, 'Search by name or username')
//   d.users.length === 0  -> CB.el('p', {class: 'muted'}, 'No people found')
//   otherwise             -> d.users.map(row))
// row(u) = CB.el('div', {class: 'item'}, CB.avatar(u), CB.userLink(u),
//                 CB.el('span', {class: 'muted'}, '@' + u.username), action(u))
// action(u) by u.relationship:
//   'none'             -> CB.el('button', {testid: 'add-' + u.id, onclick: async () => {
//                           await CB.api('POST', '/api/friends/requests', {user_id: u.id});
//                           CB.toast('Request sent'); CB.refresh(); }}, 'Add friend')
//   'request_sent'     -> CB.el('button', {disabled: true}, 'Requested')
//   'request_received' -> CB.el('button', {onclick: () => CB.go('friends')}, 'Respond')
//   'friends'          -> CB.el('button', {testid: 'message-' + u.id, onclick: async () => {
//                           const r = await CB.api('POST', '/api/dm', {user_id: u.id});
//                           CB.go('chat', {id: r.conversation.id}); }}, 'Message')
// Server answers: GET /api/users -> {users: [{id, username, display_name, relationship}]};
// POST /api/dm -> {conversation: {id, ...}}.

async function load(params) {
  const q = (params.q || '').trim();
  if (q === '') {
    return { q: '', users: null };
  }
  const r = await CB.api('GET', '/api/users' + CB.qs({ q }));
  return { q, users: r.users };
}

function render(d) {
  return CB.el('div', { class: 'stack' },
    CB.form({
      fields: [{ name: 'q', label: 'Search people', value: d.q }],
      submit: 'Search',
      onsubmit: (v) => CB.go('people', { q: v.q.trim() })
    }),
    d.users === null
      ? CB.el('p', { class: 'muted' }, 'Search by name or username')
      : d.users.length === 0
        ? CB.el('p', { class: 'muted' }, 'No people found')
        : d.users.map(row)
  );
}

function row(u) {
  return CB.el('div', { class: 'item' }, CB.avatar(u), CB.userLink(u),
    CB.el('span', { class: 'muted' }, '@' + u.username), action(u)
  );
}

function action(u) {
  switch (u.relationship) {
    case 'none':
      return CB.el('button', { testid: 'add-' + u.id, onclick: async () => {
        await CB.api('POST', '/api/friends/requests', { user_id: u.id });
        CB.toast('Request sent'); CB.refresh();
      }}, 'Add friend');
    case 'request_sent':
      return CB.el('button', { disabled: true }, 'Requested');
    case 'request_received':
      return CB.el('button', { onclick: () => CB.go('friends') }, 'Respond');
    case 'friends':
      return CB.el('button', { testid: 'message-' + u.id, onclick: async () => {
        const r = await CB.api('POST', '/api/dm', { user_id: u.id });
        CB.go('chat', { id: r.conversation.id });
      }}, 'Message');
    default:
      return CB.el('span', {}, 'Unknown');
  }
}

CB.page('people', {
  title: 'People',
  nav: 'People',
  order: 30,
  load,
  render
});
