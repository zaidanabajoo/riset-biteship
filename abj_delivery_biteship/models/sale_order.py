# -*- coding: utf-8 -*-
"""
Sale Order Extension for Biteship
==================================
Adds shipping rate fields and "Get Shipping Rates" button
to the Sale Order form.
"""
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ── Biteship Shipping Fields ─────────────────────────────────────────
    abj_shipping_cost = fields.Float(
        string='Ongkos Kirim (Biteship)',
        copy=False,
        tracking=True,
        help='Biaya pengiriman yang dipilih dari hasil cek ongkir Biteship.',
    )
    abj_selected_courier = fields.Char(
        string='Kurir Terpilih',
        copy=False,
        tracking=True,
        help='Nama kurir yang dipilih (e.g., JNE, SiCepat).',
    )
    abj_selected_service = fields.Char(
        string='Layanan Terpilih',
        copy=False,
        tracking=True,
        help='Kode layanan kurir (e.g., reg, oke, yes).',
    )
    abj_selected_courier_code = fields.Char(
        string='Kode Kurir',
        copy=False,
        help='Kode kurir Biteship (e.g., jne, sicepat).',
    )
    abj_selected_service_name = fields.Char(
        string='Nama Layanan',
        copy=False,
        help='Nama layanan lengkap (e.g., Reguler, YES, OKE).',
    )
    abj_shipping_duration = fields.Char(
        string='Estimasi Pengiriman',
        copy=False,
        help='Durasi estimasi pengiriman (e.g., 1-2 hari).',
    )

    # ══════════════════════════════════════════════════════════════════════
    # ACTION: Get Shipping Rates
    # ══════════════════════════════════════════════════════════════════════

    def action_abj_get_biteship_rates(self):
        """
        Fetch shipping rates from Biteship API and show selection wizard.
        Triggered by the "🚚 Get Shipping Rates" button on the SO form.
        """
        self.ensure_one()
        api_service = self.env['abj.biteship.api']
        config = api_service._abj_get_config()

        # ── Validate origin ──
        origin_postal = config.get('origin_postal_code', '')
        if not origin_postal:
            raise UserError(
                'Kode pos asal belum diisi.\n'
                'Silakan lengkapi di Settings → Biteship.'
            )

        # ── Validate destination ──
        partner = self.partner_shipping_id or self.partner_id
        if not partner:
            raise UserError('Pelanggan belum dipilih.')
        dest_postal = partner.zip
        if not dest_postal:
            raise UserError(
                f'Kode pos pelanggan "{partner.name}" belum diisi.\n'
                'Silakan lengkapi di form Contact.'
            )

        # ── Build items from order lines ──
        items = []
        for line in self.order_line.filtered(
            lambda l: l.product_id and l.product_id.type != 'service'
        ):
            weight_gram = int((line.product_id.weight or 0.0) * 1000)
            if weight_gram <= 0:
                raise UserError(
                    f'Berat produk "{line.product_id.name}" belum diisi atau 0.\n'
                    'Silakan isi berat produk (dalam kg) di master produk.'
                )
            items.append({
                'name': line.product_id.name[:50],
                'description': (line.name or line.product_id.name)[:100],
                'value': int(line.price_unit),
                'weight': weight_gram,
                'quantity': int(line.product_uom_qty),
                'length': int(getattr(line.product_id, 'product_length', 0) or 10),
                'width': int(getattr(line.product_id, 'product_width', 0) or 10),
                'height': int(getattr(line.product_id, 'product_height', 0) or 10),
            })

        if not items:
            raise UserError('Tidak ada produk fisik di order ini untuk dikirim.')

        # ── Get couriers ──
        couriers = config.get('default_couriers', 'jne,sicepat,anteraja')

        # ── Call Biteship API ──
        result = api_service.abj_get_rates(
            origin_postal_code=origin_postal,
            destination_postal_code=dest_postal,
            items=items,
            couriers=couriers,
        )

        pricing = result.get('pricing', [])
        if not pricing:
            raise UserError(
                'Tidak ada tarif pengiriman yang tersedia untuk rute ini.\n'
                'Periksa kode pos asal dan tujuan.'
            )

        # ── Create wizard with rate lines ──
        wizard = self.env['abj.biteship.rate.wizard'].create({
            'abj_order_id': self.id,
        })

        for rate in pricing:
            self.env['abj.biteship.rate.line'].create({
                'abj_wizard_id': wizard.id,
                'abj_courier_name': rate.get('courier_name', ''),
                'abj_courier_code': rate.get('courier_code', ''),
                'abj_service_name': rate.get('courier_service_name', ''),
                'abj_service_code': rate.get('courier_service_code', ''),
                'abj_service_type': rate.get('service_type', ''),
                'abj_price': rate.get('price', 0),
                'abj_shipping_fee': rate.get('shipping_fee', 0),
                'abj_duration': rate.get('duration', ''),
                'abj_description': rate.get('description', ''),
                'abj_insurance_fee': rate.get('insurance_fee', 0),
            })

        return {
            'name': '🚚 Pilih Tarif Pengiriman',
            'type': 'ir.actions.act_window',
            'res_model': 'abj.biteship.rate.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }
