const messages = document.getElementById('messages');
const quickReplies = document.getElementById('quickReplies');
const form = document.getElementById('chatForm');
const input = document.getElementById('chatInput');
const resetBtn = document.getElementById('resetBtn');
const uploadBox = document.getElementById('uploadBox');
const fileInput = document.getElementById('fileInput');
const uploadBtn = document.getElementById('uploadBtn');
const uploadStatus = document.getElementById('uploadStatus');
const navToggle = document.getElementById('navToggle');
const siteNav = document.getElementById('siteNav');
let sessionId = null;
let claimReference = null;
const userId = localStorage.getItem('zenith_user_id') || `web-${crypto.randomUUID()}`;
localStorage.setItem('zenith_user_id', userId);

function bubble(text, who='bot') {
  const el = document.createElement('div');
  el.className = `msg ${who}`;
  const t = document.createElement('div'); t.textContent = text; el.appendChild(t);
  const tm = document.createElement('span'); tm.className='time'; tm.textContent = new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}); el.appendChild(tm);
  messages.appendChild(el); messages.scrollTop = messages.scrollHeight;
}

function renderResponse(data) {
  (data.messages || []).forEach(m => bubble(m, 'bot'));
  quickReplies.innerHTML = '';
  (data.options || []).forEach(opt => {
    const b = document.createElement('button'); b.type='button'; b.textContent=opt.label; b.onclick=()=>send(opt.value, opt.label); quickReplies.appendChild(b);
  });
  input.placeholder = data.input_hint || 'Type a message…';
  if (data.claim_reference) claimReference = data.claim_reference;
  uploadBox.classList.toggle('hidden', !(data.allow_attachment && claimReference));
}

async function start() {
  messages.innerHTML=''; quickReplies.innerHTML=''; uploadBox.classList.add('hidden'); claimReference=null;
  try {
    const r = await fetch('/api/v1/chat/start', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:userId,channel:'web'})});
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || 'Service unavailable');
    sessionId=data.session_id; renderResponse(data);
  } catch(e) {
    sessionId = null;
    bubble(`The digital assistant is temporarily unavailable. Please call Zenith on +266 2232 4347 for assistance.`, 'bot');
  }
}

async function send(value, display=null) {
  const text = (value || '').trim(); if (!text || !sessionId) return;
  bubble(display || text, 'user'); input.value=''; quickReplies.innerHTML='';
  try {
    const r = await fetch('/api/v1/chat/message', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({session_id:sessionId,text})});
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || 'Request failed');
    renderResponse(data);
  } catch(e) { bubble(`Sorry, the service could not process that message: ${e.message}`, 'bot'); }
}

form.addEventListener('submit', e => {e.preventDefault(); send(input.value)});
resetBtn.addEventListener('click', start);
uploadBtn.addEventListener('click', async () => {
  if (!claimReference || !fileInput.files[0]) {uploadStatus.textContent='Choose a file first.'; return;}
  const fd = new FormData(); fd.append('file', fileInput.files[0]);
  uploadStatus.textContent='Uploading…';
  try {
    const r = await fetch(`/api/v1/claims/${encodeURIComponent(claimReference)}/attachments`, {method:'POST',body:fd});
    const data=await r.json(); if(!r.ok) throw new Error(data.detail || 'Upload failed');
    uploadStatus.textContent=`Uploaded ${data.filename} successfully.`; fileInput.value='';
  } catch(e){uploadStatus.textContent=e.message;}
});

if (navToggle && siteNav) {
  navToggle.addEventListener('click', () => {
    const open = siteNav.classList.toggle('open');
    navToggle.setAttribute('aria-expanded', String(open));
    navToggle.textContent = open ? '×' : '☰';
  });
  siteNav.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
    siteNav.classList.remove('open');
    navToggle.setAttribute('aria-expanded', 'false');
    navToggle.textContent = '☰';
  }));
}

document.querySelectorAll('a[href="#assistant"]').forEach(link => {
  link.addEventListener('click', () => setTimeout(() => input?.focus(), 450));
});

start();
