from flask import Flask, request, jsonify, render_template_string, redirect, url_for, flash
from flask_cors import CORS
import json
import os
import uuid
import datetime

app = Flask(__name__)
app.secret_key = 'fixmate_secret_2024'
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database.json')
BOOKINGS_PATH = os.path.join(BASE_DIR, 'bookings.json')

def load_data(path, default):
    if not os.path.exists(path): return default
    with open(path, 'r') as f:
        try: return json.load(f)
        except: return default

def save_data(path, data):
    with open(path, 'w') as f: json.dump(data, f, indent=4)

# ── API ENDPOINTS ──────────────────────────────────────────────────────────────

@app.route('/api/workers', methods=['GET'])
def get_workers():
    return jsonify(load_data(DB_PATH, {}))

@app.route('/api/book', methods=['POST'])
def create_booking():
    data = request.json
    if not data: return jsonify({"error": "No data"}), 400
    bookings = load_data(BOOKINGS_PATH, [])
    new_booking = {
        "id": "BK-" + str(uuid.uuid4())[:6].upper(),
        "date_created": datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p"),
        "customer_name": data.get('customer_name', 'Unknown'),
        "customer_phone": data.get('customer_phone', 'Unknown'),
        "customer_address": data.get('customer_address', 'Unknown'),
        "lat": data.get('lat'),
        "lng": data.get('lng'),
        "worker_name": data.get('worker_name', 'Unknown'),
        "service": data.get('service', 'Unknown'),
        "date": data.get('date', ''),
        "time": data.get('time', ''),
        "note": data.get('note', ''),
        "status": "Pending"
    }
    bookings.insert(0, new_booking)
    save_data(BOOKINGS_PATH, bookings)
    return jsonify({"success": True, "booking_id": new_booking["id"]})

@app.route('/api/bookings', methods=['GET'])
def get_bookings():
    return jsonify(load_data(BOOKINGS_PATH, []))

@app.route('/api/bookings/count', methods=['GET'])
def get_booking_count():
    bookings = load_data(BOOKINGS_PATH, [])
    pending = sum(1 for b in bookings if b.get('status') == 'Pending')
    return jsonify({"total": len(bookings), "pending": pending})

# ── ADMIN DASHBOARD ────────────────────────────────────────────────────────────

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    data = load_data(DB_PATH, {})
    bookings = load_data(BOOKINGS_PATH, [])

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_booking_status':
            bid = request.form.get('booking_id')
            new_status = request.form.get('status')
            for b in bookings:
                if b['id'] == bid:
                    b['status'] = new_status
                    break
            save_data(BOOKINGS_PATH, bookings)
            flash(f"✅ Booking {bid} updated to {new_status}!", "success")

        elif action == 'delete_booking':
            bid = request.form.get('booking_id')
            bookings = [b for b in bookings if b['id'] != bid]
            save_data(BOOKINGS_PATH, bookings)
            flash("🗑️ Booking deleted!", "success")

        elif action == 'edit':
            service = request.form.get('service')
            worker_id = request.form.get('worker_id')
            for w in data.get(service, []):
                if w['id'] == worker_id:
                    new_name = request.form.get('name', '')
                    w['name'] = new_name
                    w['initials'] = new_name[:2].upper() if new_name else '??'
                    w['phone'] = request.form.get('phone', '')
                    loc = request.form.get('location', '').strip()
                    if loc: w['location'] = loc
                    w['isOnline'] = request.form.get('is_online') == 'on'
                    break
            save_data(DB_PATH, data)
            flash(f"✅ Worker updated! Phone app will refresh automatically.", "success")

        elif action == 'add':
            service = request.form.get('service')
            name = request.form.get('name', 'Worker')
            colors = [4294286859, 4293858372, 4279318913, 4287319286, 4282086134, 4285354991, 4278638292, 4294542102]
            import random
            new_worker = {
                "id": str(uuid.uuid4())[:6],
                "name": name,
                "serviceType": service.capitalize(),
                "phone": request.form.get('phone', ''),
                "location": request.form.get('location', 'Local'),
                "rating": float(request.form.get('rating', 4.5)),
                "reviewCount": 1,
                "isOnline": request.form.get('is_online') == 'on',
                "distanceKm": float(request.form.get('distance', 1.0)),
                "experience": request.form.get('experience', '1 year'),
                "jobsDone": 0,
                "avatarColorValue": random.choice(colors),
                "initials": name[:2].upper()
            }
            if service not in data: data[service] = []
            data[service].append(new_worker)
            save_data(DB_PATH, data)
            flash(f"✅ New {service} worker '{name}' added! Visible in phone app instantly.", "success")

        elif action == 'delete':
            service = request.form.get('service')
            worker_id = request.form.get('worker_id')
            data[service] = [w for w in data.get(service, []) if w['id'] != worker_id]
            save_data(DB_PATH, data)
            flash("🗑️ Worker deleted!", "success")

        return redirect(url_for('admin'))

    pending_count = sum(1 for b in bookings if b.get('status') == 'Pending')
    total_workers = sum(len(v) for v in data.values())
    return render_template_string(HTML_TEMPLATE, data=data, bookings=bookings,
                                   pending_count=pending_count, total_workers=total_workers)

