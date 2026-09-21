import os, sqlite3, secrets, requests, json, urllib.parse, re
from flask import Flask, request, redirect, session, abort, render_template_string
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)
oauth_state = URLSafeTimedSerializer(app.secret_key, salt='discord-oauth-state')

DB = os.environ.get('DB_PATH', 'shop.db')

CID = os.environ.get('DISCORD_CLIENT_ID', '')
SECRET = os.environ.get('DISCORD_CLIENT_SECRET', '')
REDIRECT = os.environ.get('DISCORD_REDIRECT_URI', '')
GUILD = os.environ.get('DISCORD_GUILD_ID', '')
BOT = os.environ.get('DISCORD_BOT_TOKEN', '')
FREE = os.environ.get('FREE_ROLE_ID', '')
VIP = os.environ.get('VIP_ROLE_ID', '')
ADMIN = os.environ.get('ADMIN_KEY', '')
PRODUCT = os.environ.get('PRODUCT_NAME', 'デジタル商品')

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

with db() as c:
    c.execute('CREATE TABLE IF NOT EXISTS inventory(id INTEGER PRIMARY KEY AUTOINCREMENT,url TEXT UNIQUE,used INTEGER DEFAULT 0,used_by TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS claims(id INTEGER PRIMARY KEY AUTOINCREMENT,discord_id TEXT,url TEXT)')

def roles(uid):
    if not (GUILD and BOT): return []
    r = requests.get(f'https://discord.com/api/v10/guilds/{GUILD}/members/{uid}', headers={'Authorization': f'Bot {BOT}'}, timeout=10)
    return r.json().get('roles', []) if r.status_code == 200 else []

def kind(uid):
    rs = roles(uid)
    return 'vip' if VIP and VIP in rs else ('free' if FREE and FREE in rs else 'none')

THEME_CSS = '''
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        background-color: #0b0b0e;
        color: #f3f3f5;
        margin: 0;
        padding: 20px;
        display: flex;
        justify-content: center;
    }
    .container {
        width: 100%;
        max-width: 480px;
    }
    .card {
        background: #141418;
        border: 1px solid #22222c;
        padding: 24px;
        border-radius: 16px;
        margin-bottom: 16px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.4);
    }
    h1, h2 {
        margin-top: 0;
        font-size: 1.25rem;
        letter-spacing: -0.02em;
    }
    .logo {
        color: #e50914;
        font-weight: 800;
        letter-spacing: 1px;
    }
    p {
        color: #9ba1a6;
        font-size: 0.9rem;
        line-height: 1.5;
    }
    button, .btn {
        display: block;
        width: 100%;
        box-sizing: border-box;
        padding: 14px;
        border: 0;
        border-radius: 10px;
        background: #e50914;
        color: white;
        font-weight: 600;
        font-size: 0.95rem;
        text-align: center;
        text-decoration: none;
        cursor: pointer;
        transition: background 0.2s;
        margin-top: 14px;
    }
    button:hover, .btn:hover {
        background: #f40612;
    }
    .btn-secondary {
        background: #22222c;
        color: #f3f3f5;
    }
    .btn-secondary:hover {
        background: #2c2c38;
    }
    textarea, input[type=file] {
        width: 100%;
        box-sizing: border-box;
        padding: 12px;
        background: #0b0b0e;
        border: 1px solid #22222c;
        border-radius: 10px;
        color: #f3f3f5;
        font-family: monospace;
        margin-top: 8px;
        font-size: 0.85rem;
    }
    textarea:focus, input:focus {
        outline: none;
        border-color: #e50914;
    }
    .err {
        background: rgba(229, 9, 20, 0.1);
        border: 1px solid rgba(229, 9, 20, 0.3);
        color: #ff6b6b;
        padding: 12px;
        border-radius: 10px;
        margin-bottom: 16px;
        font-size: 0.9rem;
    }
    .badge {
        display: inline-block;
        padding: 4px 8px;
        background: #22222c;
        border-radius: 6px;
        font-size: 0.8rem;
        color: #f3f3f5;
    }
    hr {
        border: 0;
        border-top: 1px solid #22222c;
        margin: 16px 0;
    }
    .link-box {
        background: #0b0b0e;
        padding: 12px;
        border-radius: 8px;
        word-break: break-all;
        white-space: pre-wrap;
        font-family: monospace;
        font-size: 0.75rem;
        max-height: 220px;
        overflow-y: auto;
        margin-top: 8px;
        border: 1px solid #22222c;
        text-align: left;
    }
</style>
'''

