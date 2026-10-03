from flask import Flask, render_template, request, session, redirect, url_for, flash
from datetime import datetime
import os
from threading import Lock
from uuid import uuid4

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY') or os.urandom(32)

PAYMENT_METHODS = {'現金', '信用卡', '行動支付'}
INVENTORY_LOCK = Lock()

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


def build_order(cart, member=None):
    """Build a validated cart summary using current product and stock data."""
    items = []
    cart_total = 0

    for product_id, quantity in cart.items():
        product = next((p for p in PRODUCTS if p['id'] == int(product_id)), None)
        if product and quantity > 0:
            items.append({
                'product': product.copy(),
                'quantity': quantity,
                'subtotal': product['price'] * quantity,
            })
            cart_total += product['price'] * quantity

    member_discount = int(cart_total * member['discount']) if member else 0
    bulk_discount = int(cart_total * 0.1) if cart_total >= 500 else 0
    return {
        'cart_items': items,
        'cart_total': cart_total,
        'member_discount': member_discount,
        'bulk_discount': bulk_discount,
        'final_total': max(0, cart_total - member_discount - bulk_discount),
    }

@app.route('/')
def home():
    """Home page - display products and cart summary"""
    cart = session.get('cart', {})
    member = session.get('member')
    order = build_order(cart, member)

    return render_template('index.html',
                          products=PRODUCTS,
                          **order,
                          member=member)

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    """Add product to cart"""
    try:
        quantity = int(request.form.get('quantity', 1))
    except (TypeError, ValueError):
        flash('商品數量格式錯誤', 'error')
        return redirect(url_for('home'))

    product = next((p for p in PRODUCTS if p['id'] == product_id), None)
    if not product or quantity < 1:
        flash('商品或數量無效', 'error')
        return redirect(url_for('home'))

    cart = session.get('cart', {})
    new_quantity = cart.get(str(product_id), 0) + quantity
    if new_quantity > product['stock']:
        flash(f'{product["name"]} 庫存不足，目前庫存 {product["stock"]} 件', 'warning')
        return redirect(url_for('home'))
    cart[str(product_id)] = new_quantity

    session['cart'] = cart
    flash('商品已加入購物車', 'success')
    return redirect(url_for('home'))

@app.route('/update_cart/<int:product_id>', methods=['POST'])
def update_cart(product_id):
    """Update cart item quantity"""
    action = request.form.get('action')
    cart = session.get('cart', {})
    product = next((p for p in PRODUCTS if p['id'] == product_id), None)

    if str(product_id) in cart:
        if action == 'increase':
            if product and cart[str(product_id)] < product['stock']:
                cart[str(product_id)] += 1
            else:
                flash('已達商品庫存上限', 'warning')
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
    member = session.get('member')
    order = build_order(cart, member)

    return render_template('cart.html',
                         **order,
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

    member = session.get('member')
    order = build_order(cart, member)

    if request.method == 'POST':
        payment_method = request.form.get('payment_method')
        if payment_method not in PAYMENT_METHODS:
            flash('付款方式無效，請重新選擇', 'error')
            return redirect(url_for('checkout'))

        with INVENTORY_LOCK:
            for item in order['cart_items']:
                product = next(p for p in PRODUCTS if p['id'] == item['product']['id'])
                if item['quantity'] > product['stock']:
                    flash(f'{product["name"]} 庫存不足，請調整購物車', 'warning')
                    return redirect(url_for('cart'))

            for item in order['cart_items']:
                product = next(p for p in PRODUCTS if p['id'] == item['product']['id'])
                product['stock'] -= item['quantity']
                item['product']['stock'] = product['stock']

        order.update({
            'id': uuid4().hex[:8].upper(),
            'created_at': datetime.now().strftime('%Y年%m月%d日 %H:%M:%S'),
            'payment_method': payment_method,
            'member': member.copy() if member else None,
        })
        if member:
            points_earned = order['final_total'] // 10
            stored_member = next(m for m in MEMBERS if m['id'] == member['id'])
            stored_member['points'] += points_earned
            order['member']['points'] = stored_member['points']
            order['points_earned'] = points_earned
        session['last_order'] = order

        # Clear cart
        session.pop('cart', None)

        return redirect(url_for('receipt', order_id=order['id']))

    return render_template('checkout.html', **order, member=member)

@app.route('/receipt')
def receipt():
    """Receipt page"""
    order = session.get('last_order')
    if not order or request.args.get('order_id') != order['id']:
        flash('找不到此筆交易收據', 'warning')
        return redirect(url_for('home'))
    return render_template('receipt.html', **order)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