# ── HTML TEMPLATE ──────────────────────────────────────────────────────────────

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>FixMate Admin Pro</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Poppins', sans-serif; background: #0F0E17; color: #E8E8F0; min-height: 100vh; }

        /* ── TOP BAR ── */
        .topbar {
            background: linear-gradient(135deg, #6C63FF, #3A3080);
            padding: 16px 30px;
            display: flex;
            align-items: center;
            gap: 16px;
            box-shadow: 0 4px 20px rgba(108,99,255,0.4);
            position: sticky; top: 0; z-index: 100;
        }
        .topbar h1 { font-size: 22px; font-weight: 800; color: white; flex: 1; }
        .topbar .live-badge {
            background: #10B981; color: white; padding: 4px 14px;
            border-radius: 20px; font-size: 12px; font-weight: 600;
            display: flex; align-items: center; gap: 6px;
            animation: pulse 2s infinite;
        }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.6} }

        /* ── STATS BAR ── */
        .stats-bar {
            display: flex; gap: 16px; padding: 20px 30px;
            flex-wrap: wrap;
        }
        .stat-card {
            background: #1C1B2E; border: 1px solid #2D2B50;
            border-radius: 14px; padding: 16px 24px;
            flex: 1; min-width: 140px; text-align: center;
            transition: transform 0.2s;
        }
        .stat-card:hover { transform: translateY(-3px); }
        .stat-card .val { font-size: 32px; font-weight: 800; color: #6C63FF; }
        .stat-card .lbl { font-size: 12px; color: #888; margin-top: 2px; }
        .stat-card.pending .val { color: #F59E0B; }
        .stat-card.online .val { color: #10B981; }

        /* ── LAYOUT ── */
        .main { display: grid; grid-template-columns: 1fr 1.2fr; gap: 20px; padding: 0 30px 30px; }
        @media (max-width: 900px) { .main { grid-template-columns: 1fr; } }

        /* ── PANELS ── */
        .panel { background: #1C1B2E; border: 1px solid #2D2B50; border-radius: 20px; overflow: hidden; }
        .panel-header {
            padding: 20px 24px 16px;
            border-bottom: 1px solid #2D2B50;
            display: flex; align-items: center; gap: 10px;
        }
        .panel-header h2 { font-size: 16px; font-weight: 700; flex: 1; }
        .panel-body { padding: 20px 24px; max-height: 80vh; overflow-y: auto; }
        .panel-body::-webkit-scrollbar { width: 4px; }
        .panel-body::-webkit-scrollbar-thumb { background: #3D3B60; border-radius: 4px; }

        /* ── FLASH MESSAGES ── */
        .flash { background: #0D2E1F; border: 1px solid #10B981; color: #10B981;
                 padding: 12px 20px; margin: 16px 30px; border-radius: 10px; font-size: 13px; font-weight: 600; }

        /* ── BOOKING CARDS ── */
        .booking-card {
            background: #13122A; border-radius: 14px; padding: 16px;
            margin-bottom: 14px; border-left: 4px solid #6C63FF;
            transition: transform 0.2s;
        }
        .booking-card:hover { transform: translateX(4px); }
        .booking-card.Pending { border-left-color: #F59E0B; }
        .booking-card.Accepted { border-left-color: #10B981; }
        .booking-card.Rejected { border-left-color: #EF4444; }
        .booking-top { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
        .booking-top .cname { font-size: 15px; font-weight: 700; flex: 1; }
        .badge { padding: 3px 12px; border-radius: 20px; font-size: 11px; font-weight: 700; }
        .badge.Pending { background: #F59E0B22; color: #F59E0B; border: 1px solid #F59E0B44; }
        .badge.Accepted { background: #10B98122; color: #10B981; border: 1px solid #10B98144; }
        .badge.Rejected { background: #EF444422; color: #EF4444; border: 1px solid #EF444444; }
        .booking-info { font-size: 12px; color: #9991CC; line-height: 1.8; }
        .booking-info span { color: #C8C3FF; font-weight: 500; }
        .booking-actions { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
        .btn-map {
            background: linear-gradient(135deg, #3B82F6, #1D4ED8);
            color: white; padding: 8px 16px; border-radius: 8px;
            text-decoration: none; font-size: 12px; font-weight: 600;
            display: inline-flex; align-items: center; gap: 6px;
            border: none; cursor: pointer; transition: opacity 0.2s;
        }
        .btn-map:hover { opacity: 0.85; }
        .btn-accept { background: #10B981; color: white; padding: 6px 14px; border-radius: 8px; font-size: 11px; font-weight: 700; border: none; cursor: pointer; }
        .btn-reject { background: #EF4444; color: white; padding: 6px 14px; border-radius: 8px; font-size: 11px; font-weight: 700; border: none; cursor: pointer; }
        .btn-del-sm { background: #2D1B1B; color: #EF4444; padding: 6px 14px; border-radius: 8px; font-size: 11px; font-weight: 700; border: 1px solid #EF444444; cursor: pointer; }

        /* ── SERVICE SECTIONS ── */
        .service-header {
            display: flex; align-items: center; gap: 10px;
            background: linear-gradient(135deg, #6C63FF22, #6C63FF11);
            border: 1px solid #6C63FF44; border-radius: 10px;
            padding: 10px 16px; margin: 14px 0 10px; cursor: pointer;
        }
        .service-header h3 { font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; flex: 1; color: #A199FF; }
        .service-header .count { background: #6C63FF; color: white; padding: 2px 10px; border-radius: 10px; font-size: 11px; font-weight: 700; }

        /* ── WORKER CARDS ── */
        .worker-card {
            background: #13122A; border: 1px solid #2D2B50; border-radius: 12px;
            padding: 14px; margin-bottom: 10px;
        }
        .worker-meta { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
        .worker-avatar {
            width: 42px; height: 42px; border-radius: 50%;
            background: linear-gradient(135deg, #6C63FF, #3A3080);
            display: flex; align-items: center; justify-content: center;
            font-weight: 800; font-size: 15px; color: white; flex-shrink: 0;
        }
        .worker-info { flex: 1; }
        .worker-info .wname { font-size: 14px; font-weight: 700; }
        .worker-info .wphone { font-size: 11px; color: #888; }
        .online-dot { width: 10px; height: 10px; border-radius: 50%; }
        .online-dot.on { background: #10B981; box-shadow: 0 0 6px #10B981; }
        .online-dot.off { background: #666; }

        /* ── FORM INPUTS ── */
        .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
        input[type="text"], input[type="number"], select, textarea {
            background: #0F0E17; border: 1px solid #3D3B60; color: #E8E8F0;
            border-radius: 8px; padding: 8px 12px; width: 100%; font-family: 'Poppins', sans-serif;
            font-size: 12px; outline: none; transition: border 0.2s;
        }
        input:focus, select:focus, textarea:focus { border-color: #6C63FF; }
        select option { background: #1C1B2E; }
        label.check { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #A199FF; cursor: pointer; margin: 6px 0; }
        input[type="checkbox"] { width: auto; accent-color: #6C63FF; width: 16px; height: 16px; }

        /* ── BUTTONS ── */
        .btn { border: none; border-radius: 8px; cursor: pointer; font-family: 'Poppins', sans-serif; font-weight: 600; transition: all 0.2s; }
        .btn-primary { background: linear-gradient(135deg, #6C63FF, #4F46E5); color: white; padding: 9px 16px; font-size: 12px; width: 100%; margin-top: 8px; }
        .btn-primary:hover { opacity: 0.9; transform: translateY(-1px); }
        .btn-danger { background: #2D1B1B; color: #EF4444; border: 1px solid #EF444444; padding: 7px 14px; font-size: 11px; margin-top: 8px; width: 100%; }
        .btn-danger:hover { background: #EF4444; color: white; }
        .btn-green { background: linear-gradient(135deg, #10B981, #059669); color: white; padding: 9px 16px; font-size: 12px; width: 100%; margin-top: 8px; }

        /* ── ADD WORKER MODAL ── */
        .add-section {
            background: linear-gradient(135deg, #1C1B3A, #13122A);
            border: 2px dashed #6C63FF66; border-radius: 14px;
            padding: 20px; margin-bottom: 20px;
        }
        .add-section h3 { font-size: 15px; font-weight: 700; color: #A199FF; margin-bottom: 14px; }

        /* ── REFRESH COUNTDOWN ── */
        .refresh-bar {
            background: #13122A; border-top: 1px solid #2D2B50;
            text-align: center; padding: 8px; font-size: 11px; color: #666;
        }
        #countdown { color: #6C63FF; font-weight: 700; }
    </style>
</head>
<body>

<!-- TOP BAR -->
<div class="topbar">
    <div>
        <span style="font-size:26px;">🔧</span>
    </div>
    <h1>FixMate Business Control</h1>
    <div class="live-badge">🔴 LIVE</div>
    <div style="font-size:12px; color:rgba(255,255,255,0.6);">Auto-refresh: <span id="countdown">15</span>s</div>
</div>

<!-- FLASH MESSAGES -->
{% with messages = get_flashed_messages(with_categories=true) %}
  {% if messages %}{% for cat, msg in messages %}
  <div class="flash">{{ msg }}</div>
  {% endfor %}{% endif %}
{% endwith %}

<!-- STATS -->
<div class="stats-bar">
    <div class="stat-card pending">
        <div class="val">{{ pending_count }}</div>
        <div class="lbl">⏳ Pending Bookings</div>
    </div>
    <div class="stat-card">
        <div class="val">{{ bookings|length }}</div>
        <div class="lbl">📋 Total Bookings</div>
    </div>
    <div class="stat-card online">
        <div class="val">{{ total_workers }}</div>
        <div class="lbl">👷 Total Workers</div>
    </div>
    <div class="stat-card">
        <div class="val" style="color:#F59E0B;">{{ data|length }}</div>
        <div class="lbl">🛠️ Service Types</div>
    </div>
</div>

<!-- MAIN GRID -->
<div class="main">

    <!-- ── LEFT: LIVE BOOKINGS ── -->
    <div class="panel">
        <div class="panel-header">
            <h2>🚨 Live Bookings</h2>
            {% if pending_count > 0 %}
            <span class="badge Pending">{{ pending_count }} NEW</span>
            {% endif %}
        </div>
        <div class="panel-body">
            {% if bookings %}
            {% for b in bookings %}
            <div class="booking-card {{ b.status }}">
                <div class="booking-top">
                    <div class="cname">👤 {{ b.customer_name }}</div>
                    <span class="badge {{ b.status }}">{{ b.status }}</span>
                </div>
                <div class="booking-info">
                    📞 <span>{{ b.customer_phone }}</span><br>
                    📍 <span>{{ b.customer_address }}</span><br>
                    🛠️ <span>{{ b.worker_name }}</span> — {{ b.service }}<br>
                    🗓️ <span>{{ b.date }}</span> @ <span>{{ b.time }}</span><br>
                    🕐 <span>{{ b.date_created }}</span>
                    {% if b.note %}<br>📝 {{ b.note }}{% endif %}
                </div>
                <div class="booking-actions">
                    {% if b.lat %}
                    <a href="https://www.google.com/maps/dir/?api=1&destination={{ b.lat }},{{ b.lng }}" 
                       target="_blank" class="btn-map">🗺️ Open Route Map</a>
                    {% endif %}
                    <form method="POST" action="/admin" style="display:inline;">
                        <input type="hidden" name="action" value="update_booking_status">
                        <input type="hidden" name="booking_id" value="{{ b.id }}">
                        <input type="hidden" name="status" value="Accepted">
                        <button type="submit" class="btn-accept">✅ Accept</button>
                    </form>
                    <form method="POST" action="/admin" style="display:inline;">
                        <input type="hidden" name="action" value="update_booking_status">
                        <input type="hidden" name="booking_id" value="{{ b.id }}">
                        <input type="hidden" name="status" value="Rejected">
                        <button type="submit" class="btn-reject">❌ Reject</button>
                    </form>
                    <form method="POST" action="/admin" style="display:inline;">
                        <input type="hidden" name="action" value="delete_booking">
                        <input type="hidden" name="booking_id" value="{{ b.id }}">
                        <button type="submit" class="btn-del-sm" onclick="return confirm('Delete this booking?')">🗑️</button>
                    </form>
                </div>
            </div>
            {% endfor %}
            {% else %}
            <div style="text-align:center; padding:40px; color:#555;">
                <div style="font-size:48px;">📭</div>
                <div style="margin-top:12px; font-size:14px;">No bookings yet.<br>Waiting for customers...</div>
            </div>
            {% endif %}
        </div>
        <div class="refresh-bar">🔄 Page auto-refreshes every <span id="countdown2">15</span> seconds</div>
    </div>

    <!-- ── RIGHT: MANAGE WORKERS ── -->
    <div class="panel">
        <div class="panel-header">
            <h2>👷 Manage Workers</h2>
            <span class="badge" style="background:#6C63FF22; color:#A199FF; border:1px solid #6C63FF44;">{{ total_workers }} workers</span>
        </div>
        <div class="panel-body">

            <!-- ADD WORKER FORM -->
            <div class="add-section">
                <h3>➕ Add New Worker</h3>
                <form method="POST" action="/admin">
                    <input type="hidden" name="action" value="add">
                    <div class="form-grid">
                        <select name="service">
                            <option value="electrician">⚡ Electrician</option>
                            <option value="plumber">🔧 Plumber</option>
                            <option value="cleaner">🧹 Cleaner</option>
                            <option value="carpenter">🪚 Carpenter</option>
                            <option value="mechanic">🔩 Mechanic</option>
                            <option value="painter">🎨 Painter</option>
                            <option value="medical">🏥 Medical</option>
                            <option value="grocery">🛒 Grocery</option>
                        </select>
                        <input type="text" name="name" placeholder="Full Name *" required>
                        <input type="text" name="phone" placeholder="Phone Number *" required>
                        <input type="text" name="location" placeholder="City / Area">
                        <input type="text" name="experience" placeholder="Experience (e.g. 3 years)">
                        <input type="number" name="distance" placeholder="Distance (km)" step="0.1" value="1.0">
                    </div>
                    <label class="check">
                        <input type="checkbox" name="is_online" checked> 🟢 Set as Online (Available)
                    </label>
                    <button type="submit" class="btn btn-green">➕ Add Worker to App</button>
                </form>
            </div>

            <!-- WORKER LIST BY SERVICE -->
            {% for service, workers in data.items() %}
            <div class="service-header">
                <h3>
                    {% if service == 'electrician' %}⚡
                    {% elif service == 'plumber' %}🔧
                    {% elif service == 'cleaner' %}🧹
                    {% elif service == 'carpenter' %}🪚
                    {% elif service == 'mechanic' %}🔩
                    {% elif service == 'painter' %}🎨
                    {% elif service == 'medical' %}🏥
                    {% elif service == 'grocery' %}🛒
                    {% else %}👷{% endif %}
                    {{ service }}
                </h3>
                <span class="count">{{ workers|length }}</span>
            </div>
            {% for w in workers %}
            <div class="worker-card">
                <div class="worker-meta">
                    <div class="worker-avatar">{{ w.initials }}</div>
                    <div class="worker-info">
                        <div class="wname">{{ w.name }}</div>
                        <div class="wphone">📞 {{ w.phone }} · 📍 {{ w.location }}</div>
                    </div>
                    <div class="online-dot {% if w.isOnline %}on{% else %}off{% endif %}"></div>
                </div>
                <form method="POST" action="/admin">
                    <input type="hidden" name="action" value="edit">
                    <input type="hidden" name="service" value="{{ service }}">
                    <input type="hidden" name="worker_id" value="{{ w.id }}">
                    <div class="form-grid">
                        <input type="text" name="name" value="{{ w.name }}" placeholder="Name">
                        <input type="text" name="phone" value="{{ w.phone }}" placeholder="Phone">
                        <input type="text" name="location" value="{{ w.location or '' }}" placeholder="City">
                        <div></div>
                    </div>
                    <label class="check">
                        <input type="checkbox" name="is_online" {% if w.isOnline %}checked{% endif %}> 🟢 Online / Available
                    </label>
                    <button type="submit" class="btn btn-primary">💾 Save Changes → Updates Phone App</button>
                </form>
                <form method="POST" action="/admin" onsubmit="return confirm('Delete {{ w.name }}?')">
                    <input type="hidden" name="action" value="delete">
                    <input type="hidden" name="service" value="{{ service }}">
                    <input type="hidden" name="worker_id" value="{{ w.id }}">
                    <button type="submit" class="btn btn-danger">🗑️ Remove Worker</button>
                </form>
            </div>
            {% endfor %}
            {% endfor %}

        </div>
    </div>
</div>

<script>
// Auto-refresh countdown
let seconds = 15;
function tick() {
    seconds--;
    document.getElementById('countdown').textContent = seconds;
    document.getElementById('countdown2').textContent = seconds;
    if (seconds <= 0) {
        location.reload();
    } else {
        setTimeout(tick, 1000);
    }
}
setTimeout(tick, 1000);

// Flash message auto-hide
setTimeout(() => {
    const flashes = document.querySelectorAll('.flash');
    flashes.forEach(f => f.style.transition = 'opacity 0.5s', f.style.opacity = '0');
    setTimeout(() => flashes.forEach(f => f.remove()), 600);
}, 4000);
</script>

</body>
</html>
"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
