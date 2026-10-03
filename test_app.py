import unittest

import app as pos


class POSCheckoutTests(unittest.TestCase):
    def setUp(self):
        self.original_products = [product.copy() for product in pos.PRODUCTS]
        self.original_members = [member.copy() for member in pos.MEMBERS]
        self.client = pos.app.test_client()

    def tearDown(self):
        pos.PRODUCTS[:] = [product.copy() for product in self.original_products]
        pos.MEMBERS[:] = [member.copy() for member in self.original_members]

    def set_cart(self, cart, member=None):
        with self.client.session_transaction() as session:
            session['cart'] = cart
            if member:
                session['member'] = member

    def test_checkout_calculates_same_rounded_discounts(self):
        order = pos.build_order({'1': 10}, pos.MEMBERS[0])
        self.assertEqual(order['cart_total'], 500)
        self.assertEqual(order['member_discount'], 50)
        self.assertEqual(order['bulk_discount'], 50)
        self.assertEqual(order['final_total'], 400)

    def test_home_cart_summary_matches_checkout_amounts(self):
        self.set_cart({'1': 10}, pos.MEMBERS[0])
        home = self.client.get('/')
        cart = self.client.get('/cart')
        self.assertIn('應付金額:'.encode(), home.data)
        self.assertIn('總計:'.encode(), cart.data)
        self.assertIn('NT$ 400'.encode(), home.data)
        self.assertIn('NT$ 400'.encode(), cart.data)
        self.assertIn('-NT$ 50'.encode(), home.data)
        self.assertIn('-NT$ 50'.encode(), cart.data)

    def test_payment_creates_receipt_and_decrements_stock_once(self):
        self.set_cart({'1': 2}, pos.MEMBERS[0])
        starting_points = pos.MEMBERS[0]['points']
        response = self.client.post('/checkout', data={'payment_method': '信用卡'})
        self.assertEqual(response.status_code, 302)
        receipt_url = response.headers['Location']
        self.assertIn('order_id=', receipt_url)
        self.assertEqual(pos.PRODUCTS[0]['stock'], 18)

        receipt = self.client.get(receipt_url)
        self.assertEqual(receipt.status_code, 200)
        self.assertIn('珍珠奶茶'.encode(), receipt.data)
        self.assertIn('信用卡'.encode(), receipt.data)
        self.assertIn('交易編號'.encode(), receipt.data)
        self.assertNotIn(b'moment()', receipt.data)
        self.assertEqual(self.client.get(receipt_url).status_code, 200)
        self.assertEqual(pos.PRODUCTS[0]['stock'], 18)
        self.assertEqual(pos.MEMBERS[0]['points'], starting_points + 9)

    def test_checkout_rejects_invalid_payment_without_changing_stock(self):
        self.set_cart({'1': 1}, pos.MEMBERS[0])
        starting_points = pos.MEMBERS[0]['points']
        response = self.client.post('/checkout', data={'payment_method': '未支援'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(pos.PRODUCTS[0]['stock'], 20)
        self.assertEqual(pos.MEMBERS[0]['points'], starting_points)
        with self.client.session_transaction() as session:
            self.assertEqual(session['cart'], {'1': 1})
            self.assertNotIn('last_order', session)

    def test_checkout_rejects_stale_cart_when_stock_is_insufficient(self):
        self.set_cart({'1': 2})
        pos.PRODUCTS[0]['stock'] = 1
        response = self.client.post('/checkout', data={'payment_method': '現金'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(pos.PRODUCTS[0]['stock'], 1)
        with self.client.session_transaction() as session:
            self.assertEqual(session['cart'], {'1': 2})
            self.assertNotIn('last_order', session)

    def test_add_to_cart_rejects_invalid_and_over_stock_quantities(self):
        self.client.post('/add_to_cart/1', data={'quantity': '0'})
        self.client.post('/add_to_cart/1', data={'quantity': '21'})
        with self.client.session_transaction() as session:
            self.assertNotIn('cart', session)

    def test_receipt_requires_matching_completed_order(self):
        response = self.client.get('/receipt?payment_method=現金')
        self.assertEqual(response.status_code, 302)


if __name__ == '__main__':
    unittest.main()
