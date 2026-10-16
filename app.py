import json
import os
import threading
import time
from flask import Flask, jsonify, render_template_string, request, g
from prometheus_client import (
    Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
)

app = Flask(__name__)

# ---------- Метрики ----------
CLICKS       = Counter('student_clicks_total', 'Клики по студенту')
XP_GAINED    = Counter('student_xp_earned_total', 'Всего XP набрано')
XP_CURRENT   = Gauge('student_xp_current', 'Текущий XP на шкале')
LEVEL_GAUGE  = Gauge('student_level_current', 'Текущий уровень (курс)')
LEVELUPS     = Counter('student_levelups_total', 'Достигнуто уровней')
UPGRADES     = Counter('student_upgrades_purchased_total', 'Куплено апгрейдов', ['type'])
AUTO_XP      = Gauge('student_auto_xp_per_sec', 'Пассивный XP в секунду')
VISITS       = Counter('student_page_visits_total', 'Заходы на главную страницу')
REQ_COUNT    = Counter('student_http_requests_total', 'HTTP запросы', ['endpoint'])
REQ_LATENCY  = Histogram('student_request_duration_seconds', 'Латентность', ['endpoint'])

# ---------- Уровни ----------
LEVELS = [
    ('Абитуриент',   '🧑‍🎓',  100),
    ('Первокурсник', '📘',    200),
    ('Второкурсник', '📗',    350),
    ('Третьекурсник','📙',    550),
    ('Бакалавр',     '🎓',    800),
    ('Магистр',      '🧑‍🔬', 1200),
    ('PhD',          '👨‍🏫', 999999),  # финальный
]

# ---------- Состояние ----------
state = {
    'xp': 0.0,
    'level': 0,
    'click_power': 1.0,
    'auto_xp': 0.0,
    'upgrades': {'coffee': 0, 'books': 0, 'notebook': 0},
}

UPGRADES_DEF = {
    'coffee':   {'base_cost': 15, 'mult': 1.6, 'desc': '☕ Кофе — +1 XP/сек'},
    'books':    {'base_cost': 20, 'mult': 1.7, 'desc': '📚 Учебник — +1 к силе клика'},
    'notebook': {'base_cost': 60, 'mult': 1.9, 'desc': '💻 Ноутбук — +3 XP/сек'},
}

def cost_of(kind):
    d = UPGRADES_DEF[kind]
    return int(d['base_cost'] * (d['mult'] ** state['upgrades'][kind]))

def xp_needed_for(level):
    return LEVELS[level][2] if level < len(LEVELS) else 10**9

# ---------- Сохранение состояния (переживает перезапуск контейнера) ----------
STATE_FILE = os.environ.get('STATE_FILE', '/data/state.json')

def load_state():
    try:
        with open(STATE_FILE, encoding='utf-8') as f:
            saved = json.load(f)
        for k in ('xp', 'level', 'click_power', 'auto_xp'):
            if k in saved:
                state[k] = saved[k]
        state['upgrades'].update(saved.get('upgrades', {}))
    except (FileNotFoundError, ValueError, OSError):
        pass

def save_state():
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        tmp = STATE_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(state, f)
        os.replace(tmp, STATE_FILE)
    except OSError:
        pass

# ---------- Тикер пассивного XP ----------
def ticker():
    n = 0
    while True:
        time.sleep(1)
        n += 1
        if n % 5 == 0:
            save_state()
        inc = state['auto_xp']
        if inc > 0:
            add_xp(inc)
        XP_CURRENT.set(state['xp'])
        LEVEL_GAUGE.set(state['level'])

def add_xp(amount):
    state['xp'] += amount
    XP_GAINED.inc(amount)
    # проверка level-up (может перескочить несколько уровней)
    while state['level'] < len(LEVELS) - 1 and state['xp'] >= xp_needed_for(state['level']):
        state['xp'] -= xp_needed_for(state['level'])
        state['level'] += 1
        LEVELUPS.inc()
        LEVEL_GAUGE.set(state['level'])
        XP_CURRENT.set(state['xp'])
    XP_CURRENT.set(state['xp'])

load_state()
threading.Thread(target=ticker, daemon=True).start()
LEVEL_GAUGE.set(state['level'])
AUTO_XP.set(state['auto_xp'])
XP_CURRENT.set(state['xp'])

# ---------- Middleware ----------
@app.before_request
def _t0():
    g.t0 = time.time()

