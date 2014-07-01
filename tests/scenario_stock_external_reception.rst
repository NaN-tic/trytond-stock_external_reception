==========================================
Stock Shipment External Reception Scenario
==========================================

=============
General Setup
=============

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> today = datetime.date.today()
    >>> yesterday = today - relativedelta(days=1)

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install stock Module::

    >>> Module = Model.get('ir.module.module')
    >>> modules = Module.find([('name', '=', 'stock_external_reception')])
    >>> Module.install([x.id for x in modules], config.context)
    >>> Wizard('ir.module.module.install_upgrade').execute('upgrade')

Create company::

    >>> Currency = Model.get('currency.currency')
    >>> CurrencyRate = Model.get('currency.currency.rate')
    >>> Company = Model.get('company.company')
    >>> Party = Model.get('party.party')
    >>> company_config = Wizard('company.company.config')
    >>> company_config.execute('company')
    >>> company = company_config.form
    >>> party = Party(name='OPENLABS')
    >>> party.save()
    >>> company.party = party
    >>> currencies = Currency.find([('code', '=', 'EUR')])
    >>> if not currencies:
    ...     currency = Currency(name='Euro', symbol=u'€', code='EUR',
    ...         rounding=Decimal('0.01'), mon_grouping='[3, 3, 0]',
    ...         mon_decimal_point=',')
    ...     currency.save()
    ...     CurrencyRate(date=today + relativedelta(month=1, day=1),
    ...         rate=Decimal('1.0'), currency=currency).save()
    ... else:
    ...     currency, = currencies
    >>> company.currency = currency
    >>> company_config.execute('add')
    >>> company, = Company.find()

Reload the context::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> config._context = User.get_preferences(True, config.context)

Create stock user::

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
    >>> reception.click('done')
    Traceback (most recent call last):
        ...
    UserError: ('UserError', ('Calling button done on stock.external.reception is not allowed!', ''))

Create external shipment from received products::

    >>> config.user = stock_user.id
    >>> Reception = Model.get('stock.external.reception')
    >>> reception = Reception(reception.id)
    >>> reception.click('done')
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
    >>> move.from_location == party.customer_location
    True
    >>> move.to_location == storage_loc
    True
