// Loads and adds notes through the JSON API.
const list = document.querySelector('#notes');
const form = document.querySelector('#add-note');

function csrfToken() {
  return document.cookie.split('; ').find(part => part.startsWith('csrf_token='))?.slice('csrf_token='.length) ?? '';
}

async function getApiToken() {
  await fetch('/api/token', { method: 'POST', headers: { 'X-CSRF-Token': csrfToken() } });
}

async function load() {
  const response = await fetch('/api/notes');
  if (!response.ok) return;
  const { notes } = await response.json();
  list.replaceChildren(...notes.map(note => Object.assign(document.createElement('li'), { textContent: note.text })));
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  const text = new FormData(form).get('text');
  await fetch('/api/notes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken() },
    body: JSON.stringify({ text }),
  });
  form.reset();
  await load();
});

await getApiToken();
await load();
