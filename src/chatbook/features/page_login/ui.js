// page_login: the login and register page (public).
// CONTRACT (keep this comment; implement exactly this):
// CB.page('login', {title: 'Welcome', public: true, render})      no nav, no load
// render() -> CB.el('div', {class: 'stack narrow'}, these four, in this order:
//   CB.el('h2', {}, 'Log in')
//   CB.form({fields: [{name: 'username', label: 'Username'},
//                     {name: 'password', label: 'Password', type: 'password'}],
//            submit: 'Log in',
//            onsubmit: async (v) => {
//              const r = await CB.api('POST', '/api/auth/login',
//                                     {username: v.username, password: v.password});
//              CB.login(r.token, r.user); }})
//   CB.el('h2', {}, 'Create account')
//   CB.form({fields: [{name: 'username', label: 'Username'},
//                     {name: 'display_name', label: 'Display name'},
//                     {name: 'password', label: 'Password', type: 'password'}],
//            submit: 'Create account',
//            onsubmit: async (v) => {
//              const r = await CB.api('POST', '/api/auth/register',
//                  {username: v.username, password: v.password, display_name: v.display_name});
//              CB.login(r.token, r.user); }}))
// Server answers: {token, user}. No try/catch.
CB.page('login', {
  title: 'Welcome',
  public: true,
  render: () => CB.el('p', {class: 'muted'}, 'Coming soon'),
});
