// page_profile: a user's profile (own profile: the edit form).
// CONTRACT (keep this comment; implement exactly this):
// CB.page('profile', {title: 'Profile', nav: 'Profile', order: 50, load, render})
// load(params): return (await CB.api('GET', '/api/users/' + (params.id || CB.me.id))).user
// render(u) -> CB.el('div', {class: 'stack'},
//   CB.el('div', {class: 'row'}, CB.avatar(u), CB.el('h2', {}, u.display_name)),
//   CB.el('div', {class: 'muted'}, '@' + u.username),
//   CB.el('p', {}, u.bio || 'No bio yet'),
//   CB.el('div', {class: 'muted'}, CB.plural(u.friend_count, 'friend')),
//   actions(u))
// actions(u) by u.relationship:
//   'self' -> CB.form({fields: [
//       {name: 'display_name', label: 'Display name', value: u.display_name},
//       {name: 'bio', label: 'Bio', type: 'textarea', value: u.bio}],
//     submit: 'Save profile',
//     onsubmit: async (v) => {
//       await CB.api('PUT', '/api/profile', {display_name: v.display_name, bio: v.bio});
//       CB.toast('Profile saved'); await CB.reloadMe(); CB.refresh(); }})
//   'none' -> button 'Add friend':
//       await CB.api('POST', '/api/friends/requests', {user_id: u.id}); CB.refresh()
//   'request_sent' -> button 'Cancel request':
//       await CB.api('DELETE', '/api/friends/requests/' + u.request_id); CB.refresh()
//   'request_received' -> button 'Accept':
//       await CB.api('POST', '/api/friends/requests/' + u.request_id + '/accept'); CB.refresh()
//   'friends' -> CB.el('div', {class: 'row'},
//       button 'Message': const r = await CB.api('POST', '/api/dm', {user_id: u.id});
//                         CB.go('chat', {id: r.conversation.id})
//       button 'Unfriend': await CB.api('DELETE', '/api/friends/' + u.id); CB.refresh())
// Server answer: {user: {id, username, display_name, bio, joined_at, relationship, friend_count,
// request_id}}.
CB.page('profile', {
  title: 'Profile',
  nav: 'Profile',
  order: 50,
  render: () => CB.el('p', {class: 'muted'}, 'Coming soon'),
});
