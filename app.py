import os, sqlite3, secrets, requests, json, urllib.parse, re, html
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
<meta name="format-detection" content="telephone=no, date=no, email=no, address=no">
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
    details summary {
        cursor: pointer;
        user-select: none;
        outline: none;
    }
</style>
'''

def get_redirect_uri():
    if REDIRECT:
        return REDIRECT
    return request.host_url.rstrip('/') + '/oauth/callback'

@app.route('/')
def home():
    u = session.get('u')
    k = kind(u['id']) if u else 'none'
    with db() as c:
        stock = c.execute('SELECT count(*) n FROM inventory WHERE used=0').fetchone()['n']
    
    msgs = session.pop('msgs', [])
    
    html_content = THEME_CSS + '''
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
    return render_template_string(html_content, u=u, k=k, stock=stock, product=PRODUCT, msgs=msgs)

@app.route('/login')
def login():
    if not CID: abort(500, 'DISCORD_CLIENT_ID が設定されていません。')
    redirect_uri = get_redirect_uri()
    state = oauth_state.dumps({'nonce': secrets.token_urlsafe(24)})
    params = {
        'client_id': CID,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'identify',
        'state': state
    }
    auth_url = 'https://discord.com/oauth2/authorize?' + urllib.parse.urlencode(params)
    return redirect(auth_url)

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

    redirect_uri = get_redirect_uri()
    r = requests.post('https://discord.com/api/v10/oauth2/token', data={'client_id': CID, 'client_secret': SECRET, 'grant_type': 'authorization_code', 'code': code, 'redirect_uri': redirect_uri}, timeout=10)
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
        
        generated_link = None
        
        # --- [修正箇所] トークン抽出ロジックを強化 ---
        # NetflixIdの後に続く値 (クオーテーション、コロン、スペース、= などで区切られたもの) を確実に抽出
        match = re.search(r'NetflixId["\'\s:=]+([^\s;"\']+)', target_url)
        if match:
            val = match.group(1)
            # URLエンコードされている場合（例: ct%3D...）を一度デコードする
            val = urllib.parse.unquote(val)
            # 先頭に付いている「ct=」を取り除き、純粋なトークンにする
            if val.startswith('ct='):
                val = val[3:]
            generated_link = f"https://netflix.com/unsupported?nftoken={val}"
        else:
            generated_link = target_url

        c.execute('UPDATE inventory SET used=1, used_by=? WHERE id=? AND used=0', (u['id'], row['id']))
        c.execute('INSERT INTO claims(discord_id, url) VALUES(?, ?)', (u['id'], generated_link))

    is_link = generated_link.startswith(('http://', 'https://'))

    html_content = THEME_CSS + '''
    <div class="container">
        <div class="card" style="text-align:center;">
            <h2 style="color:#4cd137;">✨ 受け取り完了</h2>
            <p>アカウントの生成に成功しました。</p>
            
            <textarea readonly id="targetLink" style="width:100%; height:140px; resize:vertical; background:#0b0b0e; border:1px solid #22222c; color:#f3f3f5; padding:12px; border-radius:8px; margin-top:8px; word-break:break-all;">{{generated_link}}</textarea>
            
            <button type="button" class="btn" onclick="copyLink()" style="margin-top:16px;">リンクをコピーする</button>
            {% if is_link %}
                <a href="{{generated_link}}" target="_blank" rel="noopener noreferrer" class="btn" style="background:#28a745; margin-top:10px;">ブラウザで開く</a>
            {% endif %}
            <a href="/" class="btn btn-secondary">ホームへ戻る</a>
        </div>
    </div>
    <script>
    function copyLink() {
        const copyText = document.getElementById('targetLink');
        copyText.select();
        copyText.setSelectionRange(0, 99999);
        navigator.clipboard.writeText(copyText.value).then(() => {
            alert('リンクをコピーしました！');
        }).catch(err => {
            console.error('コピーに失敗しました', err);
        });
    }
    </script>
    '''
    return render_template_string(html_content, generated_link=generated_link, is_link=is_link)

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
            clean_text = re.sub(r'[\r\n]*[=]{4,}[\r\n]*|[\r\n]*[-]{4,}[\r\n]*', '\n\n', raw_text)
            blocks = re.split(r'\n\s*\n', clean_text)
            valid_accounts = []
            
            for block in blocks:
                block = re.sub(r'^[\(\)]+|[\(\)]+$', '', block.strip()).strip()
                if not block:
                    continue
                if 'NetflixId' in block or '.netflix.com' in block:
                    valid_accounts.append(block)
            
            if not valid_accounts and ('NetflixId' in raw_text or '.netflix.com' in raw_text):
                valid_accounts = [raw_text.strip()]

            for acc in valid_accounts:
                try:
                    c.execute('INSERT INTO inventory(url) VALUES(?)', (acc,))
                except sqlite3.IntegrityError:
                    pass
                            
        return redirect('/admin?key=' + urllib.parse.quote(ADMIN))
        
    with db() as c:
        rows = c.execute('SELECT id,url,used FROM inventory ORDER BY id DESC').fetchall()
    
    rows_html = ""
    for r in rows:
        status_badge = "<span style='color:#e50914;'>使用済み</span>" if r['used'] else "<span style='color:#4cd137;'>未使用</span>"
        safe_val = html.escape(r['url'])

        rows_html += f'''
        <div style="background: #0b0b0e; border: 1px solid #22222c; padding: 12px; border-radius: 10px; margin-bottom: 10px;">
            <div style="font-size:0.85rem; margin-bottom: 6px;">
                <b>ID: {r['id']}</b> | {status_badge}
            </div>
            <details>
                <summary style="font-size:0.85rem; color:#9ba1a6; outline:none; padding:4px 0;">データ内容を表示</summary>
                <textarea readonly style="width:100%; height:120px; resize:vertical; margin-top:8px; background:#141418; border:1px solid #22222c; color:#f3f3f5; padding:8px; border-radius:8px; font-size:0.75rem;">{safe_val}</textarea>
            </details>
        </div>
        '''

    html_content = THEME_CSS + f'''
    <div class="container">
        <div class="card">
            <h2>🛠️ 在庫管理</h2>
            <form method=post enctype=multipart/form-data>
                <label style="font-size:0.85rem; color:#9ba1a6;">チェッカーの出力を貼り付け:</label>
                <textarea name=urls rows=8 placeholder="ここにチェッカー結果を貼り付け..."></textarea>
                <label style="font-size:0.85rem; color:#9ba1a6; display:block; margin-top:10px;">またはファイルを選択 (複数選択可):</label>
                <input type=file name=file multiple>
                <button type=submit style="margin-top:16px;">在庫を追加する</button>
            </form>
        </div>
        <div class="card">
            <h2>📦 登録済み在庫一覧 ({len(rows)}件)</h2>
            {rows_html if rows_html else "<p>在庫はありません。</p>"}
        </div>
    </div>
    '''
    return render_template_string(html_content)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '26236')))
