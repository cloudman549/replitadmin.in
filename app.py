from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime, timedelta, date
from functools import wraps
import os
import sys
import gzip
import time
import threading
from bson.objectid import ObjectId

# Windows consoles default to cp1252 and crash on emoji log output.
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

app = Flask(__name__)
app.secret_key = 'admin-secret-key-change-this-to-something-secure'
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000
CORS(app)

# MongoDB Connection
MONGO_URI = "mongodb+srv://terajoginderbhai123_db_user:llhBLaZ6AjqP5dVU@cluster0.d7bjhgb.mongodb.net/?retryWrites=true&w=majority"
client = MongoClient(
    MONGO_URI,
    maxPoolSize=50,
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=5000,
    socketTimeoutMS=15000,
    appname='replitstore-admin',
)
db = client['repltjimmy']

# Collections
config_collection = db['config']
orders_collection = db['orders']
normal_ids_collection = db['normal_ids']
verified_ids_collection = db['verified_ids']
used_utrs_collection = db['used_utrs']

# ====================== PERFORMANCE ======================
_COMPRESSIBLE = {
    'text/html', 'text/css', 'application/json', 'application/javascript',
    'text/javascript', 'image/svg+xml', 'text/plain', 'application/xml',
}

@app.after_request
def gzip_response(response):
    """Compress HTML/JSON responses (dashboard 62KB -> ~11KB)."""
    try:
        if response.direct_passthrough or not (200 <= response.status_code < 300):
            return response
        if response.headers.get('Content-Encoding'):
            return response
        if 'gzip' not in (request.headers.get('Accept-Encoding') or '').lower():
            return response
        if response.mimetype not in _COMPRESSIBLE:
            return response
        data = response.get_data()
        if len(data) < 500:
            return response
        compressed = gzip.compress(data, compresslevel=6)
        if len(compressed) >= len(data):
            return response
        response.set_data(compressed)
        response.headers['Content-Encoding'] = 'gzip'
        response.headers['Content-Length'] = str(len(compressed))
        response.headers.add('Vary', 'Accept-Encoding')
    except Exception:
        pass
    return response

def _ensure_indexes():
    try:
        normal_ids_collection.create_index([('sold', 1)])
        verified_ids_collection.create_index([('sold', 1)])
        orders_collection.create_index([('utr', 1)])
        orders_collection.create_index([('status', 1), ('date', -1)])
        orders_collection.create_index([('date', -1)])
        used_utrs_collection.create_index([('utr', 1)])
    except Exception as e:
        print(f"index error: {e}")

threading.Thread(target=_ensure_indexes, daemon=True).start()

DEFAULT_CONFIG = {
    'normal_price': 200,
    'verified_price': 400,
    'qr_code': '',
    'admin_username': 'Kundan',
    'admin_password': 'Kundan@123',
    'announcement': '',
    'bharatpe_token': '',
    'bharatpe_mid': '',
    'upi_id': '',
    'whatsapp_link': 'https://wa.link/soyd4g',
    'telegram_link': 'https://t.me/replitstore',
    'vip_utrs': []
}

def init_config():
    try:
        config = config_collection.find_one({})
        if config is None:
            config_collection.insert_one(dict(DEFAULT_CONFIG))
            print("✅ Default config created")
            return

        # Older/copied config documents may be missing keys (especially
        # admin_username / admin_password). Fill only the missing ones so
        # existing custom settings are never overwritten.
        missing = {k: v for k, v in DEFAULT_CONFIG.items() if k not in config}
        if missing:
            config_collection.update_one({'_id': config['_id']}, {'$set': missing})
            print(f"✅ Filled missing config keys: {', '.join(missing)}")
    except Exception as e:
        print(f"❌ Config init error: {e}")

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

# Startup
print("="*50)
try:
    client.admin.command('ping')
    print("✅ MongoDB Connected!")
    init_config()
except Exception as e:
    print(f"❌ MongoDB Failed: {e}")
print("="*50)

# ====================== ROUTES ======================

@app.route('/')
def index():
    return redirect(url_for('admin_login'))

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        data = request.json or {}
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        config = config_collection.find_one({}) or {}
        admin_username = (config.get('admin_username') or DEFAULT_CONFIG['admin_username']).strip()
        admin_password = config.get('admin_password') or DEFAULT_CONFIG['admin_password']
        if username == admin_username and password == admin_password:
            session['admin_logged_in'] = True
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Invalid credentials'})
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    response = make_response(render_template('admin_dashboard.html'))
    response.headers['Cache-Control'] = 'no-store'
    return response

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))

# ====================== API ======================

