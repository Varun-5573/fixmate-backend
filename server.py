from flask import Flask, request, jsonify, render_template_string, redirect, url_for, flash, Response
from flask_cors import CORS
import json, os, uuid, datetime, random, csv, io, threading
try:
    import requests as req_lib
    HAS_REQUESTS = True
except:
    HAS_REQUESTS = False

app = Flask(__name__)
app.secret_key = 'fixmate_secret_2024'
CORS(app)

import sys
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database.json')
BOOKINGS_PATH = os.path.join(BASE_DIR, 'bookings.json')
PROFILE_PATH = os.path.join(BASE_DIR, 'profile.json')
SUPPORT_PATH = os.path.join(BASE_DIR, 'support.json')

# Cloud sync config
CLOUD_URL = 'https://fixmate-backend-68dy.onrender.com'
SYNC_SECRET = 'fm_sync_key_2024'
IS_CLOUD = os.environ.get('RENDER', False)  # True when running on Render

def load_data(path, default):
    if not os.path.exists(path): return default
    with open(path, 'r') as f:
        try: return json.load(f)
        except: return default

def save_data(path, data):
    with open(path, 'w') as f: json.dump(data, f, indent=4)

def push_to_cloud(db_data):
    """Sync local worker changes to cloud in background thread"""
    if IS_CLOUD or not HAS_REQUESTS: return
    try:
        req_lib.post(f'{CLOUD_URL}/api/sync_db',
            json={'data': db_data, 'secret': SYNC_SECRET},
            timeout=10)
        print('Synced workers to cloud!')
    except Exception as e:
        print(f'Cloud sync failed (cloud might be sleeping): {e}')

def save_workers_and_sync(data):
    """Save locally AND push to cloud so phone app gets update"""
    save_data(DB_PATH, data)
    threading.Thread(target=push_to_cloud, args=(data,), daemon=True).start()

def keep_alive_ping():
    """Ping our own Render server every 14 min to prevent sleep"""
    import time
    time.sleep(60)  # Wait for server to fully start
    while True:
        try:
            if HAS_REQUESTS:
                req_lib.get(f'{CLOUD_URL}/health', timeout=15)
                print('💓 Keep-alive ping sent — server stays awake!')
        except Exception as e:
            print(f'Keep-alive ping failed: {e}')
        import time; time.sleep(14 * 60)  # Every 14 minutes

# Start keep-alive ONLY on Render cloud (not local)
if IS_CLOUD:
    threading.Thread(target=keep_alive_ping, daemon=True).start()
    print('Keep-alive thread started - server will NOT sleep!')

# ── API ENDPOINTS ────────────────────────────────────────────────────────────

@app.route('/api/workers', methods=['GET'])
def get_workers():
    return jsonify(load_data(DB_PATH, {}))

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "alive"})

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
        "lat": data.get('lat'), "lng": data.get('lng'),
        "worker_name": data.get('worker_name', 'Unknown'),
        "service": data.get('service', 'Unknown'),
        "date": data.get('date', ''), "time": data.get('time', ''),
        "note": data.get('note', ''), "status": "Pending"
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

@app.route('/api/toggle_worker', methods=['POST'])
def toggle_worker():
    data = request.json
    db = load_data(DB_PATH, {})
    for service, workers in db.items():
        for w in workers:
            if w['id'] == data.get('worker_id'):
                w['isOnline'] = not w.get('isOnline', False)
                save_workers_and_sync(db)
                return jsonify({"success": True, "isOnline": w['isOnline']})
    return jsonify({"error": "Worker not found"}), 404

@app.route('/api/sync_db', methods=['POST'])
def sync_db():
    """Receive synced worker data from local server and save it"""
    req = request.json
    if not req or req.get('secret') != SYNC_SECRET:
        return jsonify({'error': 'Unauthorized'}), 403
    save_data(DB_PATH, req.get('data', {}))
    print('Received sync from local admin')
    return jsonify({'success': True})

@app.route('/api/profile', methods=['GET', 'POST'])
def manage_profile():
    if request.method == 'POST':
        save_data(PROFILE_PATH, request.json)
        return jsonify({"success": True})
    return jsonify(load_data(PROFILE_PATH, {"name": "Village Pro User", "email": "user@villagepro.com", "phone": "+91 9000000000", "location": "Ramagundam, Telangana"}))

@app.route('/api/my_bookings', methods=['GET'])
def my_bookings():
    # In a real app this would filter by user ID, here we return all for demonstration or filter by phone
    phone = request.args.get('phone')
    bookings = load_data(BOOKINGS_PATH, [])
    if phone:
        bookings = [b for b in bookings if b.get('customer_phone') == phone]
    return jsonify(bookings)

