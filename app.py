from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime, timedelta, date
from functools import wraps
import os
from bson.objectid import ObjectId

app = Flask(__name__)
app.secret_key = 'admin-secret-key-change-this-to-something-secure'
CORS(app)

# MongoDB Connection
MONGO_URI = "mongodb+srv://suresh9576sharma_db_user:dn3hXtnCq5NmLGXv@replit0.djpxcq9.mongodb.net/?appName=replit0"
client = MongoClient(MONGO_URI)
db = client['repltjimmy']

# Collections
config_collection = db['config']
orders_collection = db['orders']
normal_ids_collection = db['normal_ids']
verified_ids_collection = db['verified_ids']
used_utrs_collection = db['used_utrs']

def init_config():
    try:
        if config_collection.count_documents({}) == 0:
            default_config = {
                'normal_price': 200,
                'verified_price': 400,
                'qr_code': '',
                'admin_username': 'jimmy',
                'admin_password': 'jimmy123',
                'announcement': '',
                'bharatpe_token': '',
                'bharatpe_mid': '',
                'upi_id': '',
                'whatsapp_link': 'https://wa.link/soyd4g',
                'telegram_link': 'https://l1nq.link/?telegram=SUPERMAN_ADMIN1',
                'vip_utrs': []  # Initialize empty VIP UTR list
            }
            config_collection.insert_one(default_config)
            print("✅ Default config created")
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
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        config = config_collection.find_one({})
        if config and username == config.get('admin_username') and password == config.get('admin_password'):
            session['admin_logged_in'] = True
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Invalid credentials'})
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    return render_template('admin_dashboard.html')

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
    
    return jsonify({'success': True, 'added': len(docs)})

@app.route('/api/admin/ids/<id_id>', methods=['DELETE'])
@admin_required
def delete_id(id_id):
    try:
        # Try both collections
        res1 = normal_ids_collection.delete_one({'_id': ObjectId(id_id)})
        res2 = verified_ids_collection.delete_one({'_id': ObjectId(id_id)})
        return jsonify({'success': (res1.deleted_count + res2.deleted_count) > 0})
    except:
        return jsonify({'success': False})

@app.route('/api/admin/orders')
@admin_required
def admin_orders():
    # Sort by date DESC so latest orders come first
    orders = list(orders_collection.find({}).sort('date', -1))
    for o in orders:
        o['_id'] = str(o['_id'])
        o['date'] = o['date'].isoformat() if isinstance(o.get('date'), datetime) else o.get('date')
        o.setdefault('status', 'pending')
        o.setdefault('auto_approved', False)
        o.setdefault('is_vip', False)
    return jsonify(orders)

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
    except:
        return jsonify({'success': False})

@app.route('/api/admin/stats')
@admin_required
def admin_stats():
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end = datetime.combine(date.today(), datetime.max.time())

    normal_added_today = normal_ids_collection.count_documents({'added_date': {'$gte': today_start}})
    verified_added_today = verified_ids_collection.count_documents({'added_date': {'$gte': today_start}})

    normal_available = normal_ids_collection.count_documents({'sold': False})
    verified_available = verified_ids_collection.count_documents({'sold': False})

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

    return jsonify({
        'normal_total': normal_added_today,
        'normal_available': normal_available,
        'verified_total': verified_added_today,
        'verified_available': verified_available,
        'total_orders': today_orders_count,
        'total_revenue': today_revenue,
        'pending_orders': pending_orders_count,
        'auto_approved_today': auto_approved_count
    })

# ====================== MAIN ======================
if __name__ == '__main__':
    os.makedirs('templates', exist_ok=True)
    print("\n" + "="*50)
    print("🚀 SupermanStore Admin Panel Starting...")
    print("="*50)
    print(f"🌐 Admin Panel: http://localhost:5001/")
    print(f"⚡ Auto Payment: ENABLED")
    print(f"👑 VIP UTR: ENABLED")
    print("="*50 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5001)