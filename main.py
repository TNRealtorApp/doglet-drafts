import os
import string
import random
import psycopg
from psycopg.rows import dict_row
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:DogletMemory2024!@switchyard.proxy.rlwy.net:53345/openclaw_memory"
)
BASE_URL = os.environ.get("BASE_URL", "https://doglet-drafts-production.up.railway.app")

def get_db():
    return psycopg.connect(DATABASE_URL)

def gen_id(length=8):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))

@app.on_event("startup")
def startup():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS drafts (
            id VARCHAR(12) PRIMARY KEY,
            content TEXT NOT NULL,
            draft_type VARCHAR(20) DEFAULT 'text',
            subject VARCHAR(500),
            recipient VARCHAR(500),
            created_at TIMESTAMP DEFAULT NOW(),
            expires_at TIMESTAMP DEFAULT (NOW() + INTERVAL '48 hours'),
            viewed_at TIMESTAMP,
            edit_count INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

class DraftCreate(BaseModel):
    content: str
    draft_type: str = "text"
    subject: Optional[str] = None
    recipient: Optional[str] = None

class DraftUpdate(BaseModel):
    content: str
    subject: Optional[str] = None

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/drafts")
def create_draft(draft: DraftCreate):
    draft_id = gen_id()
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO drafts (id, content, draft_type, subject, recipient) VALUES (%s, %s, %s, %s, %s)",
        (draft_id, draft.content, draft.draft_type, draft.subject, draft.recipient)
    )
    conn.commit()
    cur.close()
    conn.close()
    return {"id": draft_id, "url": f"{BASE_URL}/d/{draft_id}"}

@app.put("/api/drafts/{draft_id}")
def update_draft(draft_id: str, draft: DraftUpdate):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE drafts SET content=%s, subject=%s, edit_count=edit_count+1 WHERE id=%s AND (expires_at > NOW() OR expires_at IS NULL) RETURNING id",
        (draft.content, draft.subject, draft_id)
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if not row:
        raise HTTPException(404, "Draft not found or expired")
    return {"ok": True}

