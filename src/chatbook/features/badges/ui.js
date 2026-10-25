// badges: the nav badge service (no page).
// CONTRACT (keep this comment; implement exactly this):
// No page. At the top level of the file:
// CB.every(5000, async () => {
//   const u = await CB.api('GET', '/api/updates');
//   CB.badge('inbox', u.unread_total);
//   CB.badge('friends', u.friend_requests);
// });
// Server answer: {unread_total, unread_conversations, friend_requests}.
CB.every(5000, async () => {});
