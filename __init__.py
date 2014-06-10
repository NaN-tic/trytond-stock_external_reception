# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .shipment import *


def register():
    Pool.register(
        ExternalReception,
        ExternalReceptionLine,
        ShipmentExternal,
        module='stock_external_reception', type_='model')
