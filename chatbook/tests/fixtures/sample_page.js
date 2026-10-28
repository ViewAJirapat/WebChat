// Frame test fixture (tests/test_ui_runtime.py, tests/test_testing.py): two pages and one job
// that use every documented CB function. Not a product page. The API it expects (mocked):
//   GET  /api/sample[?id=]       -> {owner: U, note, items: [{id, name, likes}]}
//   POST /api/sample             body = the "Add" form values -> {}
//   POST /api/sample/{id}/like   -> {}
//   POST /api/sample/fail        -> an error answer (each test picks the status)
//   GET  /api/sample/count       -> {n}            (the CB.every job, every 4000 ms)
//   POST /api/sample/login       body {name} -> {token, user}
//   GET  /api/ping               -> {}
const LABEL = 'Sample'; // the isolation test loads a second file that declares LABEL too
let renders = 0;

CB.every(4000, async () => {
  const u = await CB.api('GET', '/api/sample/count');
  CB.badge('sample', u.n);
});

const row = (it) => CB.el('div', {class: 'item', testid: 'item-' + it.id},
  CB.el('b', {}, it.name), ': ', CB.plural(it.likes, 'like'),
  CB.el('button', {testid: 'like-' + it.id, onclick: async () => {
    await CB.api('POST', '/api/sample/' + it.id + '/like');
    CB.refresh();
  }}, 'Like'));

const helpers = () => {
  CB.toast(CB.qs({a: 1, b: 'x y', c: null, d: undefined, e: ''}));
  CB.toast('[' + CB.qs({c: null}) + ']');
  CB.toast(CB.plural(1, 'friend'));
  CB.toast(CB.plural(3, 'friend'));
  CB.toast(CB.short('abcdef', 3));
  CB.toast(CB.short('abc', 3));
};

const addForm = () => CB.form({
  fields: [
    {name: 'name', label: 'Name'},
    {name: 'kind', label: 'Kind', type: 'select', value: 'b',
      options: [{value: 'a', label: 'Apple'}, {value: 'b', label: 'Banana'}]},
    {name: 'tags', label: 'Tags', type: 'checkboxes',
      options: [{value: '1', label: 'One'}, {value: '2', label: 'Two'}]},
    {name: 'note', label: 'Note', type: 'textarea'},
    {name: 'secret', label: 'Secret', type: 'password'},
  ],
  submit: 'Add',
  reset: true,
  onsubmit: async (v) => {
    await CB.api('POST', '/api/sample', v);
    CB.refresh();
  },
});

CB.page('sample', {
  title: LABEL,
  nav: LABEL,
  order: 60,
  poll: 1000,
  load: async (params) => {
    if (params.boom) throw new Error('boom in load');
    return await CB.api('GET', '/api/sample' + CB.qs({id: params.id}));
  },
  render: (d, params) => {
    renders += 1;
    return CB.el('div', {class: 'stack'},
      CB.el('h2', {}, LABEL + ' ' + (params.id || 'all')),
      CB.el('div', {class: 'row'}, CB.avatar(d.owner), CB.userLink(d.owner)),
      CB.el('p', {class: 'muted'}, 'Signed in as ' + (CB.me ? CB.me.display_name : 'nobody')),
      CB.el('p', {class: 'muted'}, 'Renders: ' + renders),
      CB.el('p', {class: 'muted'}, CB.short(d.note, 10)),
      CB.el('p', {class: 'raw'}, '<i>raw</i>', 5, null, false, undefined, ['A', ['B']]),
      d.items.length ? d.items.map(row) : CB.el('p', {class: 'muted'}, 'Nothing here'),
      CB.el('div', {class: 'row'},
        // 'Reload thrice' comes first: a click on 'Reload' must prefer the exact label
        CB.el('button', {onclick: () => { CB.refresh(); CB.refresh(); CB.refresh(); }},
          'Reload thrice'),
        CB.el('button', {onclick: () => CB.refresh()}, 'Reload'),
        CB.el('button', {onclick: () => CB.go('sample', {id: 7, flag: true})}, 'Open seven'),
        CB.el('button', {onclick: () => CB.api('POST', '/api/sample/fail')}, 'Fail'),
        CB.el('button', {onclick: () => CB.el('a', {href: '#'})}, 'Break'),
        CB.el('button', {onclick: () => CB.el('script', {})}, 'Bad tag'),
        CB.el('button', {onclick: async () => { await CB.reloadMe(); CB.refresh(); }},
          'Who am I'),
        CB.el('button', {onclick: helpers}, 'Helpers'),
        CB.el('button', {disabled: true}, 'Locked')),
      addForm(),
      CB.form({fields: [{name: 'q', label: 'Go to id'}], submit: 'Find',
        onsubmit: (v) => CB.go('sample', {id: v.q.trim()})}));
  },
});

CB.page('sample_open', {
  title: 'Open',
  public: true,
  render: () => CB.el('div', {class: 'stack narrow'},
    CB.el('button', {onclick: () => CB.api('GET', '/api/ping')}, 'Ping'),
    CB.form({fields: [{name: 'name', label: 'Name'}], submit: 'Sign in',
      onsubmit: async (v) => {
        const r = await CB.api('POST', '/api/sample/login', {name: v.name});
        CB.login(r.token, r.user);
      }})),
});
