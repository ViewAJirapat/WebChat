// page_group_new: the new group form.
// CONTRACT (keep this comment; implement exactly this):
// CB.page('group_new', {title: 'New group', load, render})            no nav
// load(): return await CB.api('GET', '/api/friends')                   // {friends: [U]}
// render(d) -> d.friends.length === 0
//   ? CB.el('p', {class: 'muted'}, 'Add friends first')
//   : CB.form({fields: [
//         {name: 'title', label: 'Group name'},
//         {name: 'members', label: 'Members', type: 'checkboxes',
//          options: d.friends.map((f) => ({value: String(f.id), label: f.display_name}))}],
//       submit: 'Create group',
//       onsubmit: async (v) => {
//         const r = await CB.api('POST', '/api/groups',
//                                {title: v.title, member_ids: v.members.map(Number)});
//         CB.go('chat', {id: r.conversation.id}); }})
// Server answer of POST /api/groups: {conversation: C}.
CB.page('group_new', {
  title: 'New group',
  render: () => CB.el('p', {class: 'muted'}, 'Coming soon'),
});
