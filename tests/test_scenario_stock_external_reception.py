import unittest
from decimal import Decimal

from proteus import Model
from trytond.exceptions import UserError
from trytond.model.modelview import AccessButtonError
from trytond.modules.company.tests.tools import create_company
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        # Activate stock_external_reception
        config = activate_modules('stock_external_reception')

        # Create company
        _ = create_company()

        # Create stock user
        User = Model.get('res.user')
        Group = Model.get('res.group')
        stock_user = User()
        stock_user.name = 'Stock'
        stock_user.login = 'stock'
        stock_group, = Group.find([('name', '=', 'Stock')])
        stock_user.groups.append(stock_group)
        stock_user.save()

        # Create reception user
        reception_user = User()
        reception_user.name = 'Reception'
        reception_user.login = 'reception'
        reception_group, = Group.find([('name', '=', 'Stock External Reception')
                                       ])
        reception_user.groups.append(reception_group)
        reception_user.save()

        # Create customer
        Party = Model.get('party.party')
        customer = Party(name='Customer')
        customer.save()

        # Create product
        ProductUom = Model.get('product.uom')
        ProductTemplate = Model.get('product.template')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        template = ProductTemplate()
        template.name = 'Product'
        template.default_uom = unit
        template.type = 'goods'
        template.list_price = Decimal('20')
        template.save()
        product, = template.products
        product.save()

        # Get stock locations
        Location = Model.get('stock.location')
        storage_loc, = Location.find([('code', '=', 'STO')])

        # Recieve products from customer
        config.user = reception_user.id
        Reception = Model.get('stock.external.reception')
        reception = Reception()
        reception.reference = '1234'
        reception.party = customer
        line = reception.lines.new()
        line.description = 'Test product'
        line.quantity = 1
        reception.click('receive')

        with self.assertRaises(AccessButtonError):
            reception.click('done')

        # Create external shipment from received products
        config.user = stock_user.id
        Reception = Model.get('stock.external.reception')
        reception = Reception(reception.id)

        with self.assertRaises(UserError):
            reception.click('done')

        line, = reception.lines
        line.product = product
        reception.click('done')
        shipment, = reception.shipments
        self.assertEqual(shipment.party, reception.party)
        self.assertEqual(shipment.state, 'done')
        self.assertEqual(shipment.effective_date, reception.effective_date)

        move, = shipment.moves
        self.assertEqual(move.state, 'done')
        self.assertEqual(move.product, product)
        self.assertEqual(move.quantity, 1.0)
        self.assertEqual(move.uom, unit)
        self.assertEqual(move.from_location, customer.customer_location)
        self.assertEqual(move.to_location, storage_loc)
