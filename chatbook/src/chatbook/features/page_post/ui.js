// page_post: one post with its comments.
// CONTRACT (keep this comment; implement exactly this):
// CB.page('post', {title: 'Post', load, render})                       no nav
// load(params):
//   const a = await CB.api('GET', '/api/posts/' + params.id)
//   const b = await CB.api('GET', '/api/posts/' + params.id + '/comments')
//   return {post: a.post, comments: b.comments}
// render(d, params) -> CB.el('div', {class: 'stack'}, in this order:
//   CB.el('button', {onclick: () => CB.go('feed')}, 'Back to feed'),
//   CB.el('div', {class: 'card'},
//     CB.el('div', {class: 'row'}, CB.avatar(d.post.author), CB.userLink(d.post.author),
//           CB.el('small', {class: 'muted'}, CB.time(d.post.created_at))),
//     CB.el('p', {}, d.post.body),
//     CB.el('button', {testid: 'like-' + d.post.id, onclick: async () => {
//         await CB.api(d.post.liked ? 'DELETE' : 'POST', '/api/posts/' + d.post.id + '/like');
//         CB.refresh(); }}, (d.post.liked ? 'Unlike' : 'Like') + ' (' + d.post.like_count + ')')),
//   CB.el('h3', {}, 'Comments (' + d.comments.length + ')'),
//   d.comments.length ? d.comments.map(comment) : CB.el('p', {class: 'muted'}, 'No comments yet'),
//   CB.form({fields: [{name: 'body', label: 'Write a comment'}], submit: 'Comment', reset: true,
//            onsubmit: async (v) => {
//              const text = v.body.trim(); if (text === '') return;
//              await CB.api('POST', '/api/posts/' + params.id + '/comments', {body: text});
//              CB.refresh(); }}))
// comment(k) (defined inside render, so it can read d) = CB.el('div', {class: 'item'},
//   CB.avatar(k.author), CB.userLink(k.author),
//   CB.el('span', {}, k.body), CB.el('small', {class: 'muted'}, CB.time(k.created_at)),
//   k.author.id === CB.me.id || d.post.author.id === CB.me.id
//     ? CB.el('button', {testid: 'delete-' + k.id, onclick: async () => {
//         await CB.api('DELETE', '/api/comments/' + k.id); CB.refresh(); }}, 'Delete')
//     : null)
// Server answers: {post: Post}; {comments: [K]}, K = {id, post_id, author: U, body, created_at}.
CB.page('post', {
  title: 'Post',
  load: async (params) => {
    const a = await CB.api('GET', '/api/posts/' + params.id);
    const b = await CB.api('GET', '/api/posts/' + params.id + '/comments');
    return { post: a.post, comments: b.comments };
  },
  render: (d, params) => {
    const comment = (k) => CB.el('div', { class: 'item' },
      CB.avatar(k.author),
      CB.userLink(k.author),
      CB.el('span', {}, k.body),
      CB.el('small', { class: 'muted' }, CB.time(k.created_at)),
      k.author.id === CB.me.id || d.post.author.id === CB.me.id
        ? CB.el('button', { testid: 'delete-' + k.id, onclick: async () => {
            await CB.api('DELETE', '/api/comments/' + k.id);
            CB.refresh();
          } }, 'Delete')
        : null
    );

    return CB.el('div', { class: 'stack' },
      CB.el('button', { onclick: () => CB.go('feed') }, 'Back to feed'),
      CB.el('div', { class: 'card' },
        CB.el('div', { class: 'row' },
          CB.avatar(d.post.author),
          CB.userLink(d.post.author),
          CB.el('small', { class: 'muted' }, CB.time(d.post.created_at))
        ),
        CB.el('p', {}, d.post.body),
        CB.el('button', { testid: 'like-' + d.post.id, onclick: async () => {
            await CB.api(d.post.liked ? 'DELETE' : 'POST', '/api/posts/' + d.post.id + '/like');
            CB.refresh();
          } }, (d.post.liked ? 'Unlike' : 'Like') + ' (' + d.post.like_count + ')')
      ),
      CB.el('h3', {}, 'Comments (' + d.comments.length + ')'),
      d.comments.length ? d.comments.map(comment) : CB.el('p', { class: 'muted' }, 'No comments yet'),
      CB.form({
        fields: [{ name: 'body', label: 'Write a comment' }],
        submit: 'Comment',
        reset: true,
        onsubmit: async (v) => {
          const text = v.body.trim(); if (text === '') return;
          await CB.api('POST', '/api/posts/' + params.id + '/comments', { body: text });
          CB.refresh();
        }
      })
    );
  }
});
