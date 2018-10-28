==========================================
Stock Shipment External Reception Scenario
==========================================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> today = datetime.date.today()
    >>> yesterday = today - relativedelta(days=1)

Activate stock_external_reception::

    >>> config = activate_modules('stock_external_reception')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create stock user::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> stock_user = User()
    >>> stock_user.name = 'Stock'
    >>> stock_user.login = 'stock'
    >>> stock_user.main_company = company
    >>> stock_group, = Group.find([('name', '=', 'Stock')])
    >>> stock_user.groups.append(stock_group)
    >>> stock_user.save()

Create reception user::

    >>> reception_user = User()
    >>> reception_user.name = 'Reception'
    >>> reception_user.login = 'reception'
    >>> reception_user.main_company = company
    >>> reception_group, = Group.find([('name', '=', 'Stock External Reception')])
    >>> reception_user.groups.append(reception_group)
    >>> reception_user.save()

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20')
    >>> template.cost_price = Decimal('8')
    >>> template.save()
    >>> product.template = template
    >>> product.save()

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])

Recieve products from customer::

    >>> config.user = reception_user.id
    >>> Reception = Model.get('stock.external.reception')
    >>> ReceptionLine = Model.get('stock.external.reception.line')
    >>> reception = Reception()
    >>> reception.reference = '1234'
    >>> reception.party = customer
    >>> line = reception.lines.new()
    >>> line.description = 'Test product'
    >>> line.quantity = 1
    >>> reception.click('receive')
    >>> reception.click('done')    # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    UserError: ('UserError', ('Calling button done on stock.external.reception is not allowed!', ''))

Create external shipment from received products::

    >>> config.user = stock_user.id
    >>> Reception = Model.get('stock.external.reception')
    >>> reception = Reception(reception.id)
    >>> reception.click('done')    # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    UserError: ('UserError', (u'Missing product on Line "Test product" of reception "1".', ''))
    >>> line, = reception.lines
    >>> line.product = product
    >>> reception.click('done')
    >>> shipment, = reception.shipments
    >>> shipment.party == reception.party
    True
    >>> shipment.state
    u'done'
    >>> shipment.effective_date == reception.effective_date
    True
    >>> move, = shipment.moves
    >>> move.state
    u'done'
    >>> move.product == product
    True
    >>> move.quantity == 1.0
    True
    >>> move.uom == unit
    True
    >>> move.from_location == customer.customer_location
    True
    >>> move.to_location == storage_loc
    True
