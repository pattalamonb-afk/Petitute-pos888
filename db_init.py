from app import db, Customer, Booking
from datetime import datetime, timedelta

db.create_all()

if not Customer.query.first():
    c1 = Customer(name="น.ส. ศรีสุข", phone="0812345678", email="sri@example.com", member=True, points=120)
    c2 = Customer(name="นายสมชาย", phone="0898765432", email="som@example.com", member=False)
    db.session.add_all([c1,c2])
    db.session.commit()

    b1 = Booking(customer_id=c1.id, service_type="overnight", size="M",
                 start=datetime.utcnow(), end=datetime.utcnow()+timedelta(days=1), price=500.0, paid=False)
    b2 = Booking(customer_id=c2.id, service_type="groom", size="S",
                 start=datetime.utcnow(), end=datetime.utcnow()+timedelta(hours=1), price=200.0, paid=True)
    db.session.add_all([b1,b2])
    db.session.commit()

print("DB initialized")