@app.delete("/api/drafts/{draft_id}")
def delete_draft(draft_id: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM drafts WHERE id=%s RETURNING id", (draft_id,))
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if not row:
        raise HTTPException(404, "Draft not found")
    return {"ok": True}

@app.get("/api/drafts/{draft_id}")
def get_draft_json(draft_id: str):
    conn = get_db()
    cur = conn.cursor(row_factory=dict_row)
    cur.execute(
        "SELECT * FROM drafts WHERE id=%s AND (expires_at > NOW() OR expires_at IS NULL)",
        (draft_id,)
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(404, "Draft not found or expired")
    if not row['viewed_at']:
        cur.execute("UPDATE drafts SET viewed_at=NOW() WHERE id=%s", (draft_id,))
        conn.commit()
    cur.close()
    conn.close()
    row['created_at'] = row['created_at'].isoformat() if row['created_at'] else None
    row['expires_at'] = row['expires_at'].isoformat() if row['expires_at'] else None
    row['viewed_at'] = row['viewed_at'].isoformat() if row['viewed_at'] else None
    return dict(row)

@app.get("/d/{draft_id}", response_class=HTMLResponse)
def view_draft(draft_id: str):
    return DRAFT_HTML.replace("__DRAFT_ID__", draft_id)

DRAFT_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Doglet Drafts</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
--bg-primary:#0a0a0b;--bg-secondary:#141416;--bg-tertiary:#1c1c1f;
--bg-elevated:#242426;--border-subtle:#2a2a2e;
--text-primary:#fafafa;--text-secondary:#a1a1a3;
--accent-primary:#10b981;--accent-secondary:#3b82f6;
}
body{font-family:'DM Sans',sans-serif;background:var(--bg-primary);color:var(--text-primary);min-height:100vh;-webkit-text-size-adjust:100%}
.container{max-width:600px;margin:0 auto;padding:16px}
.header{display:flex;align-items:center;justify-content:space-between;padding:12px 0;border-bottom:1px solid var(--border-subtle);margin-bottom:16px}
.brand{font-size:18px;font-weight:700;display:flex;align-items:center;gap:8px}
.expires{font-size:12px;color:var(--text-secondary)}
.meta{background:var(--bg-secondary);border-radius:12px;padding:14px 16px;margin-bottom:16px;border:1px solid var(--border-subtle)}
.meta-type{font-size:14px;color:var(--text-secondary);margin-bottom:4px}
.meta-subject{font-size:16px;font-weight:600}
.content-area{background:var(--bg-secondary);border-radius:12px;padding:18px;min-height:200px;border:1px solid var(--border-subtle);
  font-size:16px;line-height:1.6;color:var(--text-primary);outline:none;white-space:pre-wrap;word-wrap:break-word;margin-bottom:8px;
  -webkit-user-modify:read-write;overflow-wrap:break-word}
.content-area:empty::before{content:'Draft content...';color:var(--text-secondary)}
.content-area:focus{border-color:var(--accent-primary)}
.char-count{text-align:right;font-size:12px;color:var(--text-secondary);margin-bottom:16px}
.actions{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
.actions .btn-full{grid-column:1/-1}
.btn{display:flex;align-items:center;justify-content:center;gap:8px;padding:14px;border-radius:12px;border:1px solid var(--border-subtle);
  background:var(--bg-elevated);color:var(--text-primary);font-family:'DM Sans',sans-serif;font-size:15px;font-weight:600;
  cursor:pointer;text-decoration:none;transition:all .15s;-webkit-tap-highlight-color:transparent}
.btn:active{transform:scale(.97);opacity:.8}
.btn-primary{background:var(--accent-primary);border-color:var(--accent-primary);color:#000}
.btn-copied{background:#10b981!important;border-color:#10b981!important;color:#000!important}
.toast{position:fixed;bottom:100px;left:50%;transform:translateX(-50%);background:var(--accent-primary);color:#000;
  padding:10px 24px;border-radius:20px;font-size:14px;font-weight:600;opacity:0;transition:opacity .3s;pointer-events:none;z-index:99}
.toast.show{opacity:1}
.error-page{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:80vh;text-align:center;padding:20px}
.error-page h2{font-size:20px;margin:16px 0 8px}
.error-page p{color:var(--text-secondary);font-size:14px}
#loading{display:flex;align-items:center;justify-content:center;min-height:60vh;color:var(--text-secondary)}
</style>
</head>
<body>
<div class="container">
<div id="loading">Loading draft...</div>
<div id="draft" style="display:none">
  <div class="header">
    <div class="brand">🐼 Doglet Drafts</div>
    <div class="expires" id="expires"></div>
  </div>
  <div class="meta" id="meta">
    <div class="meta-type" id="metaType"></div>
    <div class="meta-subject" id="metaSubject"></div>
  </div>
  <div class="content-area" id="content" contenteditable="true" spellcheck="true"></div>
  <div class="char-count"><span id="charCount">0</span> chars</div>
  <div class="actions">
    <button class="btn" id="btnCopy" onclick="copyDraft()">📋 Copy</button>
    <button class="btn" id="btnEmail" onclick="openEmail()">📧 Email</button>
    <button class="btn" id="btnText" onclick="openText()">💬 Text</button>
    <button class="btn" id="btnWhatsApp" onclick="openWhatsApp()" style="background:#25D366;border-color:#25D366;color:#fff">💬 WhatsApp</button>
    <button class="btn btn-primary" id="btnShare" onclick="shareDraft()" style="grid-column:span 2">↗ Share</button>
  </div>
</div>
<div id="error" style="display:none" class="error-page">
  <div style="font-size:48px">🐼</div>
  <h2>Draft not found</h2>
  <p>This draft has expired or doesn't exist.</p>
</div>
</div>
<div class="toast" id="toast"></div>
<script>
const DRAFT_ID = "__DRAFT_ID__";
let draft = null;
let saveTimer = null;

async function load() {
  try {
    const r = await fetch(`/api/drafts/${DRAFT_ID}`);
    if (!r.ok) throw new Error();
    draft = await r.json();
    render();
  } catch {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('error').style.display = 'flex';
  }
}

function render() {
  document.getElementById('loading').style.display = 'none';
  document.getElementById('draft').style.display = 'block';
  const icon = draft.draft_type === 'email' ? '✉️' : '💬';
  const label = draft.draft_type === 'email' ? 'Email' : 'Text';
  const to = draft.recipient ? ` to ${draft.recipient}` : '';
  document.getElementById('metaType').textContent = `${icon} ${label}${to}`;
  if (draft.subject) {
    document.getElementById('metaSubject').textContent = `Subject: ${draft.subject}`;
  } else {
    document.getElementById('meta').style.display = draft.recipient ? 'block' : 'none';
    document.getElementById('metaSubject').style.display = 'none';
  }
  document.getElementById('content').textContent = draft.content;
  updateCount();
  if (draft.expires_at) {
    const ms = new Date(draft.expires_at) - Date.now();
    const h = Math.max(0, Math.floor(ms / 3600000));
    document.getElementById('expires').textContent = h > 0 ? `Expires in ${h}h` : 'Expiring soon';
  }
}

function updateCount() {
  document.getElementById('charCount').textContent = document.getElementById('content').textContent.length;
}

document.addEventListener('input', e => {
  if (e.target.id === 'content') {
    updateCount();
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveDraft, 1000);
  }
});

async function saveDraft() {
  const content = document.getElementById('content').textContent;
  try {
    await fetch(`/api/drafts/${DRAFT_ID}`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({content, subject: draft.subject})
    });
    showToast('Saved ✓');
  } catch {}
}

function getContent() { return document.getElementById('content').textContent; }

async function copyDraft() {
  try {
    await navigator.clipboard.writeText(getContent());
    const b = document.getElementById('btnCopy');
    b.classList.add('btn-copied');
    b.innerHTML = '✅ Copied!';
    setTimeout(() => { b.classList.remove('btn-copied'); b.innerHTML = '📋 Copy'; }, 2000);
  } catch { showToast('Copy failed'); }
}

function openEmail() {
  const s = draft.subject ? `subject=${enc(draft.subject)}&` : '';
  window.location.href = `mailto:?${s}body=${enc(getContent())}`;
}

function openText() {
  window.location.href = `sms:?body=${enc(getContent())}`;
}

function openWhatsApp() {
  window.location.href = `https://wa.me/?text=${enc(getContent())}`;
}

async function shareDraft() {
  if (navigator.share) {
    try {
      await navigator.share({text: getContent()});
    } catch {}
  } else {
    copyDraft();
  }
}

function enc(s) { return encodeURIComponent(s); }

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 1500);
}

load();
</script>
</body>
</html>"""
