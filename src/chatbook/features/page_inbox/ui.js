// page_inbox: the conversation list (home page).
// CONTRACT (keep this comment; implement exactly this):
// CB.page('inbox', {title: 'Chats', nav: 'Chats', order: 10, poll: 3000, load, render})
// load(): return await CB.api('GET', '/api/conversations')
// render(d) -> CB.el('div', {class: 'stack'},
//   CB.el('div', {class: 'row'}, CB.el('h2', {}, 'Chats'),
//         CB.el('button', {onclick: () => CB.go('group_new')}, 'New group')),
//   d.conversations.length ? d.conversations.map(item)
//                          : CB.el('p', {class: 'muted'}, 'No conversations yet'))
// item(c) = CB.el('div', {class: c.unread > 0 ? 'item unread' : 'item', testid: 'conv-' + c.id,
//                         onclick: () => CB.go('chat', {id: c.id})},
//   CB.el('b', {}, c.title),
//   CB.el('div', {class: 'muted'}, c.last_message
//       ? c.last_message.sender.display_name + ': ' + CB.short(c.last_message.body, 60)
//       : 'No messages yet'),
//   CB.el('small', {class: 'muted'}, CB.time(c.updated_at)),
//   c.unread > 0 ? CB.el('span', {class: 'badge'}, String(c.unread)) : null)
// Server answer: {conversations: [C]}, C = {id, kind, title, members, last_message: M | null,
// unread, updated_at}, M = {id, conversation_id, sender: U, body, created_at}.
CB.page('inbox', {
  title: 'Chats',
  nav: 'Chats',
  order: 10,
  render: () => CB.el('p', {class: 'muted'}, 'Coming soon'),
});
