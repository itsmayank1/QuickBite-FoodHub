from flask import Flask, render_template, request, redirect, session, flash
import mysql.connector
import random
import threading
import time
from datetime import datetime, timedelta
import razorpay # type: ignore
import os

razorpay_client = razorpay.Client(auth=(
    os.getenv("RZP_KEY_ID"),
    os.getenv("RZP_SECRET")
))

app = Flask(__name__)

# ===== GLOBAL BRANDING =====
APP_NAME = "QuickBite FoodHub"
TAGLINE = "Fast • Fresh • Food | by Mayank Upadhayay | contact:QuickBiteFoodhub@yahoo.com"

@app.context_processor
def inject_globals():
    return {
        "APP_NAME": APP_NAME,
        "TAGLINE": TAGLINE
    }
 
app.secret_key = "food_ordering_secret"

# Database connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="food_ordering_db",
    port=3307
)
cursor = db.cursor()



@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        if not name or not email or not password:
            flash("All fields are required!")
            return redirect('/signup')

        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        if cursor.fetchone():
            flash("Email already registered!")
            return redirect('/signup')

        cursor.execute(
            "INSERT INTO users (name, email, password) VALUES (%s,%s,%s)",
            (name, email, password)
        )
        db.commit()

        flash("Signup successful! Please login.")
        return redirect('/login')

    return render_template('signup.html')

@app.route('/admin_signup', methods=['GET','POST'])
def admin_signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cursor.execute(
            "INSERT INTO admin (username, password) VALUES (%s,%s)",
            (username, password)
        )
        db.commit()

        flash("Admin account created")
        return redirect('/login_all')

    return render_template("admin_signup.html")