@app.after_request
def _rec(resp):
    ep = request.endpoint or 'unknown'
    if ep in ('metrics', 'health'):
        return resp
    REQ_COUNT.labels(endpoint=ep).inc()
    REQ_LATENCY.labels(endpoint=ep).observe(time.time() - g.t0)
    return resp

# ---------- UI ----------
HTML = r"""
<!doctype html>
<html><head><meta charset="utf-8"><title>Student Clicker</title>
<style>
 *{box-sizing:border-box}
 body{font-family:system-ui,sans-serif;background:#0e1117;color:#e6e6e6;
      margin:0;padding:2rem;display:flex;flex-direction:column;align-items:center;min-height:100vh}
 h1{margin:0 0 .5rem;font-weight:600}
 .sub{color:#888;margin-bottom:1.5rem}
 .level{font-size:1.1rem;color:#facc15;margin-bottom:1rem;letter-spacing:.5px}
 .scene{position:relative;width:360px;height:280px;display:flex;
        align-items:center;justify-content:center;cursor:pointer;
        user-select:none;transition:transform .05s}
 .scene:active{transform:scale(.97)}
 .student{font-size:9rem;line-height:1;filter:drop-shadow(0 6px 12px rgba(0,0,0,.5));
          transition:transform .1s}
 .desk{position:absolute;bottom:20px;width:320px;height:14px;background:#3a2f22;
       border-radius:6px;box-shadow:0 4px 0 #241b12}
 .laptop{position:absolute;bottom:32px;font-size:2.6rem;left:50%;
         transform:translateX(-50%) translateY(10px)}
 .bubble{position:absolute;top:0;left:50%;transform:translateX(-50%);
         background:#1a1f2b;padding:.4rem .8rem;border-radius:12px;
         font-size:.85rem;color:#9ca3af;animation:float 2s infinite}
 @keyframes float{0%,100%{transform:translateX(-50%) translateY(0)}
                  50%{transform:translateX(-50%) translateY(-6px)}}

 .bar-wrap{width:100%;max-width:520px;margin-top:1.5rem}
 .bar-label{display:flex;justify-content:space-between;font-size:.85rem;
            color:#9ca3af;margin-bottom:.4rem}
 .bar{width:100%;height:26px;background:#1a1f2b;border-radius:13px;
      overflow:hidden;box-shadow:inset 0 0 0 1px #2a3140}
 .bar-fill{height:100%;width:0;border-radius:13px;
           background:linear-gradient(90deg,#22c55e,#16a34a);
           transition:width .25s ease-out}

 .stats{display:flex;gap:2rem;margin-top:1.5rem;font-size:.85rem;color:#888}
 .stats b{display:block;font-size:1.4rem;color:#4ade80;margin-top:.2rem;text-align:center}

 .shop{margin-top:2rem;display:flex;flex-direction:column;gap:.6rem;width:520px;max-width:100%}
 .item{display:flex;justify-content:space-between;align-items:center;
       background:#1a1f2b;padding:.9rem 1.1rem;border-radius:10px}
 .item small{color:#888}
 .item button{background:#3b82f6;color:#fff;border:none;padding:.55rem 1rem;
              border-radius:8px;cursor:pointer;font-size:.9rem}
 .item button:disabled{background:#333;cursor:not-allowed;opacity:.6}

 .pop{position:absolute;pointer-events:none;color:#4ade80;font-weight:700;
      animation:pop .8s ease-out forwards;font-size:1.2rem}
 @keyframes pop{to{transform:translateY(-60px);opacity:0}}
</style></head>
<body>
 <h1>🎓 Student Clicker</h1>
 <div class="sub">Помоги студенту доучиться до PhD</div>
 <div class="level" id="level">Уровень: 🧑‍🎓 Абитуриент</div>

 <div class="scene" id="scene">
   <div class="bubble" id="bubble">нажми, чтобы помочь учиться</div>
   <div class="student" id="student">🧑‍🎓</div>
   <div class="laptop">💻</div>
   <div class="desk"></div>
 </div>

 <div class="bar-wrap">
   <div class="bar-label">
     <span>Прогресс обучения</span>
     <span id="xp-text">0 / 100 XP</span>
   </div>
   <div class="bar"><div class="bar-fill" id="bar"></div></div>
 </div>

 <div class="stats">
   <div>За клик<b id="power">1</b></div>
   <div>XP/сек<b id="auto">0</b></div>
   <div>Кликов<b id="clicks">0</b></div>
 </div>

 <div class="shop" id="shop"></div>

<script>
let localClicks = 0;

async function api(path, method='GET') {
  const r = await fetch(path, {method});
  return r.json();
}

function popText(text, ev){
  const el = document.createElement('div');
  el.className = 'pop';
  el.innerText = text;
  const rect = document.getElementById('scene').getBoundingClientRect();
  el.style.left = (ev.clientX - rect.left) + 'px';
  el.style.top  = (ev.clientY - rect.top)  + 'px';
  document.getElementById('scene').appendChild(el);
  setTimeout(() => el.remove(), 800);
}

async function render() {
  const s = await api('/state');
  document.getElementById('level').innerText = 'Уровень: ' + s.level_icon + ' ' + s.level_name;
  document.getElementById('student').innerText = s.level_icon;
  document.getElementById('power').innerText = s.click_power;
  document.getElementById('auto').innerText  = s.auto_xp;
  document.getElementById('clicks').innerText = localClicks;

  const pct = Math.min(100, (s.xp / s.xp_needed) * 100);
  document.getElementById('bar').style.width = pct + '%';
  document.getElementById('xp-text').innerText =
    Math.floor(s.xp) + ' / ' + s.xp_needed + ' XP';

  const shop = document.getElementById('shop');
  shop.innerHTML = '';
  for (const [kind, info] of Object.entries(s.upgrades)) {
    const div = document.createElement('div');
    div.className = 'item';
    div.innerHTML = `<div>${info.desc}<br><small>куплено: ${info.owned}</small></div>`;
    const btn = document.createElement('button');
    btn.innerText = `Купить (${info.cost} XP)`;
    btn.disabled = s.xp < info.cost;
    btn.onclick = async (e) => {
      e.stopPropagation();
      const r = await api('/buy/' + kind, 'POST');
      if (r.error) return;
      render();
    };
    div.appendChild(btn);
    shop.appendChild(div);
  }
}

document.getElementById('scene').onclick = async (e) => {
  const s = await api('/click', 'POST');
  localClicks++;
  popText('+' + s.gained, e);
  render();
  document.getElementById('bubble').innerText = s.phrase;
};

render();
setInterval(render, 1500);
</script>
</body></html>
"""

