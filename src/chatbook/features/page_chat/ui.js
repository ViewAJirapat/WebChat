// page_chat: one conversation thread with the composer.
// CONTRACT (keep this comment; implement exactly this):
// CB.page('chat', {title: 'Chat', poll: 2000, load, render})          no nav
// load(params):
//   const limit = Number(params.limit || 50)
//   const d = await CB.api('GET', '/api/conversations/' + params.id)     // {conversation, reads}
//   const h = await CB.api('GET', '/api/conversations/' + params.id + '/messages' + CB.qs({limit}))
//   if (d.conversation.unread > 0) await CB.api('POST', '/api/conversations/' + params.id + '/read')
//   return {conv: d.conversation, reads: d.reads, messages: h.messages, hasMore: h.has_more, limit}
// render(d, params) -> CB.el('div', {class: 'stack'}, in this order:
//   CB.el('div', {class: 'row'}, CB.el('h2', {}, d.conv.title), d.conv.kind === 'group'
//     ? CB.el('button', {onclick: () => CB.go('group', {id: params.id})}, 'Group settings') : null),
//   CB.el('div', {class: 'muted'}, d.conv.members.map((m) => m.display_name).join(', ')),
//   d.hasMore ? CB.el('button', {onclick: () => CB.go('chat', {id: params.id, limit: d.limit + 50})},
//                     'Show older') : null,
//   CB.el('div', {class: 'messages'},
//         d.messages.length ? d.messages.map(row) : CB.el('p', {class: 'muted'}, 'Say hi!')),
//   seen(d) ? CB.el('div', {class: 'muted'}, 'Seen') : null,
//   CB.form({fields: [{name: 'body', label: 'Write a message'}], submit: 'Send', reset: true,
//            onsubmit: async (v) => {
//              const text = v.body.trim(); if (text === '') return;
//              await CB.api('POST', '/api/conversations/' + params.id + '/messages', {body: text});
//              CB.refresh(); }}))
// row(m) = CB.el('div', {class: m.sender.id === CB.me.id ? 'msg mine' : 'msg'}, CB.avatar(m.sender),
//   CB.el('b', {}, m.sender.display_name), ': ', m.body, ' ',
//   CB.el('small', {class: 'muted'}, CB.time(m.created_at)))
// seen(d): mine = the messages whose sender.id === CB.me.id; none -> false; last = id of the last
//   of them; true when some r in d.reads has r.user_id !== CB.me.id and r.last_read_id >= last
// Server answers: GET /api/conversations/{id} -> {conversation: C, reads: [{user_id, last_read_id}]};
//   GET .../messages -> {messages: [M], has_more}; POST .../messages -> {message: M}.
CB.page('chat', {
  title: 'Chat',
  render: () => CB.el('p', {class: 'muted'}, 'Coming soon'),
});