@app.route('/api/admin/config', methods=['GET', 'POST'])
@admin_required
def admin_config():
    if request.method == 'POST':
        data = request.json
        update = {}
        keys = ['normal_price', 'verified_price', 'qr_code', 'admin_username', 
                'admin_password', 'announcement', 'bharatpe_token', 'bharatpe_mid',
                'upi_id', 'whatsapp_link', 'telegram_link', 'vip_utrs']
        for k in keys:
            if k in data:
                if k in ['normal_price', 'verified_price']:
                    update[k] = int(data[k])
                else:
                    update[k] = data[k]
        if update:
            config_collection.update_one({}, {'$set': update}, upsert=True)
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'No data'})
    config = config_collection.find_one({}, {'_id': 0})
    return jsonify(config or {})

@app.route('/api/admin/ids', methods=['POST'])
@admin_required
def admin_ids_add():
    """Single ID add (kept for API compatibility but not used in UI)"""
    data = request.json
    id_type = data.get('type', 'normal')
    
    if id_type not in ['normal', 'verified']:
        return jsonify({'success': False, 'error': 'Invalid type'})
    
    coll = normal_ids_collection if id_type == 'normal' else verified_ids_collection
    
    new_id = {
        'userid': data.get('userid', '').strip(),
        'password': data.get('password', '').strip(),
        'email': data.get('email', '').strip(),
        'email_password': data.get('email_password', '').strip(),
        'sold': False,
        'added_date': datetime.now()
    }
    coll.insert_one(new_id)
    return jsonify({'success': True})

@app.route('/api/admin/ids/<id_type>', methods=['GET'])
@admin_required
def admin_ids_list(id_type):
    if id_type not in ['normal', 'verified']:
        return jsonify({'success': False, 'error': 'Invalid type'})
    
    coll = normal_ids_collection if id_type == 'normal' else verified_ids_collection
    ids = list(coll.find({}).sort('added_date', -1))
    
    for i in ids:
        i['_id'] = str(i['_id'])
        if i.get('added_date'):
            i['added_date'] = i['added_date'].isoformat()
    
    return jsonify({'ids': ids})

@app.route('/api/admin/ids/bulk', methods=['POST'])
@admin_required
def bulk_add_ids():
    data = request.json
    id_type = data.get('type', 'normal')
    
    if id_type not in ['normal', 'verified']:
        return jsonify({'success': False, 'error': 'Invalid type'})
    
    userids = data.get('userids', [])
    password = data.get('password', '').strip()
    email = data.get('email', '').strip()
    email_password = data.get('email_password', '').strip()
    
    if not userids or not password:
        return jsonify({'success': False, 'error': 'No data'})
    
    coll = normal_ids_collection if id_type == 'normal' else verified_ids_collection
    
    docs = []
    for userid in userids:
        if userid.strip():  # Only add non-empty user IDs
            docs.append({
                'userid': userid.strip(),
                'password': password,
                'email': email,
                'email_password': email_password,
                'sold': False,
                'added_date': datetime.now()
            })
    
    if docs:
        coll.insert_many(docs)
        print(f"✅ Bulk added {len(docs)} {id_type} IDs")
    
    return jsonify({'success': True, 'added': len(docs)})

@app.route('/api/admin/ids/<id_id>', methods=['DELETE'])
@admin_required
def delete_id(id_id):
    try:
        # Try both collections
        res1 = normal_ids_collection.delete_one({'_id': ObjectId(id_id)})
        res2 = verified_ids_collection.delete_one({'_id': ObjectId(id_id)})
        deleted = (res1.deleted_count + res2.deleted_count) > 0
        if deleted:
            print(f"🗑️ Deleted ID: {id_id}")
        return jsonify({'success': deleted})
    except Exception as e:
        print(f"❌ Delete ID error: {e}")
        return jsonify({'success': False})

@app.route('/api/admin/orders')
@admin_required
def admin_orders():
    try:
        limit = min(int(request.args.get('limit', 100)), 500)
    except (TypeError, ValueError):
        limit = 100
    # Sort by date DESC so latest orders come first, and only fetch what the UI shows
    orders = list(orders_collection.find({}).sort('date', -1).limit(limit))
    for o in orders:
        o['_id'] = str(o['_id'])
        o['date'] = o['date'].isoformat() if isinstance(o.get('date'), datetime) else o.get('date')
        o.setdefault('status', 'pending')
        o.setdefault('auto_approved', False)
        o.setdefault('is_vip', False)
    response = jsonify(orders)
    response.headers['Cache-Control'] = 'no-store'
    return response

