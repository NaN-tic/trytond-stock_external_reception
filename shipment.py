#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import Workflow, ModelSQL, ModelView, fields
from trytond.pyson import Eval, If, In, Bool, Id
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__all__ = ['Configuration', 'ExternalReception', 'ExternalReceptionLine',
    'ShipmentExternal']
__metaclass__ = PoolMeta

_STATES = {
    'readonly': Eval('state') != 'draft',
    }
_DEPENDS = ['state']


class Configuration:
    __name__ = 'stock.configuration'
    external_reception_sequence = fields.Property(fields.Many2One(
            'ir.sequence', 'External reception Sequence', domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'stock.external.reception'),
                ], required=True))


class ExternalReception(Workflow, ModelSQL, ModelView):
    "External Reception"
    __name__ = 'stock.external.reception'
    _rec_name = 'code'
    code = fields.Char("Code", size=None, select=True, readonly=True)
    company = fields.Many2One('company.company', 'Company', required=True,
        states=_STATES, depends=_DEPENDS,
        domain=[
            ('id', If(In('company', Eval('context', {})), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ])
    party = fields.Many2One('party.party', 'Party', required=True,
        states=_STATES, depends=_DEPENDS)
    reference = fields.Char("Reference", size=None, select=True,
        states=_STATES, depends=_DEPENDS)
    warehouse = fields.Many2One('stock.location', "Warehouse",
        required=True, domain=[('type', '=', 'warehouse')],
        states=_STATES, depends=_DEPENDS)
    effective_date = fields.Date('Effective Date', required=True,
        states=_STATES, depends=_DEPENDS)
    lines = fields.One2Many('stock.external.reception.line', 'reception',
        'Lines', states={
            'readonly': ~Eval('state').in_(['draft', 'received']),
            },
        depends=_DEPENDS)
    shipments = fields.One2Many('stock.shipment.external', 'reception',
        'External Shipments', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('received', 'Received'),
        ('done', 'Done'),
        ], 'State', readonly=True)

    @classmethod
    def __setup__(cls):
        super(ExternalReception, cls).__setup__()
        cls._order[0] = ('id', 'DESC')
        cls._transitions |= set((
                ('draft', 'received'),
                ('received', 'draft'),
                ('received', 'done'),
                ))
        cls._error_messages.update({
                'missing_product': ('Missing product on Line "%s" of reception'
                    ' "%s".'),
                })
        cls._buttons.update({
                'draft': {
                    'invisible': Eval('state') != 'received',
                    'icon': 'tryton-go-previous',
                    },
                'receive': {
                    'invisible': Eval('state') != 'draft',
                    'icon': 'tryton-go-next',
                    },
                'done': {
                    'invisible': Eval('state') != 'received',
                    'icon': 'tryton-ok',
                    'readonly': ~Eval('groups', []).contains(
                        Id('stock', 'group_stock')),
                    },
                })

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @classmethod
    def default_warehouse(cls):
        Location = Pool().get('stock.location')
        locations = Location.search(cls.warehouse.domain)
        if len(locations) == 1:
            return locations[0].id

    @staticmethod
    def default_effective_date():
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, receptions):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('received')
    def receive(cls, receptions):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, receptions):
        pool = Pool()
        Shipment = pool.get('stock.shipment.external')
        to_create = []
        for reception in receptions:
            shipment = reception._get_shipment()
            shipment.reception = reception
            moves = []
            for line in reception.lines:
                if not line.product:
                    cls.raise_user_error('missing_product', (line.rec_name,
                            reception.rec_name))
                move = line._get_move()
                move.to_location = shipment.to_location
                move.from_location = shipment.from_location
                moves.append(move._save_values)
            shipment.moves = moves
            vals = shipment._save_values
            vals['moves'] = [('create', moves)]
            to_create.append(vals)
        if to_create:
            with Transaction().set_user(0):
                shipments = Shipment.create(to_create)
                Shipment.wait(shipments)
                Shipment.assign_force(shipments)
                Shipment.done(shipments)

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('stock.configuration')

        vlist = [x.copy() for x in vlist]
        config = Config(1)
        for values in vlist:
            values['code'] = Sequence.get_id(
                config.external_reception_sequence.id)
        shipments = super(ExternalReception, cls).create(vlist)
        return shipments

    def _get_shipment(self):
        'Return the shipment to be generated by the external reception'
        pool = Pool()
        Shipment = pool.get('stock.shipment.external')
        shipment = Shipment()
        shipment.company = self.company
        shipment.effective_date = self.effective_date
        shipment.party = self.party
        shipment.reference = self.rec_name
        shipment.from_location = self.party.customer_location
        shipment.to_location = self.warehouse.storage_location
        return shipment


class ExternalReceptionLine(ModelSQL, ModelView):
    "External Reception Line"
    __name__ = 'stock.external.reception.line'
    _rec_name = 'description'
    reception = fields.Many2One('stock.external.reception', 'Reception',
        ondelete='CASCADE', select=True)
    sequence = fields.Integer('Sequence')
    description = fields.Text('Description', size=None, required=True)
    product = fields.Many2One('product.product', 'Product')
    product_uom_category = fields.Function(
        fields.Many2One('product.uom.category', 'Product Uom Category'),
        'on_change_with_product_uom_category')
    quantity = fields.Float('Quantity',
        digits=(16, Eval('unit_digits', 2)),
        depends=['unit_digits'])
    unit = fields.Many2One('product.uom', 'Unit',
        domain=[
            If(Bool(Eval('product_uom_category')),
                ('category', '=', Eval('product_uom_category')),
                ('category', '!=', -1)),
            ],
        depends=['product_uom_category'])
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'on_change_with_unit_digits')

    @fields.depends('unit')
    def on_change_with_unit_digits(self, name=None):
        if self.unit:
            return self.unit.digits
        return 2

    @fields.depends('product')
    def on_change_with_product_uom_category(self, name=None):
        if self.product:
            return self.product.default_uom_category.id

    def _get_move(self):
        'Return the move to be generated by the external line'
        pool = Pool()
        Move = pool.get('stock.move')
        move = Move()
        move.product = self.product
        move.quantity = self.quantity
        move.uom = self.unit
        move.company = self.reception.company
        move.effective_date = self.reception.effective_date
        move.state = 'draft'
        return move


class ShipmentExternal:
    __name__ = 'stock.shipment.external'

    reception = fields.Many2One('stock.external.reception',
        'External Reception', readonly=True)