@app.route('/agent_signup', methods=['GET','POST'])
def agent_signup():
    if request.method == 'POST':
        name = request.form['name']
        password = request.form['password']

        cursor.execute(
            "INSERT INTO delivery_agents (name, password) VALUES (%s,%s)",
            (name, password)
        )
        db.commit()

        flash("Agent created")
        return redirect('/login_all')

    return render_template("agent_signup.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        if not email or not password:
            flash("Email and password required!")
            return redirect('/login')

        cursor.execute(
            "SELECT * FROM users WHERE email=%s AND password=%s",
            (email, password)
        )
        user = cursor.fetchone()

        if user:
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            flash("Login successful!")
            return redirect('/')
        else:
            flash("Invalid login credentials!")
            return redirect('/login')

    return render_template('login.html')

# ================= COMMON LOGIN PAGE =================
@app.route('/login_all', methods=['GET','POST'])
def login_all():

    if request.method == 'POST':

        role = request.form.get('role')
        username = request.form.get('username')
        password = request.form.get('password')

        # ===== USER LOGIN =====
        if role == "user":
            cursor.execute(
                "SELECT * FROM users WHERE email=%s AND password=%s",
                (username, password)
            )
            user = cursor.fetchone()

            if user:
                session['user_id'] = user[0]
                session['user_name'] = user[1]
                flash("User login successful")
                return redirect('/')
            else:
                flash("Invalid user login")

        # ===== ADMIN LOGIN =====
        elif role == "admin":
            cursor.execute(
                "SELECT * FROM admin WHERE username=%s AND password=%s",
                (username, password)
            )
            admin = cursor.fetchone()

            if admin:
                session['admin'] = True
                flash("Admin login successful")
                return redirect('/admin/dashboard')
            else:
                flash("Invalid admin login")

        # ===== AGENT LOGIN =====
        elif role == "agent":
            cursor.execute(
                "SELECT * FROM delivery_agents WHERE name=%s AND password=%s",
                (username, password)
            )
            agent = cursor.fetchone()

            if agent:
                flash("Agent login successful")
                return redirect(f"/agent/{agent[0]}")
            else:
                flash("Invalid agent login")

    return render_template("login_all.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ================= USER SIDE =================
@app.route('/')
def index():

    search = request.args.get('search')

    if search:
        cursor.execute("SELECT * FROM food WHERE name LIKE %s", (f"%{search}%",))
    else:
        cursor.execute("SELECT * FROM food")

    foods = cursor.fetchall()

    wallet = 0
    fav_food = None   # IMPORTANT

    if 'user_id' in session:

        # wallet
        cursor.execute(
            "SELECT wallet_balance FROM users WHERE id=%s",
            (session['user_id'],)
        )
        wallet = cursor.fetchone()[0]

        # favourite food query
        cursor.execute("""
            SELECT food_name
            FROM orders
            WHERE user_id=%s
            GROUP BY food_name
            ORDER BY COUNT(*) DESC
            LIMIT 1
        """, (session['user_id'],))

        result = cursor.fetchone()
        if result:
            fav_food = result[0]

    return render_template(
        "index.html",
        foods=foods,
        wallet=wallet,
        fav=fav_food
    )
@app.route('/add_to_cart/<food>/<int:price>')
def add_to_cart(food, price):

    # create cart if not exists
    if 'cart' not in session:
        session['cart'] = {}

    cart = session['cart']

    # if item already in cart → increase quantity
    if food in cart:
        cart[food]['qty'] += 1
    else:
        cart[food] = {
            'price': price,
            'qty': 1
        }

    session['cart'] = cart
    flash(f"{food} added to cart")
    return redirect('/cart')

@app.route('/cart')
def cart():
    cart = session.get('cart', {})
    total = sum(item['price'] * item['qty'] for item in cart.values())
    return render_template('cart.html', cart=cart, total=total)

@app.route('/remove_from_cart/<food>')
def remove_from_cart(food):
    cart = session.get('cart', {})
    if food in cart:
        del cart[food]
    session['cart'] = cart
    return redirect('/cart')
@app.route('/checkout')
def checkout():
    cart = session.get('cart', {})
    if not cart:
        return redirect('/')

    total = sum(item['price'] * item['qty'] for item in cart.values())

    # 🔴 CREATE RAZORPAY ORDER HERE
    razorpay_order = razorpay_client.order.create({
        "amount": total * 100,
        "currency": "INR",
        "payment_capture": "1"
    })

    order_id = razorpay_order["id"]

    return render_template(
        'payment.html',
        food="Cart Items",
        price=total,
        order_id=order_id,
        razorpay_key=os.getenv("RZP_KEY_ID")
    )

@app.route('/payment/<food>/<int:price>')
def payment(food, price):

    # create razorpay order
    order_amount = price * 100  # paisa
    order_currency = "INR"

    razorpay_order = razorpay_client.order.create({
        "amount": order_amount,
        "currency": order_currency,
        "payment_capture": "1"
    })

    order_id = razorpay_order["id"]

    return render_template(
        "payment.html",
        food=food,
        price=price,
        order_id=order_id,
        razorpay_key=os.getenv("RZP_KEY_ID")
    )
@app.route('/cod_payment/<food>/<int:price>', methods=['POST'])
def cod_payment(food, price):

    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    address = request.form.get('address') or "None"
    contact_no = request.form.get('contact_no') or "None"
    special_message = request.form.get('special_message') or "None"

    txn_id = "TXN" + str(random.randint(100000, 999999))

    cursor.execute("""
        INSERT INTO orders
        (user_id, food_name, price, payment_status, order_status, order_time,
        transaction_id, payment_mode, address, contact_no, special_message)
        VALUES (%s,%s,%s,%s,%s,NOW(),%s,%s,%s,%s,%s)
    """, (
        user_id,
        food,
        price,
        "Pending",
        "Pending",
        txn_id,
        "COD",
        address,
        contact_no,
        special_message
    ))

    db.commit()
    session.pop('cart', None)

    return render_template("success.html", txn_id=txn_id, mode="COD")

@app.route('/wallet_payment/<food>/<int:price>', methods=['POST'])
def wallet_payment(food, price):

    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    cursor.execute("SELECT wallet_balance FROM users WHERE id=%s", (user_id,))
    wallet = cursor.fetchone()[0]

    if wallet < price:
        flash("Insufficient wallet balance")
        return redirect('/checkout')

    cursor.execute(
        "UPDATE users SET wallet_balance = wallet_balance - %s WHERE id=%s",
        (price, user_id)
    )

    address = request.form.get('address') or "None"
    contact_no = request.form.get('contact_no') or "None"
    special_message = request.form.get('special_message') or "None"

    txn_id = "TXN" + str(random.randint(100000, 999999))

    cursor.execute("""
        INSERT INTO orders
        (user_id, food_name, price, payment_status, order_status, order_time,
        transaction_id, payment_mode, address, contact_no, special_message)
        VALUES (%s,%s,%s,%s,%s,NOW(),%s,%s,%s,%s,%s)
    """, (
        user_id,
        food,
        price,
        "Paid",
        "Pending",
        txn_id,
        "Wallet",
        address,
        contact_no,
        special_message
    ))

    db.commit()
    session.pop('cart', None)

    return render_template("success.html", txn_id=txn_id, mode="Wallet")
@app.route('/payment_success/<food>/<int:price>', methods=['POST'])
def payment_success(food, price):

    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    address = request.form.get('address') or "None"
    contact_no = request.form.get('contact_no') or "None"
    special_message = request.form.get('special_message') or "None"

    txn_id = "TXN" + str(random.randint(100000, 999999))

    # 🔴 ONLINE PAYMENT SUCCESS
    payment_mode = "Online"
    payment_status = "Paid"

    cursor.execute("""
        INSERT INTO orders
        (user_id, food_name, price, payment_status, order_status, order_time,
        transaction_id, payment_mode, address, contact_no, special_message)
        VALUES (%s,%s,%s,%s,%s,NOW(),%s,%s,%s,%s,%s)
    """, (
        user_id,
        food,
        price,
        payment_status,
        "Pending",
        txn_id,
        payment_mode,
        address,
        contact_no,
        special_message
    ))

    db.commit()
    session.pop('cart', None)

    return render_template("success.html", txn_id=txn_id, mode=payment_mode)

@app.route('/orders')
def user_orders():
    #check login
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    # FETCH WALLET BALANCE 
    cursor.execute(
        "SELECT wallet_balance FROM users WHERE id=%s",
        (user_id,)
    )
    wallet_balance = cursor.fetchone()[0]

    # FETCH ONLY THIS USER'S ORDERS
    cursor.execute("""
    SELECT
        o.id,               -- o[0]
        o.user_id,          -- o[1]
        o.food_name,        -- o[2]
        o.price,            -- o[3]
        o.payment_status,   -- o[4]
        o.order_status,     -- o[5]
        o.order_time,       -- o[6]
        o.transaction_id,   -- o[7]
        o.payment_mode,     -- o[8]
        o.refund_status,    -- o[9]
        o.rating,           -- o[10]
        o.feedback,         -- o[11]
        o.address,          -- o[12]
        o.contact_no,       -- o[13]
        o.special_message,  -- o[14]
        a.name              -- o[15] 
    FROM orders o
    LEFT JOIN delivery_agents a
        ON o.delivery_agent_id = a.id
    WHERE o.user_id = %s
    ORDER BY o.id DESC
""", (user_id,))

    orders = cursor.fetchall()

    # ✅ STEP 3: SEND BOTH TO TEMPLATE
    return render_template(
        "orders.html",
        orders=orders,
        wallet_balance=wallet_balance
    )

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    # user basic info
    cursor.execute(
        "SELECT name, email, wallet_balance FROM users WHERE id=%s",
        (user_id,)
    )
    user = cursor.fetchone()

    # total orders
    cursor.execute(
        "SELECT COUNT(*) FROM orders WHERE user_id=%s",
        (user_id,)
    )
    total_orders = cursor.fetchone()[0]

    # delivered orders
    cursor.execute(
        "SELECT COUNT(*) FROM orders WHERE user_id=%s AND order_status='Delivered'",
        (user_id,)
    )
    delivered_orders = cursor.fetchone()[0]

    # cancelled orders
    cursor.execute(
        "SELECT COUNT(*) FROM orders WHERE user_id=%s AND order_status='Cancelled'",
        (user_id,)
    )
    cancelled_orders = cursor.fetchone()[0]

    # total spent (only paid)
    cursor.execute(
        "SELECT SUM(price) FROM orders WHERE user_id=%s AND payment_status='Paid'",
        (user_id,)
    )
    total_spent = cursor.fetchone()[0] or 0

    # favourite food
    cursor.execute("""
    SELECT food_name, COUNT(*) as cnt
    FROM orders
    WHERE user_id=%s
    AND food_name IS NOT NULL
    AND food_name != 'Cart Items'
    GROUP BY food_name
    ORDER BY cnt DESC
    LIMIT 1
    """, (user_id,))

    fav = cursor.fetchone()

    if fav:
        favourite_food = fav[0]
    else:
        favourite_food = "NO ORDER YET"

    return render_template(
        'profile.html',
        user=user,
        total_orders=total_orders,
        delivered_orders=delivered_orders,
        cancelled_orders=cancelled_orders,
        total_spent=total_spent,
        favourite_food=favourite_food
    )

@app.route('/submit_feedback/<int:order_id>', methods=['POST'])
def submit_feedback(order_id):
    if 'user_id' not in session:
        return redirect('/login')

    rating = request.form.get('rating')
    feedback = request.form.get('feedback')

    cursor.execute("""
        UPDATE orders
        SET rating=%s, feedback=%s
        WHERE id=%s
    """, (rating, feedback, order_id))

    db.commit()

    return redirect('/orders')
@app.route('/user/cancel_order/<int:id>')
def user_cancel_order(id):

    cursor.execute("""
        SELECT user_id, price, payment_mode, payment_status, refund_status
        FROM orders WHERE id=%s
    """, (id,))
    order = cursor.fetchone()

    if not order:
        return redirect('/orders')

    user_id, price, payment_mode, payment_status, refund_status = order

    # if already refunded → stop
    if refund_status == "Refund Completed":
        flash("Refund already completed")
        return redirect('/orders')

    new_refund_status = "Not Applicable"

    # ONLINE → initiate refund only
    if payment_mode == "Online" and payment_status == "Paid":
        new_refund_status = "Refund Initiated"

    # WALLET → instant refund once
    elif payment_mode == "Wallet":
        cursor.execute("""
            UPDATE users SET wallet_balance = wallet_balance + %s
            WHERE id=%s
        """, (price, user_id))
        new_refund_status = "Refund Completed"

    cursor.execute("""
        UPDATE orders
        SET order_status='Cancelled',
            refund_status=%s
        WHERE id=%s
    """, (new_refund_status, id))

    db.commit()
    flash("Order cancelled")
    return redirect('/orders')


# ================= ADMIN SIDE =================

@app.route('/admin', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        cursor.execute(
            "SELECT * FROM admin WHERE username=%s AND password=%s",
            (u,p)
        )
        if cursor.fetchone():
            session['admin'] = True
            return redirect('/admin/dashboard')
    return render_template("admin_login.html")

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin' not in session:
        return redirect('/admin')

    cursor.execute("SELECT * FROM food")
    foods = cursor.fetchall()

    cursor.execute("""
        SELECT
            o.id, o.user_id, o.food_name, o.price, o.payment_status,
            o.order_status, o.order_time, o.transaction_id,
            o.payment_mode, o.refund_status, o.rating, o.feedback,
            o.address, o.contact_no, o.special_message,
            a.name
        FROM orders o
        LEFT JOIN delivery_agents a ON o.delivery_agent_id = a.id
        ORDER BY o.id DESC
    """)
    orders = cursor.fetchall()

    cursor.execute("SELECT * FROM delivery_agents")
    agents = cursor.fetchall()

    # analytics
    stats = db.cursor()
    stats.execute("SELECT COUNT(*) FROM orders")
    total_orders = stats.fetchone()[0]

    stats.execute("SELECT COUNT(*) FROM orders WHERE order_status='Delivered'")
    delivered_orders = stats.fetchone()[0]

    stats.execute("SELECT COUNT(*) FROM orders WHERE order_status='Cancelled'")
    cancelled_orders = stats.fetchone()[0]

    stats.execute("SELECT SUM(price) FROM orders WHERE payment_status='Paid'")
    revenue = stats.fetchone()[0] or 0

    stats.execute("SELECT COUNT(*) FROM orders WHERE payment_mode='COD'")
    cod_orders = stats.fetchone()[0]

    stats.execute("SELECT COUNT(*) FROM orders WHERE payment_mode IN ('UPI','Card')")
    online_orders = stats.fetchone()[0]

    stats.execute("SELECT COUNT(*) FROM orders WHERE order_status='Pending'")
    pending_orders = stats.fetchone()[0]

    stats.execute("SELECT COUNT(*) FROM orders WHERE order_status='Preparing'")
    preparing_orders = stats.fetchone()[0]

    stats.execute("SELECT COUNT(*) FROM orders WHERE order_status='Out for Delivery'")
    out_orders = stats.fetchone()[0]

    return render_template(
        "admin_dashboard.html",
        foods=foods,
        orders=orders,
        agents=agents,
        total_orders=total_orders,
        delivered_orders=delivered_orders,
        cancelled_orders=cancelled_orders,
        revenue=revenue,
        cod_orders=cod_orders,
        online_orders=online_orders,
        pending_orders=pending_orders,
        preparing_orders=preparing_orders,
        out_orders=out_orders
    )


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect('/admin')

@app.route('/admin/update_status/<int:id>/<status>')
def update_status(id, status):
    if 'admin' not in session:
        return redirect('/admin')

    cursor.execute(
        "UPDATE orders SET order_status=%s WHERE id=%s",
        (status, id)
    )
    db.commit()
    print(f"📱 SMS Sent: Order #{id} status updated to {status}")
    return redirect('/admin/dashboard')

@app.route('/admin/complete_refund/<int:order_id>')
def complete_refund(order_id):

    if 'admin' not in session:
        return redirect('/admin')

    cursor.execute("""
        SELECT user_id, price, refund_status
        FROM orders WHERE id=%s
    """, (order_id,))
    order = cursor.fetchone()

    if not order:
        return redirect('/admin/dashboard')

    user_id, price, refund_status = order

    # 🔴 IMPORTANT CHECK
    if refund_status != "Refund Initiated":
        flash("Refund already processed")
        return redirect('/admin/dashboard')

    # credit wallet ONCE
    cursor.execute("""
        UPDATE users
        SET wallet_balance = wallet_balance + %s
        WHERE id=%s
    """, (price, user_id))

    cursor.execute("""
        UPDATE orders
        SET refund_status='Refund Completed'
        WHERE id=%s
    """, (order_id,))

    db.commit()

    flash("Refund completed & wallet credited")
    return redirect('/admin/dashboard')

@app.route('/admin/cancel_order/<int:id>')
def admin_cancel_order(id):

    if 'admin' not in session:
        return redirect('/admin')

    cursor.execute("""
        SELECT user_id, price, payment_mode, payment_status, refund_status
        FROM orders WHERE id=%s
    """, (id,))
    order = cursor.fetchone()

    if not order:
        return redirect('/admin/dashboard')

    user_id, price, payment_mode, payment_status, refund_status = order

    # 🛑 IF ALREADY REFUNDED → STOP EVERYTHING
    if refund_status == "Refund Completed":
        flash("Refund already completed")
        return redirect('/admin/dashboard')

    new_refund_status = "Not Applicable"

    # ONLINE → initiate refund ONLY ONCE
    if payment_mode == "Online" and payment_status == "Paid":
        if refund_status != "Refund Completed":
            new_refund_status = "Refund Initiated"

    # WALLET → instant refund ONLY ONCE
    elif payment_mode == "Wallet":
        if refund_status != "Refund Completed":
            cursor.execute("""
                UPDATE users SET wallet_balance = wallet_balance + %s
                WHERE id=%s
            """, (price, user_id))
            new_refund_status = "Refund Completed"

    cursor.execute("""
        UPDATE orders
        SET order_status='Cancelled',
            refund_status=%s
        WHERE id=%s
    """, (new_refund_status, id))

    db.commit()
    flash("Order cancelled")
    return redirect('/admin/dashboard')

@app.route('/admin/mark_delivered/<int:id>')
def mark_delivered(id):
    cursor.execute("""
        UPDATE orders
        SET order_status = 'Delivered',
            payment_status = 
                CASE 
                    WHEN payment_mode = 'COD' THEN 'Paid'
                    ELSE payment_status
                END
        WHERE id = %s
    """, (id,))
    
    db.commit()
    return redirect('/admin/dashboard')

@app.route('/admin/add_food', methods=['POST'])
def add_food():
    if 'admin' not in session:
        return redirect('/admin')

    name = request.form['name']
    price = request.form['price']

    # INPUT VALIDATION
    if not name or not price:
        flash("Food name and price are required!")
        return redirect('/admin/dashboard')

    if not price.isdigit():
        flash("Price must be a number!")
        return redirect('/admin/dashboard')

    cursor.execute(
        "INSERT INTO food (name, price) VALUES (%s,%s)",
        (name, price)
    )
    db.commit()

    flash("Food added successfully!")
    return redirect('/admin/dashboard')

@app.route('/admin/delete/<int:id>')
def delete_food(id):
    cursor.execute("DELETE FROM food WHERE id=%s",(id,))
    db.commit()
    return redirect('/admin/dashboard')

@app.route('/admin/assign_agent/<int:order_id>', methods=['POST'])
def assign_agent(order_id):
    if 'admin' not in session:
        return redirect('/admin')

    agent_id = request.form.get('agent_id')

    if not agent_id:
        flash("Please select a delivery agent")
        return redirect('/admin/dashboard')

    agent_id = int(agent_id)

    cursor.execute("""
        UPDATE orders
        SET delivery_agent_id = %s,
            order_status = 'Preparing'
        WHERE id = %s
    """, (agent_id, order_id))

    db.commit()

    flash("Delivery agent assigned successfully")
    return redirect('/admin/dashboard')


@app.route('/agent/<int:agent_id>')
def agent_dashboard(agent_id):

    cursor.execute("""
        SELECT id, food_name, order_status
        FROM orders
        WHERE delivery_agent_id = %s
    """, (agent_id,))

    orders = cursor.fetchall()

    return render_template(
        "agent_dashboard.html",
        orders=orders
    )

@app.route('/agent/update/<int:order_id>/<status>')
def agent_update_status(order_id, status):

    ALLOWED_STATUSES = ['Preparing', 'Out for Delivery', 'Delivered']

    if status not in ALLOWED_STATUSES:
        return "Invalid status", 400

    cursor.execute("""
        UPDATE orders
        SET order_status=%s
        WHERE id=%s
        AND order_status != 'Delivered'
    """, (status, order_id))

    db.commit()

    # 🔹 redirect back to same order card
    return redirect(f"/agent/{request.args.get('agent_id')}#order{order_id}")

def auto_update_order_status():
    while True:
        try:
            now = datetime.now()

            # Pending → Preparing (after 2 minutes)
            cursor.execute("""
                UPDATE orders
                SET order_status = 'Preparing'
                WHERE order_status = 'Pending'
                AND order_time <= %s
            """, (now - timedelta(minutes=2),))

            # Preparing → Out for Delivery (after 3 more minutes)
            cursor.execute("""
                UPDATE orders
                SET order_status = 'Out for Delivery'
                WHERE order_status = 'Preparing'
                AND order_time <= %s
            """, (now - timedelta(minutes=5),))

            # Out for Delivery → Delivered (after 3 more minutes)
            cursor.execute("""
                UPDATE orders
                SET order_status = 'Delivered',
                    payment_status = CASE
                        WHEN payment_mode = 'COD' THEN 'Paid'
                        ELSE payment_status
                    END
                WHERE order_status = 'Out for Delivery'
                AND order_time <= %s
            """, (now - timedelta(minutes=8),))

            db.commit()

        except Exception as e:
            print("Auto status error:", e)

        time.sleep(60)  # run every 1 minute

if __name__ == "__main__":
    status_thread = threading.Thread(
        target=auto_update_order_status,
        daemon=True
    )
    status_thread.start()

    app.run(debug=True, use_reloader=False)