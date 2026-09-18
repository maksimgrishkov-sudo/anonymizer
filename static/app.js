// Ширма — клиентская часть. Файлы читаются в браузере и уходят только на
// локальный сервер этой же программы. Внешних запросов страница не делает.

const $ = (id) => document.getElementById(id);

// Словарь замен копится между файлами одной пачки: так одна и та же
// компания в разных логах получает одну метку, и связи не рвутся.
let sharedMap = {};
let hidden = [];          // [{name, text}]
let restoreMap = {};

// ── вкладки ─────────────────────────────────────────────────────
document.querySelectorAll('.tab').forEach((t) => {
  t.onclick = () => {
    document.querySelectorAll('.tab').forEach((x) => x.classList.remove('active'));
    document.querySelectorAll('.pane').forEach((x) => x.classList.remove('active'));
    t.classList.add('active');
    $(t.dataset.tab).classList.add('active');
  };
});

// ── перетаскивание ──────────────────────────────────────────────
const drop = $('drop');
drop.onclick = () => $('files').click();
$('files').onchange = (e) => handle([...e.target.files]);

['dragenter', 'dragover'].forEach((ev) => drop.addEventListener(ev, (e) => {
  e.preventDefault(); drop.classList.add('over');
}));
['dragleave', 'drop'].forEach((ev) => drop.addEventListener(ev, (e) => {
  e.preventDefault(); drop.classList.remove('over');
}));
drop.addEventListener('drop', (e) => handle([...e.dataTransfer.files]));

function readFile(file) {
  return new Promise((resolve) => {
    const r = new FileReader();
    r.onload = () => resolve({ name: file.name, text: r.result });
    r.onerror = () => resolve(null);          // двоичное или нечитаемое — пропускаем
    r.readAsText(file, 'utf-8');
  });
}

async function handle(files) {
  if (!files.length) return;
  drop.querySelector('strong').textContent = 'Обрабатываю…';

  for (const f of files) {
    const got = await readFile(f);
    if (!got || !got.text) continue;
    const res = await post('/api/hide', { text: got.text, map: sharedMap });
    if (res.error) { alert(res.error); continue; }
    sharedMap = res.map;
    hidden.push({ name: got.name + '.anon', text: res.text, was: got.text.length });
    lastReport = res.report;
    lastLeft = res.left;
  }

  drop.querySelector('strong').textContent = 'Перетащите файлы сюда';
  render();
}

let lastReport = [], lastLeft = [];

function render() {
  if (!hidden.length) return;
  $('hideResult').hidden = false;

  $('reportCards').innerHTML = lastReport.map((r) => `
    <div class="card"><b>${r.unique}</b><span>${r.title}</span></div>`).join('');

  const warn = $('leftWarn');
  if (lastLeft.length) {
    warn.hidden = false;
    warn.innerHTML = `<b>Осталось подозрительное: ${lastLeft.length}.</b>
      Шаблоны ловят типовое; название компании и фамилии добавьте
      в <code>words.txt</code> и прогоните снова.`;
  } else {
    warn.hidden = true;
  }

  $('fileList').innerHTML = hidden.map((f) => `
    <div class="file"><span>${f.name}</span>
      <span class="meta">${f.text.length.toLocaleString('ru')} знаков</span></div>`).join('');

  $('hidePreview').textContent = hidden[hidden.length - 1].text.slice(0, 4000);
}

// ── скачивание ──────────────────────────────────────────────────
function save(name, text) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }));
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

$('dlFiles').onclick = () => hidden.forEach((f) => save(f.name, f.text));
$('dlMap').onclick = () => save('anon.map.json', JSON.stringify(sharedMap, null, 1));

// ── возврат ─────────────────────────────────────────────────────
$('mapFile').onchange = async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  const got = await readFile(f);
  try {
    restoreMap = JSON.parse(got.text);
    const n = Object.keys(restoreMap).length;
    $('mapState').textContent = `словарь загружен: ${n} замен`;
    $('mapState').className = 'mapstate ok';
  } catch {
    $('mapState').textContent = 'это не похоже на словарь замен';
    $('mapState').className = 'mapstate';
  }
};

$('doRestore').onclick = async () => {
  const res = await post('/api/restore', { text: $('restoreIn').value, map: restoreMap });
  $('restoreOut').hidden = false;
  $('restoreOut').textContent = res.text;
  if (!res.count) {
    $('restoreOut').textContent =
      'Ни одной метки не подставлено. Проверьте, что словарь тот самый.\n\n' + res.text;
  }
};

// ── проверка ────────────────────────────────────────────────────
$('doCheck').onclick = async () => {
  const res = await post('/api/check', { text: $('checkIn').value });
  const out = $('checkOut');
  if (!res.left.length) {
    out.innerHTML = '<div class="clean">Чисто: ничего похожего на секрет не нашёл.</div>';
    return;
  }
  out.innerHTML = '<div class="found">' + res.left.map((x) =>
    `<div>${x.title}: <code>${escapeHtml(x.value)}</code></div>`).join('') + '</div>';
};

function escapeHtml(s) {
  return s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

async function post(url, body) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return r.json();
}
