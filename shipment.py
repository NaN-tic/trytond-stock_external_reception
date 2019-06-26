#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import Workflow, ModelSQL, ModelView, fields
from trytond.pyson import Eval, If, In, Bool
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.i18n import gettext
from trytond.exceptions import UserError


__all__ = ['Configuration', 'ConfigurationSequence', 'ExternalReception',
    'ExternalReceptionLine', 'ShipmentExternal']

_STATES = {
    'readonly': Eval('state') != 'draft',
    }
_DEPENDS = ['state']


class Configuration(metaclass=PoolMeta):
    __name__ = 'stock.configuration'
    external_reception_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "External Reception Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'stock.external.reception'),
                ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'external_reception_sequence':
            return pool.get('stock.configuration.sequence')
        return super(Configuration, cls).multivalue_model(field)

    @staticmethod
    def default_external_reception_sequence(**pattern):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        return ModelData.get_id('stock_external_reception',
            'sequence_external_reception')


class ConfigurationSequence(metaclass=PoolMeta):
    __name__ = 'stock.configuration.sequence'
    external_reception_sequence = fields.Many2One(
        'ir.sequence', "External Reception Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('code', '=', 'stock.external.reception'),
            ],
        depends=['company'])


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
    notes = fields.Text('Notes')
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
                    raise UserError(
                        gettext('stock_external_reception.missing_product',
                            line=line.rec_name,
                            shipment=reception.rec_name))
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

    @classmethod
    def copy(cls, receptions, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default['shipments'] = None
        return super(ExternalReception, cls).copy(receptions, default=default)



class ExternalReceptionLine(ModelSQL, ModelView):
    "External Reception Line"
    __name__ = 'stock.external.reception.line'
    _rec_name = 'description'
    reception = fields.Many2One('stock.external.reception', 'Reception',
        ondelete='CASCADE', select=True)
    sequence = fields.Integer('Sequence')
    description = fields.Text('Description', required=True)
    product = fields.Many2One('product.product', 'Product')
    product_uom_category = fields.Function(
        fields.Many2One('product.uom.category', 'Product Uom Category'),
        'on_change_with_product_uom_category')
    quantity = fields.Float('Quantity',
        digits=(16, Eval('unit_digits', 2)),
        depends=['unit_digits'])
    unit = fields.Many2One('product.uom', 'Unit',
        states={
            'required': Bool(Eval('product', 0)),
            },
        domain=[
            If(Bool(Eval('product_uom_category')),
                ('category', '=', Eval('product_uom_category')),
                ('category', '!=', -1)),
            ],
        depends=['product_uom_category', 'product'])
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'on_change_with_unit_digits')
    notes = fields.Text('Notes')

    @fields.depends('product', 'unit', 'description')
    def on_change_product(self):
        if self.product:
            category = self.product.default_uom.category
            if not self.unit or self.unit not in category.uoms:
                self.unit = self.product.default_uom
                self.unit_digits = self.product.default_uom.digits
            if not self.description:
                self.description = self.product.rec_name

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


class ShipmentExternal(metaclass=PoolMeta):
    __name__ = 'stock.shipment.external'

    reception = fields.Many2One('stock.external.reception',
        'External Reception', readonly=True)
