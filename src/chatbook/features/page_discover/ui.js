// page_discover: friends online now and people you may know.
// CONTRACT (keep this comment; implement exactly this):
// CB.page('discover', {title: 'Discover', nav: 'Discover', order: 35, poll: 15000, load, render})
// load(): const on = await CB.api('GET', '/api/friends/online')
//         const sg = await CB.api('GET', '/api/friends/suggestions')
//         return {online: on.online, suggestions: sg.suggestions}
// render(d) -> CB.el('div', {class: 'stack'}, in this order:
//   CB.el('h2', {}, 'Online now'),
//   d.online.length ? d.online.map((u) => CB.el('div', {class: 'item'}, CB.avatar(u), CB.userLink(u),
//       CB.el('button', {testid: 'message-' + u.id, onclick: async () => {
//           const r = await CB.api('POST', '/api/dm', {user_id: u.id});
//           CB.go('chat', {id: r.conversation.id}); }}, 'Message')))
//     : CB.el('p', {class: 'muted'}, 'Nobody is online'),
//   CB.el('h2', {}, 'People you may know'),
//   d.suggestions.length ? d.suggestions.map((s) => CB.el('div', {class: 'item'}, CB.avatar(s),
//       CB.userLink(s), CB.el('span', {class: 'muted'}, CB.plural(s.mutual, 'mutual friend')),
//       CB.el('button', {testid: 'add-' + s.id, onclick: async () => {
//           await CB.api('POST', '/api/friends/requests', {user_id: s.id});
//           CB.toast('Request sent'); CB.refresh(); }}, 'Add friend')))
//     : CB.el('p', {class: 'muted'}, 'No suggestions'))
// Server answers: {online: [U]}; {suggestions: [U + mutual]}.
CB.page('discover', {
  title: 'Discover',
  nav: 'Discover',
  order: 35,
  poll: 15000,
  load: async () => {
    const on = await CB.api('GET', '/api/friends/online');
    const sg = await CB.api('GET', '/api/friends/suggestions');
    return { online: on.online, suggestions: sg.suggestions };
  },
  render: (d) => CB.el('div', { class: 'stack' },
    CB.el('h2', {}, 'Online now'),
    d.online.length ? d.online.map((u) => CB.el('div', { class: 'item' },
      CB.avatar(u),
      CB.userLink(u),
      CB.el('button', { testid: 'message-' + u.id, onclick: async () => {
        const r = await CB.api('POST', '/api/dm', { user_id: u.id });
        CB.go('chat', { id: r.conversation.id });
      }}, 'Message')
    )) : CB.el('p', { class: 'muted' }, 'Nobody is online'),
    CB.el('h2', {}, 'People you may know'),
    d.suggestions.length ? d.suggestions.map((s) => CB.el('div', { class: 'item' },
      CB.avatar(s),
      CB.userLink(s),
      CB.el('span', { class: 'muted' }, CB.plural(s.mutual, 'mutual friend')),
      CB.el('button', { testid: 'add-' + s.id, onclick: async () => {
        await CB.api('POST', '/api/friends/requests', { user_id: s.id });
        CB.toast('Request sent');
        CB.refresh();
      }}, 'Add friend')
    )) : CB.el('p', { class: 'muted' }, 'No suggestions')
  )
});