@app.route('/api/support', methods=['GET', 'POST'])
def handle_support():
    tickets = load_data(SUPPORT_PATH, [])
    if request.method == 'POST':
        data = request.json
        msg = data.get('message', '').lower().strip()

        # Greetings - no ticket, just reply
        if msg in ["hi", "hello", "hey", "hola", "hi there", "help", "hey there"]:
            return jsonify({"success": True, "reply": "Hello! Welcome to FixMate Support \U0001f44b How can we help you today?"})

        # Smart chatbot replies
        reply = "Your message has been received! Our admin will review it and reply to you here shortly."
        if 'booking' in msg:
            reply = "I see you need help with a booking! Our admin is reviewing this and will reply here shortly."
        elif 'payment' in msg:
            reply = "For payment issues, our admin will contact you within 2 hours to resolve this."
        elif 'worker' in msg:
            reply = "Your worker issue has been escalated to our Admin. They will take action immediately."
        elif 'app' in msg or 'not working' in msg or 'crash' in msg:
            reply = "I have logged a technical issue. Our team will reply here with a fix soon."
        elif 'cancel' in msg:
            reply = "Our admin will confirm the cancellation and any refunds shortly."

        ticket = {
            "id": "TKT-" + str(uuid.uuid4())[:6].upper(),
            "date": datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p"),
            "customer": data.get('customer', 'User'),
            "phone": data.get('phone', ''),
            "message": data.get('message', ''),
            "reply": reply,
            "admin_reply": "",
            "status": "Open"
        }
        tickets.insert(0, ticket)
        save_data(SUPPORT_PATH, tickets)
        return jsonify({"success": True, "reply": reply})
    return jsonify(tickets)

@app.route('/api/admin_reply', methods=['POST'])
def admin_reply_route():
    """Admin sends custom reply to customer - phone polls and displays it"""
    data = request.json
    ticket_id = data.get('ticket_id')
    reply_msg = data.get('reply_msg', '')
    tickets = load_data(SUPPORT_PATH, [])
    for t in tickets:
        if t.get('id') == ticket_id:
            t['admin_reply'] = reply_msg
            t['status'] = 'Replied'
            break
    save_data(SUPPORT_PATH, tickets)
    return jsonify({'success': True})

@app.route('/export/bookings')
def export_bookings():
    bookings = load_data(BOOKINGS_PATH, [])
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID','Date','Customer','Phone','Address','Worker','Service','Booking Date','Time','Status','Note'])
    for b in bookings:
        writer.writerow([b.get('id',''), b.get('date_created',''), b.get('customer_name',''),
                         b.get('customer_phone',''), b.get('customer_address',''),
                         b.get('worker_name',''), b.get('service',''), b.get('date',''),
                         b.get('time',''), b.get('status',''), b.get('note','')])
    output.seek(0)
    return Response(output, mimetype='text/csv',
                    headers={"Content-Disposition": "attachment;filename=fixmate_bookings.csv"})

# ── ADMIN ────────────────────────────────────────────────────────────────────

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
                if b['id'] == bid: b['status'] = new_status; break
            save_data(BOOKINGS_PATH, bookings)
            flash(f"Booking {bid} → {new_status}", "success")
        elif action == 'delete_booking':
            bid = request.form.get('booking_id')
            bookings = [b for b in bookings if b['id'] != bid]
            save_data(BOOKINGS_PATH, bookings)
            flash("Booking deleted", "info")
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
                    exp = request.form.get('experience', '').strip()
                    if exp: w['experience'] = exp
                    w['isOnline'] = request.form.get('is_online') == 'on'
                    break
            save_workers_and_sync(data)
            flash("✅ Worker updated! Syncing to cloud... Phone app will update!", "success")
        elif action == 'add':
            service = request.form.get('service')
            name = request.form.get('name', 'Worker')
            colors = [4294286859, 4293858372, 4279318913, 4287319286, 4282086134, 4285354991, 4278638292, 4294542102]
            new_worker = {
                "id": str(uuid.uuid4())[:6], "name": name,
                "serviceType": service.capitalize(),
                "phone": request.form.get('phone', ''),
                "location": request.form.get('location', 'Local'),
                "rating": float(request.form.get('rating', 4.5)),
                "reviewCount": 1, "isOnline": request.form.get('is_online') == 'on',
                "distanceKm": float(request.form.get('distance', 1.0)),
                "experience": request.form.get('experience', '1 year'),
                "jobsDone": 0, "avatarColorValue": random.choice(colors),
                "initials": name[:2].upper()
            }
            if service not in data: data[service] = []
            data[service].append(new_worker)
            save_workers_and_sync(data)
            flash(f"✅ Worker '{name}' added! Syncing to cloud...", "success")
        elif action == 'delete':
            service = request.form.get('service')
            worker_id = request.form.get('worker_id')
            data[service] = [w for w in data.get(service, []) if w['id'] != worker_id]
            save_workers_and_sync(data)
            flash("🗑️ Worker removed! Syncing to cloud...", "info")
        elif action == 'reply_ticket':
            tid = request.form.get('ticket_id')
            reply_msg = request.form.get('reply_msg')
            tickets = load_data(SUPPORT_PATH, [])
            for t in tickets:
                if t.get('id') == tid:
                    t['reply'] = reply_msg
                    break
            save_data(SUPPORT_PATH, tickets)
            return jsonify({"success": True})
        return redirect(url_for('admin'))

    pending_count = sum(1 for b in bookings if b.get('status') == 'Pending')
    accepted_count = sum(1 for b in bookings if b.get('status') == 'Accepted')
    rejected_count = sum(1 for b in bookings if b.get('status') == 'Rejected')
    total_workers = sum(len(v) for v in data.values())
    online_workers = sum(1 for v in data.values() for w in v if w.get('isOnline'))
    services_count = {s: len(ws) for s, ws in data.items()}
    return render_template_string(HTML_TEMPLATE, data=data, bookings=bookings,
        pending_count=pending_count, accepted_count=accepted_count,
        rejected_count=rejected_count, total_workers=total_workers,
        online_workers=online_workers, services_count=services_count)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FixMate Pro Admin</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
