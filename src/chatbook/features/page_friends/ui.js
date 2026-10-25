// page_friends: friend requests and the friend list.
// CONTRACT (keep this comment; implement exactly this):
// CB.page('friends', {title: 'Friends', nav: 'Friends', order: 20, load, render})
// load(): req = await CB.api('GET', '/api/friends/requests')
//         fr = await CB.api('GET', '/api/friends');  return {req, friends: fr.friends}
// render(d) -> CB.el('div', {class: 'stack'}, in this order:
//   CB.el('h2', {}, 'Friend requests'),
//   d.req.incoming.length ? d.req.incoming.map(incoming)
//                         : CB.el('p', {class: 'muted'}, 'No requests'),
//   CB.el('h2', {}, 'Sent requests'),
//   d.req.outgoing.length ? d.req.outgoing.map(outgoing)
//                         : CB.el('p', {class: 'muted'}, 'No sent requests'),
//   CB.el('h2', {}, 'Friends (' + d.friends.length + ')'),
//   d.friends.length ? d.friends.map(friend) : CB.el('p', {class: 'muted'}, 'No friends yet'))
// incoming(r) = item: CB.avatar(r.from), CB.userLink(r.from),
//   button testid 'accept-' + r.id 'Accept':
//     await CB.api('POST', '/api/friends/requests/' + r.id + '/accept'); CB.refresh()
//   button testid 'decline-' + r.id 'Decline':
//     await CB.api('POST', '/api/friends/requests/' + r.id + '/decline'); CB.refresh()
// outgoing(r) = item: CB.avatar(r.to), CB.userLink(r.to),
//   button testid 'cancel-' + r.id 'Cancel':
//     await CB.api('DELETE', '/api/friends/requests/' + r.id); CB.refresh()
// friend(f) = item: CB.avatar(f), CB.userLink(f),
//   button testid 'message-' + f.id 'Message':
//     const r = await CB.api('POST', '/api/dm', {user_id: f.id}); CB.go('chat', {id: r.conversation.id})
//   button testid 'unfriend-' + f.id 'Unfriend':
//     await CB.api('DELETE', '/api/friends/' + f.id); CB.refresh()
// ("item" = CB.el('div', {class: 'item'}, ...).)
// Server answers: GET /api/friends/requests -> {incoming: [R], outgoing: [R]} with
// R = {id, from: U, to: U, created_at}; GET /api/friends -> {friends: [U]}.
CB.page('friends', {
  title: 'Friends',
  nav: 'Friends',
  order: 20,
  render: () => CB.el('p', {class: 'muted'}, 'Coming soon'),
});
