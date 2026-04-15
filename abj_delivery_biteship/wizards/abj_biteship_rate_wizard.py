# -*- coding: utf-8 -*-
"""
Biteship Rate Selection Wizard
===============================
Wizard to display and select shipping rates fetched from Biteship API.
User selects one rate option; on confirm, writes back to the sale.order.
"""
import logging

from odoo import fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AbjBiteshipRateWizard(models.TransientModel):
    _name = 'abj.biteship.rate.wizard'
    _description = 'Wizard Pilih Tarif Biteship'

    abj_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        required=True,
        ondelete='cascade',
    )
    abj_line_ids = fields.One2many(
        'abj.biteship.rate.line',
        'abj_wizard_id',
        string='Opsi Tarif',
    )

    def action_abj_select_rate(self):
        """
        Apply the selected rate to the parent sale.order.
        Writes courier, service, cost, and duration fields.
        """
        self.ensure_one()
        selected = self.abj_line_ids.filtered(lambda l: l.abj_selected)
        if not selected:
            raise UserError('Pilih salah satu tarif pengiriman terlebih dahulu.')
        if len(selected) > 1:
            raise UserError('Hanya boleh memilih satu tarif. Silakan centang satu saja.')

        line = selected[0]
        self.abj_order_id.write({
            'abj_shipping_cost': line.abj_price,
            'abj_selected_courier': line.abj_courier_name,
            'abj_selected_courier_code': line.abj_courier_code,
            'abj_selected_service': line.abj_service_code,
            'abj_selected_service_name': line.abj_service_name,
            'abj_shipping_duration': line.abj_duration,
        })

        _logger.info(
            "ABJ_BITESHIP: Rate selected for SO %s → %s %s @ Rp %s",
            self.abj_order_id.name,
            line.abj_courier_name,
            line.abj_service_name,
            line.abj_price,
        )

        return {'type': 'ir.actions.act_window_close'}

    def action_abj_select_cheapest(self):
        """
        Auto-select the cheapest rate option.
        Quick action button in the wizard.
        """
        self.ensure_one()
        if not self.abj_line_ids:
            raise UserError('Tidak ada tarif yang tersedia.')

        cheapest = min(self.abj_line_ids, key=lambda l: l.abj_price)

        # Deselect all, then select cheapest
        self.abj_line_ids.write({'abj_selected': False})
        cheapest.abj_selected = True

        # Auto-apply
        return self.action_abj_select_rate()


class AbjBiteshipRateLine(models.TransientModel):
    _name = 'abj.biteship.rate.line'
    _description = 'Baris Tarif Biteship'
    _order = 'abj_price asc'

    abj_wizard_id = fields.Many2one(
        'abj.biteship.rate.wizard',
        string='Wizard',
        ondelete='cascade',
    )
    abj_selected = fields.Boolean(
        string='Pilih',
        default=False,
    )
    abj_courier_name = fields.Char(
        string='Kurir',
        readonly=True,
    )
    abj_courier_code = fields.Char(
        string='Kode Kurir',
        readonly=True,
    )
    abj_service_name = fields.Char(
        string='Layanan',
        readonly=True,
    )
    abj_service_code = fields.Char(
        string='Kode Layanan',
        readonly=True,
    )
    abj_service_type = fields.Char(
        string='Tipe',
        readonly=True,
    )
    abj_price = fields.Float(
        string='Harga (Rp)',
        readonly=True,
    )
    abj_shipping_fee = fields.Float(
        string='Ongkir',
        readonly=True,
    )
    abj_duration = fields.Char(
        string='Estimasi',
        readonly=True,
    )
    abj_description = fields.Char(
        string='Deskripsi',
        readonly=True,
    )
    abj_insurance_fee = fields.Float(
        string='Asuransi',
        readonly=True,
    )