:root{
  --bg:#080B14; --bg2:#0D1117; --card:#111827; --card2:#1a2235;
  --border:#1e2d3d; --purple:#7C3AED; --purple2:#5B21B6; --green:#10B981;
  --yellow:#F59E0B; --red:#EF4444; --blue:#3B82F6; --cyan:#06B6D4;
  --text:#E2E8F0; --muted:#64748B; --white:#fff;
}
body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;overflow-x:hidden;}

/* SIDEBAR */
.sidebar{position:fixed;left:0;top:0;width:220px;height:100vh;background:var(--bg2);border-right:1px solid var(--border);z-index:200;display:flex;flex-direction:column;}
.logo{padding:24px 20px;display:flex;align-items:center;gap:12px;border-bottom:1px solid var(--border);}
.logo-icon{width:40px;height:40px;background:linear-gradient(135deg,var(--purple),var(--purple2));border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:18px;}
.logo-text{font-size:16px;font-weight:800;background:linear-gradient(135deg,#A78BFA,#7C3AED);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.nav{padding:16px 12px;flex:1;}
.nav-item{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:10px;cursor:pointer;margin-bottom:4px;font-size:13px;font-weight:500;color:var(--muted);transition:all 0.2s;text-decoration:none;}
.nav-item:hover,.nav-item.active{background:rgba(124,58,237,0.15);color:var(--purple);box-shadow:inset 0 0 0 1px rgba(124,58,237,0.2);}
.nav-item i{width:18px;text-align:center;}
.nav-badge{margin-left:auto;background:var(--red);color:white;font-size:10px;font-weight:700;padding:2px 7px;border-radius:20px;}
.sidebar-footer{padding:16px;border-top:1px solid var(--border);}
.live-indicator{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--green);}
.live-dot{width:8px;height:8px;background:var(--green);border-radius:50%;animation:pulse 2s infinite;}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1);}50%{opacity:0.5;transform:scale(1.3);}}

/* MAIN */
.main{margin-left:220px;padding:24px;min-height:100vh;}

