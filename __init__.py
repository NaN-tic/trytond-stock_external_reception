# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import shipment

def register():
    Pool.register(
        shipment.Configuration,
        shipment.ConfigurationSequence,
        shipment.ExternalReception,
        shipment.ExternalReceptionLine,
        shipment.ShipmentExternal,
        module='stock_external_reception', type_='model')
