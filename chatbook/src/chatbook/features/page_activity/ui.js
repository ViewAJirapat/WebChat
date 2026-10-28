// page_activity: my comments and likes on posts I can no longer see.
// CONTRACT (keep this comment; implement exactly this):
// CB.page('activity', {title: 'My activity', nav: 'Activity', order: 45, load, render})  no poll
// load(): return await CB.api('GET', '/api/activity/hidden')
// render(d) -> CB.el('div', {class: 'stack'}, in this order:
//   CB.el('p', {class: 'muted'}, 'Your comments and likes on posts you can no longer see'),
//   CB.el('h2', {}, 'Comments (' + d.comments.length + ')'),
//   d.comments.length ? d.comments.map((k) => CB.el('div', {class: 'item'},
//       CB.el('span', {}, 'You commented on a post by'), CB.userLink(k.post_author),
//       CB.el('span', {}, k.body), CB.el('small', {class: 'muted'}, CB.time(k.created_at)),
//       CB.el('button', {testid: 'delete-' + k.id, onclick: async () => {
//           await CB.api('DELETE', '/api/comments/' + k.id); CB.refresh(); }}, 'Delete')))
//     : CB.el('p', {class: 'muted'}, 'No comments to remove'),
//   CB.el('h2', {}, 'Likes (' + d.likes.length + ')'),
//   d.likes.length ? d.likes.map((l) => CB.el('div', {class: 'item'},
//       CB.el('span', {}, 'You liked a post by'), CB.userLink(l.post_author),
//       CB.el('small', {class: 'muted'}, CB.time(l.created_at)),
//       CB.el('button', {testid: 'unlike-' + l.post_id, onclick: async () => {
//           await CB.api('DELETE', '/api/posts/' + l.post_id + '/like'); CB.refresh(); }},
//         'Unlike')))
//     : CB.el('p', {class: 'muted'}, 'No likes to remove'))
// Server answer: {comments: [{id, post_id, post_author: U, body, created_at}],
//   likes: [{post_id, post_author: U, created_at}]}   (a like has no id: use l.post_id)
// No link to the post (its page answers 404 now). No toast, no try/catch.

async function load() {
  return await CB.api('GET', '/api/activity/hidden');
}

CB.page('activity', {
  title: 'My activity',
  nav: 'Activity',
  order: 45,
  load,
  render: (d) => CB.el('div', {class: 'stack'}, [
    CB.el('p', {class: 'muted'}, 'Your comments and likes on posts you can no longer see'),
    CB.el('h2', {}, 'Comments (' + d.comments.length + ')'),
    d.comments.length ? d.comments.map((k) => CB.el('div', {class: 'item'}, [
      CB.el('span', {}, 'You commented on a post by'),
      CB.userLink(k.post_author),
      CB.el('span', {}, k.body),
      CB.el('small', {class: 'muted'}, CB.time(k.created_at)),
      CB.el('button', {testid: 'delete-' + k.id, onclick: async () => {
        await CB.api('DELETE', '/api/comments/' + k.id); CB.refresh();
      }}, 'Delete')
    ])) : CB.el('p', {class: 'muted'}, 'No comments to remove'),
    CB.el('h2', {}, 'Likes (' + d.likes.length + ')'),
    d.likes.length ? d.likes.map((l) => CB.el('div', {class: 'item'}, [
      CB.el('span', {}, 'You liked a post by'),
      CB.userLink(l.post_author),
      CB.el('small', {class: 'muted'}, CB.time(l.created_at)),
      CB.el('button', {testid: 'unlike-' + l.post_id, onclick: async () => {
        await CB.api('DELETE', '/api/posts/' + l.post_id + '/like'); CB.refresh();
      }}, 'Unlike')
    ])) : CB.el('p', {class: 'muted'}, 'No likes to remove')
  ])
});
