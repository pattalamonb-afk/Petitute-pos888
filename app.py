from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///petitute.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY','dev-secret-petitute')

db = SQLAlchemy(app)

# Models
class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(50))
    email = db.Column(db.String(120))
    member = db.Column(db.Boolean, default=False)
    points = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    bookings = db.relationship('Booking', backref='customer', lazy=True)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    service_type = db.Column(db.String(50))  # "overnight", "hourly", "groom"
    size = db.Column(db.String(10), nullable=True)  # S/M/L for overnight/groom
    start = db.Column(db.DateTime, nullable=False)
    end = db.Column(db.DateTime, nullable=False)
    price = db.Column(db.Float, nullable=False)
    paid = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- Authentication (simple session-based) ---
ADMIN_USER = os.environ.get('ADMIN_USER','admin')
ADMIN_PASS = os.environ.get('ADMIN_PASS','admin123')

def login_required(f):
    from functools import wraps
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return wrapped

# --- Pricing logic ---
def price_for(service_type, size=None, hours=None):
    if service_type == 'overnight':
        base = {'S':300, 'M':500, 'L':700}
        return base.get(size,500)
    if service_type == 'hourly':
        h = max(1, int(hours or 1))
        return 100 + (h-1)*50
    if service_type == 'groom':
        base = {'S':200, 'M':300, 'L':450}
        return base.get(size,300)
    return 0

# --- Routes ---
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('username')
        p = request.form.get('password')
        if u == ADMIN_USER and p == ADMIN_PASS:
            session['logged_in'] = True
            session['user'] = u
            flash('เข้าสู่ระบบเรียบร้อย', 'success')
            nxt = request.args.get('next') or url_for('index')
            return redirect(nxt)
        flash('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('ออกจากระบบแล้ว', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    bookings = Booking.query.order_by(Booking.created_at.desc()).limit(20).all()
    return render_template('index.html', bookings=bookings)

@app.route('/customers')
@login_required
def customers():
    qs = Customer.query.order_by(Customer.created_at.desc()).all()
    return render_template('customers.html', customers=qs)

@app.route('/customers/new', methods=['POST'])
@login_required
def customer_new():
    name = request.form['name']
    phone = request.form.get('phone')
    email = request.form.get('email')
    member = True if request.form.get('member') == 'on' else False
    c = Customer(name=name, phone=phone, email=email, member=member)
    db.session.add(c); db.session.commit()
    flash('บันทึกลูกค้าแล้ว', 'success')
    return redirect(url_for('customers'))

@app.route('/book', methods=['GET','POST'])
@login_required
def book():
    if request.method == 'GET':
        customers = Customer.query.all()
        return render_template('bookings.html', customers=customers)
    # POST - สร้าง booking
    customer_id = int(request.form['customer_id'])
    service = request.form['service_type']
    size = request.form.get('size') or None
    if service == 'overnight':
        start = datetime.fromisoformat(request.form['start'])
        nights = int(request.form.get('nights',1))
        end = start + timedelta(days=nights)
        price = price_for('overnight', size=size) * nights
    elif service == 'hourly':
        start = datetime.fromisoformat(request.form['start'])
        hours = int(request.form.get('hours',1))
        end = start + timedelta(hours=hours)
        price = price_for('hourly', hours=hours)
    else: # groom
        start = datetime.fromisoformat(request.form['start'])
        end = start + timedelta(hours=1)
        price = price_for('groom', size=size)

    # apply member discount (10%)
    customer = Customer.query.get(customer_id)
    if customer and customer.member:
        discount = 0.10
        price = round(price * (1-discount),2)
        customer.points += int(price // 10)
    b = Booking(customer_id=customer_id, service_type=service, size=size,
                start=start, end=end, price=price, paid=False)
    db.session.add(b)
    db.session.commit()
    flash('จองเสร็จแล้ว (ยังไม่ชำระ)', 'success')
    return redirect(url_for('index'))

@app.route('/checkout/<int:booking_id>', methods=['GET','POST'])
@login_required
def checkout(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    customer = booking.customer
    if request.method == 'POST':
        booking.paid = True
        db.session.commit()
        flash('ชำระเงินเรียบร้อย', 'success')
        return redirect(url_for('index'))
    return render_template('checkout.html', booking=booking, customer=customer)

@app.route('/admin')
@login_required
def admin():
    total_bookings = Booking.query.count()
    unpaid = Booking.query.filter_by(paid=False).count()
    revenue = db.session.query(db.func.sum(Booking.price)).filter(Booking.paid==True).scalar() or 0
    customers = Customer.query.count()
    return render_template('admin.html', total_bookings=total_bookings,
                           unpaid=unpaid, revenue=revenue, customers=customers)

if __name__ == '__main__':
    # For Render/Gunicorn, entrypoint will be "gunicorn app:app"
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT',5000)), debug=True)