@app.route('/')
def home():
    u = session.get('u')
    k = kind(u['id']) if u else 'none'
    with db() as c:
        stock = c.execute('SELECT count(*) n FROM inventory WHERE used=0').fetchone()['n']
    
    msgs = session.pop('msgs', [])
    
    html = THEME_CSS + '''
    <div class="container">
        <div class="card">
            <h2><span class="logo">_Avel</span></h2>
            {% if u %}
                <p>Discord: <b>{{u['username']}}</b></p>
                <p>ロール: <span class="badge">{{k}}</span></p>
                <a href="/logout" class="btn btn-secondary" style="margin-top:10px;">ログアウト</a>
            {% else %}
                <a href="/login" class="btn">Discordでログイン</a>
            {% endif %}
        </div>
        
        {% for m in msgs %}
            <div class="err">{{m}}</div>
        {% endfor %}
        
        <div class="card">
            <h2>{{product}}</h2>
            <p>現在の在庫数: <b style="color:#fff;">{{stock}} 個</b></p>
            {% if u %}
                <form method=post action="/claim">
                    <button type=submit>アカウントを生成</button>
                </form>
            {% else %}
                <p style="font-size:0.85rem; margin-top:10px;">※受け取るにはログインが必要です。</p>
            {% endif %}
        </div>
    </div>
    '''
    return render_template_string(html, u=u, k=k, stock=stock, product=PRODUCT, msgs=msgs)

@app.route('/login')
def login():
    if not CID or not REDIRECT: abort(500, 'Discord OAuth2 settings are missing')
    state = oauth_state.dumps({'nonce': secrets.token_urlsafe(24)})
    from urllib.parse import urlencode
    return redirect('https://discord.com/oauth2/authorize?' + urlencode({'client_id': CID, 'redirect_uri': REDIRECT, 'response_type': 'code', 'scope': 'identify', 'state': state}))

@app.route('/oauth/callback')
def callback():
    state = request.args.get('state', '')
    code = request.args.get('code', '')
    if not state or not code:
        return 'Discord OAuth認証に必要な情報がありません。', 400

    try:
        oauth_state.loads(state, max_age=600)
    except (SignatureExpired, BadSignature):
        return '認証が期限切れです。やり直してください。', 400

    r = requests.post('https://discord.com/api/v10/oauth2/token', data={'client_id': CID, 'client_secret': SECRET, 'grant_type': 'authorization_code', 'code': code, 'redirect_uri': REDIRECT}, timeout=10)
    r.raise_for_status()
    t = r.json()['access_token']
    r = requests.get('https://discord.com/api/v10/users/@me', headers={'Authorization': f'Bearer {t}'}, timeout=10)
    r.raise_for_status()
    session['u'] = r.json()
    return redirect('/')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/claim', methods=['POST'])
