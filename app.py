from flask import Flask, render_template, request, session, redirect, url_for, flash
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'pos_demo_secret_key_2024'  # For session management

# Sample data - will be moved to models later
PRODUCTS = [
    {'id': 1, 'name': '珍珠奶茶', 'price': 50, 'category': '飲料', 'stock': 20},
    {'id': 2, 'name': '紅茶', 'price': 25, 'category': '飲料', 'stock': 30},
    {'id': 3, 'name': '美式咖啡', 'price': 45, 'category': '飲料', 'stock': 15},
    {'id': 4, 'name': '巧克力蛋糕', 'price': 80, 'category': '點心', 'stock': 10},
    {'id': 5, 'name': '薯條', 'price': 60, 'category': '點心', 'stock': 25},
    {'id': 6, 'name': '洋芋片', 'price': 35, 'category': '零食', 'stock': 40},
]

MEMBERS = [
    {'id': 'M001', 'name': '張小明', 'level': '金卡', 'points': 1500, 'discount': 0.1},
    {'id': 'M002', 'name': '李小華', 'level': '銀卡', 'points': 800, 'discount': 0.05},
    {'id': 'M003', 'name': '王大明', 'level': '普通', 'points': 200, 'discount': 0.0},
]

@app.route('/')
def home():
    """Home page - display products and cart summary"""
    cart = session.get('cart', {})
    cart_items = []
    cart_total = 0

    for product_id, quantity in cart.items():
        product = next((p for p in PRODUCTS if p['id'] == int(product_id)), None)
        if product:
            subtotal = product['price'] * quantity
            cart_items.append({
                'product': product,
                'quantity': quantity,
                'subtotal': subtotal
            })
            cart_total += subtotal

    return render_template('index.html',
                         products=PRODUCTS,
                         cart_items=cart_items,
                         cart_total=cart_total,
                         member=session.get('member'))

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    """Add product to cart"""
    quantity = int(request.form.get('quantity', 1))
    cart = session.get('cart', {})

    if str(product_id) in cart:
        cart[str(product_id)] += quantity
    else:
        cart[str(product_id)] = quantity

    session['cart'] = cart
    flash('商品已加入購物車', 'success')
    return redirect(url_for('home'))

@app.route('/update_cart/<int:product_id>', methods=['POST'])
def update_cart(product_id):
    """Update cart item quantity"""
    action = request.form.get('action')
    cart = session.get('cart', {})

    if str(product_id) in cart:
        if action == 'increase':
            cart[str(product_id)] += 1
        elif action == 'decrease':
            cart[str(product_id)] -= 1
            if cart[str(product_id)] <= 0:
                del cart[str(product_id)]
        elif action == 'remove':
            del cart[str(product_id)]

    session['cart'] = cart
    return redirect(url_for('cart'))

@app.route('/cart')
def cart():
    """Cart page"""
    cart = session.get('cart', {})
    cart_items = []
    cart_total = 0
    member_discount = 0

    for product_id, quantity in cart.items():
        product = next((p for p in PRODUCTS if p['id'] == int(product_id)), None)
        if product:
            subtotal = product['price'] * quantity
            cart_items.append({
                'product': product,
                'quantity': quantity,
                'subtotal': subtotal
            })
            cart_total += subtotal

    # Apply member discount if member is logged in
    member = session.get('member')
    if member:
        member_discount = cart_total * member['discount']

    final_total = cart_total - member_discount

    return render_template('cart.html',
                         cart_items=cart_items,
                         cart_total=cart_total,
                         member_discount=member_discount,
                         final_total=final_total,
                         member=member)

@app.route('/member', methods=['GET', 'POST'])
def member():
    """Member login page"""
    if request.method == 'POST':
        member_id = request.form.get('member_id')
        member = next((m for m in MEMBERS if m['id'] == member_id), None)

        if member:
            session['member'] = member
            flash(f'歡迎 {member["name"]} 會員！', 'success')
            return redirect(url_for('home'))
        else:
            flash('會員編號不存在', 'error')

    return render_template('member.html', members=MEMBERS)

@app.route('/logout')
def logout():
    """Logout member"""
    session.pop('member', None)
    flash('已登出', 'info')
    return redirect(url_for('home'))

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    """Checkout page"""
    cart = session.get('cart', {})

    if not cart:
        flash('購物車是空的', 'warning')
        return redirect(url_for('home'))

    cart_items = []
    cart_total = 0

    for product_id, quantity in cart.items():
        product = next((p for p in PRODUCTS if p['id'] == int(product_id)), None)
        if product:
            subtotal = product['price'] * quantity
            cart_items.append({
                'product': product,
                'quantity': quantity,
                'subtotal': subtotal
            })
            cart_total += subtotal

    member = session.get('member')
    member_discount = 0

    if member:
        member_discount = cart_total * member['discount']

    # Apply bulk discount (滿500打9折)
    bulk_discount = 0
    if cart_total >= 500:
        bulk_discount = cart_total * 0.1

    final_total = cart_total - member_discount - bulk_discount

    if request.method == 'POST':
        payment_method = request.form.get('payment_method')

        # Update inventory
        for product_id, quantity in cart.items():
            product = next((p for p in PRODUCTS if p['id'] == int(product_id)), None)
            if product:
                product['stock'] -= quantity
                if product['stock'] < 0:
                    product['stock'] = 0

        # Clear cart
        session.pop('cart', None)

        return redirect(url_for('receipt', payment_method=payment_method))

    return render_template('checkout.html',
                         cart_items=cart_items,
                         cart_total=cart_total,
                         member_discount=member_discount,
                         bulk_discount=bulk_discount,
                         final_total=final_total,
                         member=member)

@app.route('/receipt')
def receipt():
    """Receipt page"""
    payment_method = request.args.get('payment_method', '現金')
    return render_template('receipt.html', payment_method=payment_method)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