@app.route('/api/admin/orders/<order_id>/approve', methods=['POST'])
@admin_required
def approve_order(order_id):
    try:
        order = orders_collection.find_one({'_id': ObjectId(order_id)})
        if not order or order.get('status') != 'pending':
            return jsonify({'success': False, 'error': 'Invalid order or already processed'})
        
        utr = order.get('utr', '').strip()
        if used_utrs_collection.find_one({'utr': utr}):
            return jsonify({'success': False, 'error': 'UTR already used'})
        
        # Check if amount was edited
        data = request.json or {}
        edited_amount = data.get('edited_amount')
        edited_quantity = data.get('edited_quantity')
        
        # Use edited values if provided, otherwise use original
        final_amount = edited_amount if edited_amount else order.get('amount')
        qty = edited_quantity if edited_quantity else order.get('quantity', 1)
        
        coll = normal_ids_collection if order['type'] == 'normal' else verified_ids_collection
        avail = list(coll.find({'sold': False}).limit(qty))
        
        if len(avail) < qty:
            return jsonify({'success': False, 'error': f'Stock low. Only {len(avail)} IDs available.'})
        
        delivered = []
        for doc in avail:
            coll.update_one({'_id': doc['_id']}, {'$set': {'sold': True, 'sold_date': datetime.now()}})
            delivered.append({
                'userid': doc['userid'],
                'password': doc['password'],
                'email': doc.get('email',''),
                'email_password': doc.get('email_password','')
            })
        
        used_utrs_collection.insert_one({'utr': utr, 'timestamp': datetime.now(), 'order_id': order_id})
        
        # Update order
        update_data = {
            'status': 'approved', 
            'delivered_ids': delivered, 
            'approved_at': datetime.now(),
            'final_amount': final_amount,
            'final_quantity': qty,
            'auto_approved': False  # Manual approval
        }
        
        if edited_amount:
            update_data['original_amount'] = order.get('amount')
            update_data['amount'] = edited_amount
            update_data['amount_edited'] = True
        
        orders_collection.update_one(
            {'_id': ObjectId(order_id)},
            {'$set': update_data}
        )
        
        print(f"✅ Order {order_id} manually approved")
        print(f"📦 Delivered {qty} IDs for UTR: {utr}")
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"❌ Approval error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/orders/<order_id>/reject', methods=['POST'])
@admin_required
def reject_order(order_id):
    try:
        res = orders_collection.update_one(
            {'_id': ObjectId(order_id), 'status': 'pending'},
            {'$set': {'status': 'rejected', 'rejected_at': datetime.now()}}
        )
        
        if res.modified_count > 0:
            print(f"❌ Order {order_id} rejected")
        
        return jsonify({'success': res.modified_count > 0})
    except Exception as e:
        print(f"❌ Reject error: {e}")
        return jsonify({'success': False})

_stats_cache = {'data': None, 'ts': 0.0}
STATS_CACHE_TTL = 3  # seconds