def claim():
    u = session.get('u')
    if not u: return redirect('/login')
    k = kind(u['id'])
    with db() as c:
        n = c.execute('SELECT count(*) n FROM claims WHERE discord_id=?', (u['id'],)).fetchone()['n']
        if k == 'free' and n >= 1:
            session['msgs'] = ['無料ロールは1回までです。']
            return redirect('/')
        if k == 'none':
            session['msgs'] = ['対象ロールがありません。']
            return redirect('/')
        
        row = c.execute('SELECT id,url FROM inventory WHERE used=0 ORDER BY id LIMIT 1').fetchone()
        if not row:
            session['msgs'] = ['現在有効な在庫がありません。']
            return redirect('/')
        
        target_url = row['url']
        c.execute('UPDATE inventory SET used=1, used_by=? WHERE id=? AND used=0', (u['id'], row['id']))
        c.execute('INSERT INTO claims(discord_id, url) VALUES(?, ?)', (u['id'], target_url))

    html = THEME_CSS + '''
    <div class="container">
        <div class="card" style="text-align:center;">
            <h2 style="color:#4cd137;">✨ 受け取り完了</h2>
            <p>アカウントの生成に成功しました。</p>
            <div class="link-box" id="targetLink">{{target_url}}</div>
            <button type="button" class="btn" onclick="copyLink()" style="margin-top:16px;">情報をコピーする</button>
            <a href="/" class="btn btn-secondary">ホームへ戻る</a>
        </div>
    </div>
    <script>
    function copyLink() {
        const text = document.getElementById('targetLink').innerText;
        navigator.clipboard.writeText(text).then(() => {
            alert('情報をコピーしました！');
        }).catch(err => {
            console.error('コピーに失敗しました', err);
        });
    }
    </script>
    '''
    return render_template_string(html, target_url=target_url)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not ADMIN or request.args.get('key') != ADMIN: abort(403)
    if request.method == 'POST':
        raw_text = request.form.get('urls', '')
        
        uploaded_files = request.files.getlist('file')
        for uploaded_file in uploaded_files:
            if uploaded_file and uploaded_file.filename:
                raw_text += "\n" + uploaded_file.read().decode('utf-8', errors='ignore')

        with db() as c:
            # NETFLIX ACCOUNT DETAILS や空行、区切り線でアカウントごとに分割
            blocks = re.split(r'(?=NETFLIX ACCOUNT DETAILS)|\n\s*\n|={3,}|-{3,}', raw_text)
            
            found_links = []
            for block in blocks:
                block = block.strip()
                if not block:
                    continue
                
                link = None
                
                # 1. 既に https://netflix.com/unsupported?nftoken=... の形式になっている場合
                m_url = re.search(r'https?://[^\s]+\?nftoken=([A-Za-z0-9\-_%+=/]+)', block)
                if m_url:
                    token = urllib.parse.unquote(m_url.group(1))
                    link = f"https://netflix.com/unsupported?nftoken={token}"
                
                # 2. nftoken=... または nftoken%3D... が直接含まれている場合
                if not link:
                    m_nft = re.search(r'nftoken[=,%3D]([A-Za-z0-9\-_%+=/]+)', block, re.IGNORECASE)
                    if m_nft:
                        token = urllib.parse.unquote(m_nft.group(1))
                        link = f"https://netflix.com/unsupported?nftoken={token}"
                
                # 3. Deadflix等の生クッキー形式 (.netflix.com ... NetflixId ...) から自動抽出・ログインリンク化
                if not link and ('NetflixId' in block or '.netflix.com' in block):
                    decoded_block = urllib.parse.unquote(block)
                    # NetflixId 内の ct= または ct%3D のトークン部分を抽出
                    m_ct = re.search(r'ct[=:]\s*([A-Za-z0-9\-_%+=/]+)', decoded_block)
                    if m_ct:
                        token = m_ct.group(1).strip()
                        link = f"https://netflix.com/unsupported?nftoken={token}"
                    else:
                        m_nid = re.search(r'NetflixId\s+([^\s]+)', decoded_block)
                        if m_nid:
                            token = m_nid.group(1).strip()
                            if 'ct=' in token:
                                token = token.split('ct=')[-1].split('&')[0]
                            link = f"https://netflix.com/unsupported?nftoken={token}"

                # 4. フォールバック (万が一上記に当てはまらない場合でもテキストがあれば保持)
                if not link and len(block) > 10:
                    link = block

                if link and link not in found_links:
                    found_links.append(link)

            # 抽出できたログインリンクをDBに追加
            for link in found_links:
                try:
                    c.execute('INSERT INTO inventory(url) VALUES(?)', (link,))
                except sqlite3.IntegrityError:
                    pass
                            
        return redirect('/admin?key=' + ADMIN)
        
    with db() as c:
        rows = c.execute('SELECT id,url,used FROM inventory ORDER BY id DESC').fetchall()
    
    rows_html = ""
    for r in rows:
        status_badge = "<span style='color:#e50914;'>使用済み</span>" if r['used'] else "<span style='color:#4cd137;'>未使用</span>"
        rows_html += f"<div style='background:#0b0b0e; padding:10px; border-radius:8px; margin-bottom:10px;'><p style='font-size:0.75rem; word-break:break-all; margin:0;'><b>ID: {r['id']}</b> | {status_badge}<br><br>{r['url']}</p></div><hr>"

    html = THEME_CSS + f'''
    <div class="container">
        <div class="card">
            <h2>🛠️ 在庫管理</h2>
            <form method=post enctype=multipart/form-data>
                <label style="font-size:0.85rem; color:#9ba1a6;">チェッカー出力を貼り付け (自動でログインリンクへ変換されます):</label>
                <textarea name=urls rows=8 placeholder="ここにチェッカー結果を貼り付け..."></textarea>
                <label style="font-size:0.85rem; color:#9ba1a6; display:block; margin-top:10px;">またはファイルを選択 (複数選択可):</label>
                <input type=file name=file multiple>
                <button type=submit style="margin-top:16px;">在庫を追加する</button>
            </form>
        </div>
        <div class="card">
            <h2>📦 登録済み在庫一覧</h2>
            {rows_html if rows_html else "<p>在庫はありません。</p>"}
        </div>
    </div>
    '''
    return render_template_string(html)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '26236')))
