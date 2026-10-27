// page_group: group settings (rename, members, add a friend, leave).
// CONTRACT (keep this comment; implement exactly this):
// CB.page('group', {title: 'Group settings', load, render})           no nav
// load(params):
//   const c = (await CB.api('GET', '/api/conversations/' + params.id)).conversation
//   if (c.kind !== 'group') return {c, friends: []}
//   const f = await CB.api('GET', '/api/friends');  return {c, friends: f.friends}
// render(d, params) -> d.c.kind !== 'group' ? CB.el('p', {class: 'muted'}, 'Not a group')
//  : CB.el('div', {class: 'stack'}, in this order:
//   CB.el('div', {class: 'row'}, CB.el('h2', {}, d.c.title),
//         CB.el('button', {onclick: () => CB.go('chat', {id: params.id})}, 'Back to chat')),
//   CB.form({fields: [{name: 'title', label: 'Group name', value: d.c.title}], submit: 'Rename',
//            onsubmit: async (v) => {
//              await CB.api('PUT', '/api/groups/' + params.id, {title: v.title});
//              CB.toast('Renamed'); CB.refresh(); }}),
//   CB.el('h3', {}, 'Members (' + d.c.members.length + ')'),
//   d.c.members.map((m) => CB.el('div', {class: 'item'}, CB.avatar(m), CB.userLink(m))),
//   candidates.length ? CB.form({fields: [{name: 'user_id', label: 'Add a friend', type: 'select',
//         options: candidates.map((f) => ({value: String(f.id), label: f.display_name}))}],
//       submit: 'Add',
//       onsubmit: async (v) => {
//         await CB.api('POST', '/api/groups/' + params.id + '/members', {user_id: Number(v.user_id)});
//         CB.refresh(); }}) : null,
//   CB.el('button', {class: 'danger', onclick: async () => {
//       await CB.api('DELETE', '/api/groups/' + params.id + '/members/me');
//       CB.go('inbox'); }}, 'Leave group'))
// candidates = d.friends that are not in d.c.members (compare ids)
// Server answers: GET /api/conversations/{id} -> {conversation: C, reads};
//   GET /api/friends -> {friends: [U]}.

CB.page('group', {
  title: 'Group settings',
  load: async (params) => {
    const c = (await CB.api('GET', '/api/conversations/' + params.id)).conversation;
    if (c.kind !== 'group') return { c, friends: [] };
    const f = await CB.api('GET', '/api/friends');
    return { c, friends: f.friends };
  },
  render: (d, params) => {
    if (d.c.kind !== 'group') {
      return CB.el('p', { class: 'muted' }, 'Not a group');
    }

    const candidates = d.friends.filter(friend => !d.c.members.some(member => member.id === friend.id));

    return CB.el('div', { class: 'stack' },
      CB.el('div', { class: 'row' },
        CB.el('h2', {}, d.c.title),
        CB.el('button', { onclick: () => CB.go('chat', { id: params.id }) }, 'Back to chat')
      ),
      CB.form({
        fields: [{ name: 'title', label: 'Group name', value: d.c.title }],
        submit: 'Rename',
        onsubmit: async (v) => {
          await CB.api('PUT', '/api/groups/' + params.id, { title: v.title });
          CB.toast('Renamed');
          CB.refresh();
        }
      }),
      CB.el('h3', {}, 'Members (' + d.c.members.length + ')'),
      d.c.members.map((m) => CB.el('div', { class: 'item' }, CB.avatar(m), CB.userLink(m))),
      candidates.length ? CB.form({
        fields: [{
          name: 'user_id',
          label: 'Add a friend',
          type: 'select',
          options: candidates.map((f) => ({ value: String(f.id), label: f.display_name }))
        }],
        submit: 'Add',
        onsubmit: async (v) => {
          await CB.api('POST', '/api/groups/' + params.id + '/members', { user_id: Number(v.user_id) });
          CB.refresh();
        }
      }) : null,
      CB.el('button', { class: 'danger', onclick: async () => {
        await CB.api('DELETE', '/api/groups/' + params.id + '/members/me');
        CB.go('inbox');
      }}, 'Leave group')
    );
  }
});