@app.route('/api/admin/stats')
@admin_required
def admin_stats():
    now = time.time()
    if _stats_cache['data'] is not None and (now - _stats_cache['ts']) < STATS_CACHE_TTL:
        response = jsonify(_stats_cache['data'])
        response.headers['Cache-Control'] = 'no-store'
        return response

    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end = datetime.combine(date.today(), datetime.max.time())

    normal_added_today = normal_available = 0
    verified_added_today = verified_available = 0

    # One DB round trip for all ID counters
    try:
        rows = list(normal_ids_collection.aggregate([
            {'$group': {
                '_id': None,
                'available': {'$sum': {'$cond': [{'$eq': ['$sold', False]}, 1, 0]}},
                'added_today': {'$sum': {'$cond': [{'$gte': ['$added_date', today_start]}, 1, 0]}},
            }},
            {'$unionWith': {
                'coll': 'verified_ids',
                'pipeline': [
                    {'$group': {
                        '_id': 'verified',
                        'available': {'$sum': {'$cond': [{'$eq': ['$sold', False]}, 1, 0]}},
                        'added_today': {'$sum': {'$cond': [{'$gte': ['$added_date', today_start]}, 1, 0]}},
                    }},
                ],
            }},
        ], maxTimeMS=4000))
        for row in rows:
            if row.get('_id') == 'verified':
                verified_available = row.get('available', 0)
                verified_added_today = row.get('added_today', 0)
            else:
                normal_available = row.get('available', 0)
                normal_added_today = row.get('added_today', 0)
    except Exception as e:
        print(f"❌ ID stats error: {e}")
        normal_added_today = normal_ids_collection.count_documents({'added_date': {'$gte': today_start}})
        verified_added_today = verified_ids_collection.count_documents({'added_date': {'$gte': today_start}})
        normal_available = normal_ids_collection.count_documents({'sold': False})
        verified_available = verified_ids_collection.count_documents({'sold': False})

    pending_orders_count = 0
    today_orders_count = 0
    today_revenue = 0
    auto_approved_count = 0

    # One DB round trip for all order counters
    try:
        rows = list(orders_collection.aggregate([
            {'$facet': {
                'pending': [
                    {'$match': {'status': 'pending'}},
                    {'$count': 'n'},
                ],
                'today': [
                    {'$match': {'date': {'$gte': today_start, '$lte': today_end}, 'status': 'approved'}},
                    {'$group': {
                        '_id': None,
                        'count': {'$sum': 1},
                        'revenue': {'$sum': {'$ifNull': ['$amount', 0]}},
                    }},
                ],
                'auto': [
                    {'$match': {'date': {'$gte': today_start, '$lte': today_end}, 'auto_approved': True}},
                    {'$count': 'n'},
                ],
            }},
        ], maxTimeMS=4000))
        facet = rows[0] if rows else {}

        pending_rows = facet.get('pending') or []
        pending_orders_count = pending_rows[0].get('n', 0) if pending_rows else 0

        auto_rows = facet.get('auto') or []
        auto_approved_count = auto_rows[0].get('n', 0) if auto_rows else 0

        today_rows = facet.get('today') or []
        if today_rows:
            today_orders_count = today_rows[0].get('count', 0)
            today_revenue = today_rows[0].get('revenue', 0)
    except Exception as e:
        print(f"❌ Order stats error: {e}")
        pending_orders_count = orders_collection.count_documents({'status': 'pending'})
        today_approved_orders = list(orders_collection.find({
            'date': {'$gte': today_start, '$lte': today_end},
            'status': 'approved'
        }))
        today_orders_count = len(today_approved_orders)
        today_revenue = sum(o.get('amount', 0) for o in today_approved_orders)
        auto_approved_count = orders_collection.count_documents({
            'date': {'$gte': today_start, '$lte': today_end},
            'auto_approved': True
        })

    payload = {
        'normal_total': normal_added_today,
        'normal_available': normal_available,
        'verified_total': verified_added_today,
        'verified_available': verified_available,
        'total_orders': today_orders_count,
        'total_revenue': today_revenue,
        'pending_orders': pending_orders_count,
        'auto_approved_today': auto_approved_count
    }

    _stats_cache['data'] = payload
    _stats_cache['ts'] = now

    response = jsonify(payload)
    response.headers['Cache-Control'] = 'no-store'
    return response

@app.route('/api/admin/hard-reset', methods=['POST'])
@admin_required
def hard_reset():
    """
    DANGER: Deletes ALL data except config settings
    """
    try:
        print("\n" + "="*50)
        print("⚠️ HARD RESET INITIATED")
        print("="*50)
        
        # Count before deletion
        normal_count = normal_ids_collection.count_documents({})
        verified_count = verified_ids_collection.count_documents({})
        orders_count = orders_collection.count_documents({})
        used_utrs_count = used_utrs_collection.count_documents({})
        
        # Get VIP UTRs count before clearing
        config = config_collection.find_one({})
        vip_count = len(config.get('vip_utrs', []))
        
        print(f"📊 Current Data:")
        print(f"   Normal IDs: {normal_count}")
        print(f"   Verified IDs: {verified_count}")
        print(f"   Orders: {orders_count}")
        print(f"   Used UTRs: {used_utrs_count}")
        print(f"   VIP UTRs: {vip_count}")
        
        # Delete all data
        normal_ids_collection.delete_many({})
        verified_ids_collection.delete_many({})
        orders_collection.delete_many({})
        used_utrs_collection.delete_many({})
        
        # Clear VIP UTRs from config
        config_collection.update_one(
            {},
            {'$set': {'vip_utrs': []}}
        )
        
        print("\n✅ Database Reset Complete!")
        print("="*50 + "\n")
        
        return jsonify({
            'success': True,
            'deleted': {
                'normal_ids': normal_count,
                'verified_ids': verified_count,
                'orders': orders_count,
                'used_utrs': used_utrs_count,
                'vip_utrs': vip_count
            }
        })
    except Exception as e:
        print(f"❌ Hard reset error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ====================== MAIN ======================
if __name__ == '__main__':
    os.makedirs('templates', exist_ok=True)
    print("\n" + "="*50)
    print("🚀 ReplitStore Admin Panel Starting...")
    print("="*50)
    print(f"🌐 Admin Panel: http://localhost:5001/")
    print(f"⚡ Auto Payment: ENABLED")
    print(f"👑 VIP UTR: ENABLED")
    print(f"🗑️ Hard Reset: AVAILABLE")
    print("="*50 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5001)