/* TOPBAR */
.topbar{display:flex;align-items:center;gap:16px;margin-bottom:24px;}
.topbar h1{font-size:22px;font-weight:800;flex:1;}
.topbar h1 span{background:linear-gradient(135deg,#A78BFA,#7C3AED);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.countdown-pill{background:var(--card);border:1px solid var(--border);padding:6px 14px;border-radius:20px;font-size:12px;color:var(--muted);display:flex;align-items:center;gap:6px;}
.countdown-pill span{color:var(--purple);font-weight:700;}
.export-btn{background:linear-gradient(135deg,var(--green),#059669);color:white;padding:8px 16px;border-radius:10px;font-size:12px;font-weight:600;text-decoration:none;display:flex;align-items:center;gap:6px;border:none;cursor:pointer;transition:opacity 0.2s;}
.export-btn:hover{opacity:0.85;}

/* STATS GRID */
.stats{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:24px;}
.stat-card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:18px;position:relative;overflow:hidden;transition:transform 0.2s;}
.stat-card:hover{transform:translateY(-3px);}
.stat-card::before{content:'';position:absolute;top:0;right:0;width:60px;height:60px;border-radius:50%;opacity:0.08;transform:translate(20px,-20px);}
.stat-card.purple::before{background:var(--purple);}
.stat-card.green::before{background:var(--green);}
.stat-card.yellow::before{background:var(--yellow);}
.stat-card.red::before{background:var(--red);}
.stat-card.blue::before{background:var(--blue);}
.stat-icon{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:16px;margin-bottom:12px;}
.stat-card.purple .stat-icon{background:rgba(124,58,237,0.15);color:var(--purple);}
.stat-card.green .stat-icon{background:rgba(16,185,129,0.15);color:var(--green);}
.stat-card.yellow .stat-icon{background:rgba(245,158,11,0.15);color:var(--yellow);}
.stat-card.red .stat-icon{background:rgba(239,68,68,0.15);color:var(--red);}
.stat-card.blue .stat-icon{background:rgba(59,130,246,0.15);color:var(--blue);}
.stat-val{font-size:28px;font-weight:800;line-height:1;}
.stat-label{font-size:11px;color:var(--muted);margin-top:4px;font-weight:500;}

/* GRID LAYOUT */
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;}
.panel{background:var(--card);border:1px solid var(--border);border-radius:20px;overflow:hidden;}
.panel-head{padding:18px 22px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px;}
.panel-head h2{font-size:15px;font-weight:700;flex:1;}
.panel-body{padding:20px 22px;max-height:75vh;overflow-y:auto;}
.panel-body::-webkit-scrollbar{width:3px;}
.panel-body::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px;}

/* SEARCH BAR */
.search-bar{display:flex;gap:8px;margin-bottom:16px;}
.search-bar input{flex:1;background:var(--bg2);border:1px solid var(--border);color:var(--text);border-radius:10px;padding:9px 14px;font-size:13px;font-family:'Inter',sans-serif;outline:none;transition:border 0.2s;}
.search-bar input:focus{border-color:var(--purple);}
.filter-btn{background:var(--bg2);border:1px solid var(--border);color:var(--muted);border-radius:10px;padding:9px 14px;font-size:12px;cursor:pointer;font-family:'Inter',sans-serif;transition:all 0.2s;}
.filter-btn.active,.filter-btn:hover{border-color:var(--purple);color:var(--purple);}

/* BOOKING CARDS */
.booking-card{background:var(--card2);border-radius:14px;padding:16px;margin-bottom:12px;border-left:3px solid var(--border);transition:all 0.2s;position:relative;}
.booking-card:hover{transform:translateX(4px);}
.booking-card.Pending{border-left-color:var(--yellow);}
.booking-card.Accepted{border-left-color:var(--green);}
.booking-card.Rejected{border-left-color:var(--red);}
.booking-card.new-booking{animation:newBooking 1s ease-out;}
@keyframes newBooking{0%{background:#1a2e1a;box-shadow:0 0 20px rgba(16,185,129,0.3);}100%{background:var(--card2);}}
.bc-top{display:flex;align-items:center;gap:10px;margin-bottom:10px;}
.bc-avatar{width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,var(--purple),var(--blue));display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;color:white;flex-shrink:0;}
.bc-name{font-size:14px;font-weight:700;flex:1;}
.bc-time{font-size:10px;color:var(--muted);}
.badge{padding:3px 10px;border-radius:20px;font-size:10px;font-weight:700;}
.badge.Pending{background:rgba(245,158,11,0.15);color:var(--yellow);border:1px solid rgba(245,158,11,0.3);}
.badge.Accepted{background:rgba(16,185,129,0.15);color:var(--green);border:1px solid rgba(16,185,129,0.3);}
.badge.Rejected{background:rgba(239,68,68,0.15);color:var(--red);border:1px solid rgba(239,68,68,0.3);}
.bc-info{font-size:12px;color:var(--muted);line-height:1.9;}
.bc-info .val{color:var(--text);font-weight:500;}
.bc-actions{display:flex;gap:6px;margin-top:12px;flex-wrap:wrap;}
.btn{border:none;border-radius:8px;padding:7px 13px;font-size:11px;font-weight:600;cursor:pointer;font-family:'Inter',sans-serif;transition:all 0.15s;display:flex;align-items:center;gap:5px;}
.btn:hover{opacity:0.85;transform:translateY(-1px);}
.btn-accept{background:rgba(16,185,129,0.15);color:var(--green);border:1px solid rgba(16,185,129,0.3);}
.btn-reject{background:rgba(239,68,68,0.15);color:var(--red);border:1px solid rgba(239,68,68,0.3);}
.btn-map{background:rgba(59,130,246,0.15);color:var(--blue);border:1px solid rgba(59,130,246,0.3);text-decoration:none;}
.btn-del{background:rgba(239,68,68,0.08);color:var(--red);border:1px solid rgba(239,68,68,0.2);}
.btn-call{background:rgba(16,185,129,0.08);color:var(--green);border:1px solid rgba(16,185,129,0.2);text-decoration:none;}
.btn-whatsapp{background:rgba(37,211,102,0.1);color:#25D366;border:1px solid rgba(37,211,102,0.3);text-decoration:none;}

/* ADD WORKER */
.add-form{background:linear-gradient(135deg,rgba(124,58,237,0.1),rgba(91,33,182,0.05));border:1px dashed rgba(124,58,237,0.4);border-radius:16px;padding:20px;margin-bottom:20px;}
.add-form h3{font-size:14px;font-weight:700;color:#A78BFA;margin-bottom:14px;display:flex;align-items:center;gap:8px;}
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;}
.form-grid.three{grid-template-columns:1fr 1fr 1fr;}
input[type="text"],input[type="number"],select,textarea{background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:8px;padding:9px 12px;width:100%;font-family:'Inter',sans-serif;font-size:12px;outline:none;transition:border 0.2s;}
input:focus,select:focus{border-color:var(--purple);}
select option{background:var(--card);}
label.check{display:flex;align-items:center;gap:8px;font-size:12px;color:#A78BFA;cursor:pointer;margin:8px 0;}
input[type="checkbox"]{width:auto;accent-color:var(--purple);}
.btn-primary{background:linear-gradient(135deg,var(--purple),var(--purple2));color:white;padding:10px;border-radius:8px;width:100%;font-size:12px;font-weight:600;border:none;cursor:pointer;font-family:'Inter',sans-serif;transition:opacity 0.2s;}
.btn-primary:hover{opacity:0.85;}

/* SERVICE SECTION */
.service-sect{margin-bottom:8px;}
.service-toggle{display:flex;align-items:center;gap:10px;padding:12px 14px;background:rgba(124,58,237,0.08);border:1px solid rgba(124,58,237,0.2);border-radius:12px;cursor:pointer;margin-bottom:8px;transition:background 0.2s;}
.service-toggle:hover{background:rgba(124,58,237,0.15);}
.service-toggle h3{font-size:12px;font-weight:700;color:#A78BFA;text-transform:uppercase;letter-spacing:1px;flex:1;}
.service-count{background:var(--purple);color:white;font-size:10px;font-weight:700;padding:2px 8px;border-radius:10px;}
.service-workers{display:none;}
.service-workers.open{display:block;}

/* WORKER CARDS */
.worker-card{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:14px;margin-bottom:8px;transition:all 0.2s;}
.worker-card:hover{border-color:rgba(124,58,237,0.3);}
.wc-top{display:flex;align-items:center;gap:10px;margin-bottom:12px;}
.wc-avatar{width:42px;height:42px;border-radius:12px;background:linear-gradient(135deg,var(--purple),var(--blue));display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:800;color:white;flex-shrink:0;}
.wc-info{flex:1;}
.wc-name{font-size:14px;font-weight:700;}
.wc-sub{font-size:11px;color:var(--muted);margin-top:2px;}
.toggle-wrap{display:flex;align-items:center;gap:8px;}
.toggle-label{font-size:11px;color:var(--muted);}
.toggle{position:relative;width:40px;height:22px;cursor:pointer;}
.toggle input{opacity:0;width:0;height:0;}
.slider{position:absolute;inset:0;background:#2D3748;border-radius:22px;transition:0.2s;}
.slider:before{content:'';position:absolute;width:16px;height:16px;left:3px;bottom:3px;background:white;border-radius:50%;transition:0.2s;}
input:checked+.slider{background:var(--green);}
input:checked+.slider:before{transform:translateX(18px);}
.wc-actions{display:flex;gap:6px;}
.btn-save{background:linear-gradient(135deg,var(--purple),var(--purple2));color:white;padding:7px 14px;border-radius:8px;font-size:11px;font-weight:600;border:none;cursor:pointer;font-family:'Inter',sans-serif;}
.btn-remove{background:rgba(239,68,68,0.1);color:var(--red);border:1px solid rgba(239,68,68,0.2);padding:7px 14px;border-radius:8px;font-size:11px;font-weight:600;cursor:pointer;font-family:'Inter',sans-serif;}

/* FLASH */
.flash-container{position:fixed;top:20px;right:20px;z-index:999;display:flex;flex-direction:column;gap:8px;}
.flash{background:var(--card2);border-radius:12px;padding:12px 18px;font-size:13px;font-weight:500;display:flex;align-items:center;gap:10px;box-shadow:0 8px 30px rgba(0,0,0,0.3);animation:slideIn 0.3s ease-out;border-left:3px solid var(--green);}
.flash.info{border-left-color:var(--blue);}
@keyframes slideIn{from{opacity:0;transform:translateX(50px);}to{opacity:1;transform:translateX(0);}}

/* EMPTY STATE */
.empty{text-align:center;padding:50px 20px;color:var(--muted);}
.empty i{font-size:48px;margin-bottom:16px;opacity:0.3;}
.empty p{font-size:14px;}

/* NOTIFICATION BANNER */
.new-booking-banner{display:none;position:fixed;top:80px;right:20px;background:linear-gradient(135deg,#0D2E1F,#0a2818);border:1px solid var(--green);border-radius:14px;padding:14px 18px;z-index:998;animation:slideIn 0.3s ease-out;max-width:300px;}
.new-booking-banner h4{color:var(--green);font-size:13px;font-weight:700;margin-bottom:4px;}
.new-booking-banner p{color:var(--muted);font-size:12px;}
</style>
</head>
<body>

<!-- SIDEBAR -->
<div class="sidebar">
  <div class="logo">
    <div class="logo-icon">🔧</div>
    <div class="logo-text">FixMate Pro</div>
  </div>
  <nav class="nav">
    <a class="nav-item active" onclick="showSection('bookings')">
      <i class="fas fa-bell"></i> Bookings
      {% if pending_count > 0 %}<span class="nav-badge">{{ pending_count }}</span>{% endif %}
    </a>
    <a class="nav-item" onclick="showSection('workers')">
      <i class="fas fa-users"></i> Workers
    </a>
    <a class="nav-item" onclick="showSection('add')">
      <i class="fas fa-plus-circle"></i> Add Worker
    </a>
    <a class="nav-item" href="/export/bookings">
      <i class="fas fa-file-csv"></i> Export CSV
    </a>
  </nav>
  <div class="sidebar-footer">
    <div class="live-indicator">
      <div class="live-dot"></div>
      <span>Live — <span id="timer">15</span>s refresh</span>
    </div>
  </div>
</div>

<!-- FLASH NOTIFICATIONS -->
<div class="flash-container">
{% with messages = get_flashed_messages(with_categories=true) %}
{% if messages %}{% for cat, msg in messages %}
<div class="flash {{ cat }}"><i class="fas fa-check-circle"></i> {{ msg }}</div>
{% endfor %}{% endif %}
{% endwith %}
</div>

<!-- MAIN -->
<div class="main">

  <!-- TOPBAR -->
  <div class="topbar">
    <h1>FixMate <span>Admin Pro</span></h1>
    <div class="countdown-pill"><i class="fas fa-sync-alt" style="font-size:10px;"></i> Refresh in <span id="countdown">15</span>s</div>
    <a href="/export/bookings" class="export-btn"><i class="fas fa-download"></i> Export CSV</a>
  </div>

  <!-- STATS -->
  <div class="stats">
    <div class="stat-card purple">
      <div class="stat-icon"><i class="fas fa-clock"></i></div>
      <div class="stat-val">{{ pending_count }}</div>
      <div class="stat-label">Pending Bookings</div>
    </div>
    <div class="stat-card green">
      <div class="stat-icon"><i class="fas fa-check-circle"></i></div>
      <div class="stat-val">{{ accepted_count }}</div>
      <div class="stat-label">Accepted Today</div>
    </div>
    <div class="stat-card red">
      <div class="stat-icon"><i class="fas fa-times-circle"></i></div>
      <div class="stat-val">{{ rejected_count }}</div>
      <div class="stat-label">Rejected</div>
    </div>
    <div class="stat-card yellow">
      <div class="stat-icon"><i class="fas fa-users"></i></div>
      <div class="stat-val">{{ total_workers }}</div>
      <div class="stat-label">Total Workers</div>
    </div>
    <div class="stat-card blue">
      <div class="stat-icon"><i class="fas fa-wifi"></i></div>
      <div class="stat-val">{{ online_workers }}</div>
      <div class="stat-label">Online Now</div>
    </div>
  </div>

  <!-- SECTIONS -->
  <div id="section-bookings">
    <div class="panel">
      <div class="panel-head">
        <h2><i class="fas fa-list" style="color:var(--purple);margin-right:8px;"></i>Live Bookings ({{ bookings|length }})</h2>
        {% if pending_count > 0 %}
        <span class="badge Pending">{{ pending_count }} Pending</span>
        {% endif %}
      </div>
      <div class="panel-body">
        <!-- Search & Filter -->
        <div class="search-bar">
          <input type="text" id="searchBox" placeholder="Search customer, worker, service..." oninput="filterBookings()">
          <button class="filter-btn active" onclick="setFilter('All',this)">All</button>
          <button class="filter-btn" onclick="setFilter('Pending',this)">⏳ Pending</button>
          <button class="filter-btn" onclick="setFilter('Accepted',this)">✅ Done</button>
        </div>

        {% if bookings %}
        <div id="bookings-list">
        {% for b in bookings %}
        <div class="booking-card {{ b.status }}" data-status="{{ b.status }}" data-search="{{ b.customer_name }} {{ b.worker_name }} {{ b.service }} {{ b.customer_phone }}">
          <div class="bc-top">
            <div class="bc-avatar">{{ b.customer_name[0] }}</div>
            <div>
              <div class="bc-name">{{ b.customer_name }}</div>
              <div class="bc-time">{{ b.date_created }} · {{ b.id }}</div>
            </div>
            <span class="badge {{ b.status }}">{{ b.status }}</span>
          </div>
          <div class="bc-info">
            <i class="fas fa-phone" style="color:var(--green);width:14px;"></i> <span class="val">{{ b.customer_phone }}</span><br>
            <i class="fas fa-map-marker-alt" style="color:var(--yellow);width:14px;"></i> <span class="val">{{ b.customer_address }}</span><br>
            <i class="fas fa-hard-hat" style="color:var(--purple);width:14px;"></i> <span class="val">{{ b.worker_name }}</span> — {{ b.service }}<br>
            <i class="fas fa-calendar" style="color:var(--blue);width:14px;"></i> <span class="val">{{ b.date }}</span> @ <span class="val">{{ b.time }}</span>
            {% if b.note %}<br><i class="fas fa-sticky-note" style="color:var(--muted);width:14px;"></i> {{ b.note }}{% endif %}
          </div>
          <div class="bc-actions">
            {% if b.lat %}
            <a href="https://www.google.com/maps/dir/?api=1&destination={{ b.lat }},{{ b.lng }}" target="_blank" class="btn btn-map"><i class="fas fa-route"></i> Navigate</a>
            {% endif %}
            <a href="tel:{{ b.customer_phone }}" class="btn btn-call"><i class="fas fa-phone"></i> Call</a>
            <a href="https://wa.me/{{ b.customer_phone|replace(' ','')|replace('+','') }}" target="_blank" class="btn btn-whatsapp"><i class="fab fa-whatsapp"></i> WhatsApp</a>
            {% if b.status == 'Pending' %}
            <form method="POST" action="/admin" style="display:inline;">
              <input type="hidden" name="action" value="update_booking_status">
              <input type="hidden" name="booking_id" value="{{ b.id }}">
              <input type="hidden" name="status" value="Accepted">
              <button type="submit" class="btn btn-accept"><i class="fas fa-check"></i> Accept</button>
            </form>
            <form method="POST" action="/admin" style="display:inline;">
              <input type="hidden" name="action" value="update_booking_status">
              <input type="hidden" name="booking_id" value="{{ b.id }}">
              <input type="hidden" name="status" value="Rejected">
              <button type="submit" class="btn btn-reject"><i class="fas fa-times"></i> Reject</button>
            </form>
            {% endif %}
            <form method="POST" action="/admin" style="display:inline;" onsubmit="return confirm('Delete?')">
              <input type="hidden" name="action" value="delete_booking">
              <input type="hidden" name="booking_id" value="{{ b.id }}">
              <button type="submit" class="btn btn-del"><i class="fas fa-trash"></i></button>
            </form>
          </div>
        </div>
        {% endfor %}
        </div>
        {% else %}
        <div class="empty">
          <i class="fas fa-inbox"></i>
          <p>No bookings yet.<br>Waiting for customers...</p>
        </div>
        {% endif %}
      </div>
    </div>
  </div>

  <!-- WORKERS SECTION -->
  <div id="section-workers" style="display:none;">
    <div class="panel">
      <div class="panel-head">
        <h2><i class="fas fa-users" style="color:var(--purple);margin-right:8px;"></i>Manage Workers ({{ total_workers }})</h2>
        <span class="badge Accepted">{{ online_workers }} Online</span>
      </div>
      <div class="panel-body">
        {% for service, workers in data.items() %}
        <div class="service-sect">
          <div class="service-toggle" onclick="toggleService('{{ service }}')">
            <h3>
              {% if service=='electrician'%}⚡{% elif service=='plumber'%}🔧{% elif service=='cleaner'%}🧹
              {% elif service=='carpenter'%}🪚{% elif service=='mechanic'%}🔩{% elif service=='painter'%}🎨
              {% elif service=='medical'%}🏥{% elif service=='grocery'%}🛒{% else %}👷{% endif %}
              {{ service }}
            </h3>
            <span class="service-count">{{ workers|length }}</span>
            <i class="fas fa-chevron-down" style="font-size:11px;color:var(--muted);"></i>
          </div>
          <div class="service-workers" id="sw-{{ service }}">
            {% for w in workers %}
            <div class="worker-card">
              <div class="wc-top">
                <div class="wc-avatar">{{ w.initials }}</div>
                <div class="wc-info">
                  <div class="wc-name">{{ w.name }}</div>
                  <div class="wc-sub">📞 {{ w.phone }} · 📍 {{ w.location or 'Local' }} · ⭐ {{ w.rating }}</div>
                </div>
                <div class="toggle-wrap">
                  <span class="toggle-label">{% if w.isOnline %}Online{% else %}Offline{% endif %}</span>
                  <label class="toggle">
                    <input type="checkbox" {% if w.isOnline %}checked{% endif %} onchange="quickToggle('{{ w.id }}', this)">
                    <span class="slider"></span>
                  </label>
                </div>
              </div>
              <form method="POST" action="/admin" style="display:flex;gap:8px;flex-wrap:wrap;">
                <input type="hidden" name="action" value="edit">
                <input type="hidden" name="service" value="{{ service }}">
                <input type="hidden" name="worker_id" value="{{ w.id }}">
                <input type="text" name="name" value="{{ w.name }}" placeholder="Name" style="flex:1;min-width:120px;">
                <input type="text" name="phone" value="{{ w.phone }}" placeholder="Phone" style="flex:1;min-width:120px;">
                <input type="text" name="location" value="{{ w.location or '' }}" placeholder="City" style="flex:1;min-width:100px;">
                <input type="text" name="experience" value="{{ w.experience or '' }}" placeholder="Experience" style="flex:1;min-width:100px;">
                <input type="hidden" name="is_online" value="{% if w.isOnline %}on{% endif %}">
                <button type="submit" class="btn-save">💾 Save → App Updates</button>
              </form>
              <form method="POST" action="/admin" onsubmit="return confirm('Remove {{ w.name }}?')" style="margin-top:8px;">
                <input type="hidden" name="action" value="delete">
                <input type="hidden" name="service" value="{{ service }}">
                <input type="hidden" name="worker_id" value="{{ w.id }}">
                <button type="submit" class="btn-remove">🗑️ Remove Worker</button>
              </form>
            </div>
            {% endfor %}
          </div>
        </div>
        {% endfor %}
      </div>
    </div>
  </div>

  <!-- ADD WORKER SECTION -->
  <div id="section-add" style="display:none;">
    <div class="panel">
      <div class="panel-head">
        <h2><i class="fas fa-plus-circle" style="color:var(--purple);margin-right:8px;"></i>Add New Worker</h2>
      </div>
      <div class="panel-body">
        <div class="add-form">
          <h3><i class="fas fa-user-plus"></i> Worker Details</h3>
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
              <input type="number" name="distance" placeholder="Distance km" step="0.1" value="1.0">
            </div>
            <label class="check">
              <input type="checkbox" name="is_online" checked> 🟢 Set as Online immediately
            </label>
            <button type="submit" class="btn-primary">➕ Add Worker — Appears in App Instantly</button>
          </form>
        </div>
        <div style="padding:20px;text-align:center;color:var(--muted);font-size:13px;">
          <i class="fas fa-info-circle" style="color:var(--blue);"></i>
          Added workers appear in the phone app as soon as you pull-to-refresh or open the service screen.
        </div>
      </div>
    </div>
  </div>

</div>

<script>
// ── SECTION NAVIGATION ────────────────────────────────────────
function showSection(name) {
  ['bookings','workers','add'].forEach(s => {
    document.getElementById('section-' + s).style.display = s === name ? 'block' : 'none';
  });
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  event.currentTarget.classList.add('active');
}

// ── AUTO REFRESH ──────────────────────────────────────────────
let secs = 15;
function tick() {
  secs--;
  document.getElementById('countdown').textContent = secs;
  document.getElementById('timer').textContent = secs;
  if (secs <= 0) location.reload();
  else setTimeout(tick, 1000);
}
setTimeout(tick, 1000);

// ── SEARCH & FILTER ───────────────────────────────────────────
let currentFilter = 'All';
function filterBookings() {
  const q = document.getElementById('searchBox').value.toLowerCase();
  document.querySelectorAll('.booking-card').forEach(card => {
    const search = card.dataset.search.toLowerCase();
    const status = card.dataset.status;
    const matchSearch = search.includes(q);
    const matchFilter = currentFilter === 'All' || status === currentFilter;
    card.style.display = matchSearch && matchFilter ? 'block' : 'none';
  });
}
function setFilter(f, btn) {
  currentFilter = f;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  filterBookings();
}

// ── SERVICE TOGGLE ────────────────────────────────────────────
function toggleService(service) {
  const el = document.getElementById('sw-' + service);
  el.classList.toggle('open');
}

// ── QUICK ONLINE TOGGLE ───────────────────────────────────────
async function quickToggle(workerId, checkbox) {
  try {
    const resp = await fetch('/api/toggle_worker', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({worker_id: workerId})
    });
    const data = await resp.json();
    const label = checkbox.closest('.toggle-wrap').querySelector('.toggle-label');
    label.textContent = data.isOnline ? 'Online' : 'Offline';
    // Show mini toast
    showToast(data.isOnline ? '✅ Worker set Online' : '⚫ Worker set Offline');
  } catch(e) {
    console.error(e);
  }
}

function showToast(msg) {
  const t = document.createElement('div');
  t.className = 'flash';
  t.innerHTML = '<i class="fas fa-bolt"></i> ' + msg;
  t.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:999;';
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}

// ── SOUND ALERT FOR NEW BOOKINGS ──────────────────────────────
const lastCount = parseInt(localStorage.getItem('lastBookingCount') || '0');
const currentCount = {{ bookings|length }};
const pendingCount = {{ pending_count }};
if (currentCount > lastCount && lastCount > 0) {
  // New booking! Play beep
  try {
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain); gain.connect(ctx.destination);
    osc.frequency.setValueAtTime(800, ctx.currentTime);
    osc.frequency.setValueAtTime(600, ctx.currentTime + 0.1);
    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5);
    osc.start(); osc.stop(ctx.currentTime + 0.5);
    showToast('🔔 NEW BOOKING RECEIVED!');
  } catch(e) {}
}
localStorage.setItem('lastBookingCount', currentCount);

// ── AUTO HIDE FLASH ───────────────────────────────────────────
setTimeout(() => {
  document.querySelectorAll('.flash').forEach(f => {
    f.style.transition = 'opacity 0.5s';
    f.style.opacity = '0';
    setTimeout(() => f.remove(), 500);
  });
}, 4000);
</script>
</body>
</html>
"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