PHRASES = [
    "ещё чуть-чуть!", "о, понял!", "конспектирую…", "не отвлекай!",
    "почти разобрался", "готов к экзамену", "ух ты, инсайт!",
    "ещё страничку", "не сплю, честно",
]

# ---------- Роуты ----------
@app.route('/')
def index():
    VISITS.inc()
    return render_template_string(HTML)

@app.route('/health')
def health():
    return jsonify(status='ok')

@app.route('/state')
def get_state():
    lvl = state['level']
    return jsonify({
        'xp': state['xp'],
        'xp_needed': xp_needed_for(lvl),
        'level': lvl,
        'level_name': LEVELS[lvl][0],
        'level_icon': LEVELS[lvl][1],
        'click_power': state['click_power'],
        'auto_xp': state['auto_xp'],
        'upgrades': {
            k: {
                'owned': state['upgrades'][k],
                'cost':  cost_of(k),
                'desc':  UPGRADES_DEF[k]['desc'],
            } for k in UPGRADES_DEF
        }
    })

@app.route('/click', methods=['POST'])
def do_click():
    gain = state['click_power']
    add_xp(gain)
    CLICKS.inc()
    import random
    return jsonify(gained=gain, phrase=random.choice(PHRASES))

@app.route('/buy/<kind>', methods=['POST'])
def buy(kind):
    if kind not in UPGRADES_DEF:
        return jsonify(error='unknown'), 400
    cost = cost_of(kind)
    if state['xp'] < cost:
        return jsonify(error='not enough xp'), 400

    state['xp'] -= cost
    state['upgrades'][kind] += 1
    UPGRADES.labels(type=kind).inc()

    if kind == 'coffee':
        state['auto_xp'] += 1
    elif kind == 'notebook':
        state['auto_xp'] += 3
    elif kind == 'books':
        state['click_power'] += 1

    AUTO_XP.set(state['auto_xp'])
    XP_CURRENT.set(state['xp'])
    return jsonify(ok=True, cost_next=cost_of(kind))

@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)