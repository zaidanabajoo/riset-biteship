# -*- coding: utf-8 -*-
"""
Stock Picking Extension for Biteship
=====================================
Adds shipment creation, tracking, and status fields
to the Delivery Order (stock.picking) form.
"""
import json
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# ── Biteship Order Status Mapping ────────────────────────────────────────
ABJ_BITESHIP_STATUS_MAP = {
    'confirmed': ('confirmed', '✅ Dikonfirmasi'),
    'allocated': ('allocated', '📋 Dialokasikan'),
    'picking_up': ('picking_up', '🚶 Penjemputan'),
    'picked': ('picked', '📦 Dijemput'),
    'dropping_off': ('dropping_off', '🚚 Dalam Pengiriman'),
    'delivered': ('delivered', '✅ Terkirim'),
    'rejected': ('rejected', '❌ Ditolak'),
    'cancelled': ('cancelled', '🚫 Dibatalkan'),
    'returned': ('returned', '↩️ Dikembalikan'),
    'disposed': ('disposed', '🗑️ Disposed'),
    'on_hold': ('on_hold', '⏸️ Ditangguhkan'),
    'courier_not_found': ('courier_not_found', '⚠️ Kurir Tidak Ditemukan'),
}

ABJ_BITESHIP_TERMINAL_STATUSES = {
    'delivered', 'rejected', 'cancelled', 'returned', 'disposed',
}


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # ── Biteship Tracking & Shipment Fields ──────────────────────────────
    abj_tracking_number = fields.Char(
        string='Nomor Resi (Waybill)',
        copy=False,
        tracking=True,
        help='Nomor resi / AWB dari kurir (customer-facing).',
    )
    abj_shipment_id = fields.Char(
        string='Biteship Order ID',
        copy=False,
        tracking=True,
        help='ID order internal Biteship.',
    )
    abj_biteship_tracking_id = fields.Char(
        string='Biteship Tracking ID',
        copy=False,
        help='ID tracking internal Biteship (untuk API lookups).',
    )
    abj_courier_name = fields.Char(
        string='Nama Kurir',
        copy=False,
        tracking=True,
    )
    abj_service_type = fields.Char(
        string='Tipe Layanan',
        copy=False,
    )
    abj_shipping_cost = fields.Float(
        string='Biaya Pengiriman',
        copy=False,
        tracking=True,
    )

    abj_pickup_status = fields.Selection(
        [
            ('draft', 'Belum Dikirim'),
            ('confirmed', 'Dikonfirmasi'),
            ('allocated', 'Dialokasikan'),
            ('picking_up', 'Penjemputan'),
            ('picked', 'Dijemput'),
            ('dropping_off', 'Dalam Pengiriman'),
            ('delivered', 'Terkirim'),
            ('rejected', 'Ditolak'),
            ('cancelled', 'Dibatalkan'),
            ('returned', 'Dikembalikan'),
            ('disposed', 'Disposed'),
            ('on_hold', 'Ditangguhkan'),
            ('courier_not_found', 'Kurir Tidak Ditemukan'),
        ],
        string='Status Biteship',
        default='draft',
        copy=False,
        tracking=True,
    )
    abj_delivery_status = fields.Char(
        string='Status Detail',
        copy=False,
        help='Status mentah dari Biteship webhook/API.',
    )
    abj_delivery_type_mode = fields.Selection(
        [
            ('now', 'Pickup Sekarang'),
            ('scheduled', 'Terjadwal'),
        ],
        string='Tipe Pengiriman',
        default='now',
        copy=False,
        help='Biteship delivery type: "now" untuk pickup segera.',
    )

    # ══════════════════════════════════════════════════════════════════════
    # ACTION: Create Shipment & Request Pickup (Combined)
    # ══════════════════════════════════════════════════════════════════════

    def action_abj_create_biteship_shipment(self):
        """
        Create a shipment order on Biteship.
        Combined flow: Create Order + Trigger Pickup.
        Button label: "📦 Create Shipment & Request Pickup"
        """
        for picking in self:
            # ── Guard: prevent duplicate shipments ──
            if picking.abj_shipment_id:
                raise UserError(
                    f'Shipment sudah dibuat untuk {picking.name}.\n'
                    f'Biteship Order ID: {picking.abj_shipment_id}'
                )

            # ── Guard: only for ready/done pickings ──
            if picking.state not in ('assigned', 'done'):
                raise UserError(
                    'Validasi picking terlebih dahulu atau pastikan barang ready!\n'
                    f'Status saat ini: {picking.state}'
                )

            api_service = self.env['abj.biteship.api']
            config = api_service._abj_get_config()

            # ── Build payload ──
            payload = picking._abj_build_biteship_payload(config)

            _logger.info(
                "ABJ_BITESHIP: Creating shipment for picking %s",
                picking.name,
            )

            # ── Call API ──
            result = api_service.abj_create_shipment(payload)

            # ── Process response ──
            if not result.get('success', False):
                error_msg = result.get('error', '') or result.get('message', 'Unknown error')
                raise UserError(f'Biteship Error: {error_msg}')

            # ── Extract data from response ──
            order_id = result.get('id', '')
            courier_data = result.get('courier', {})
            tracking_id = courier_data.get('tracking_id', '')
            waybill_id = courier_data.get('waybill_id', '')
            courier_company = courier_data.get('company', '')
            courier_type = courier_data.get('type', '')
            price = result.get('price', 0)
            status = result.get('status', 'confirmed')

            # ── Map status ──
            pickup_status = 'confirmed'
            if status in ABJ_BITESHIP_STATUS_MAP:
                pickup_status = ABJ_BITESHIP_STATUS_MAP[status][0]

            # ── Write to picking ──
            vals = {
                'abj_shipment_id': order_id,
                'abj_biteship_tracking_id': tracking_id,
                'abj_courier_name': courier_company,
                'abj_service_type': courier_type,
                'abj_shipping_cost': float(price) if price else 0.0,
                'abj_pickup_status': pickup_status,
                'abj_delivery_status': status,
            }
            if waybill_id:
                vals['abj_tracking_number'] = waybill_id
                vals['carrier_tracking_ref'] = waybill_id
            picking.write(vals)

            # ── Post chatter message ──
            picking.message_post(
                body=(
                    f'<b>✅ Shipment Biteship Dibuat</b><br/>'
                    f'<b>Order ID:</b> {order_id}<br/>'
                    f'<b>Tracking ID:</b> {tracking_id}<br/>'
                    f'<b>Resi (Waybill):</b> {waybill_id or "(menunggu pickup)"}<br/>'
                    f'<b>Kurir:</b> {courier_company} ({courier_type})<br/>'
                    f'<b>Biaya:</b> Rp {price:,.0f}<br/>'
                    f'<b>Status:</b> {status}'
                ),
            )

            _logger.info(
                "ABJ_BITESHIP: Shipment created for %s → order_id=%s, waybill=%s",
                picking.name, order_id, waybill_id,
            )

    # ══════════════════════════════════════════════════════════════════════
    # ACTION: Track Shipment (Manual Refresh)
    # ══════════════════════════════════════════════════════════════════════

    def action_abj_track_biteship_shipment(self):
        """Open tracking URL in browser."""
        self.ensure_one()
        if not self.abj_tracking_number:
            raise UserError('Nomor resi belum tersedia.')
        tracking_url = f'https://cekresi.com/?noresi={self.abj_tracking_number}'
        return {
            'type': 'ir.actions.act_url',
            'url': tracking_url,
            'target': 'new',
        }

    def action_abj_refresh_biteship_status(self):
        """
        Manually refresh tracking status from Biteship API.
        Button: "🔄 Refresh Status"
        """
        self.ensure_one()
        if not self.abj_biteship_tracking_id and not self.abj_shipment_id:
            raise UserError('Tracking ID atau Order ID Biteship tidak tersedia.')

        api_service = self.env['abj.biteship.api']

        try:
            if self.abj_biteship_tracking_id:
                result = api_service.abj_get_tracking(self.abj_biteship_tracking_id)
            else:
                result = api_service.abj_retrieve_order(self.abj_shipment_id)

            self._abj_update_from_tracking_response(result)

        except Exception as e:
            _logger.error(
                "ABJ_BITESHIP: Tracking refresh failed for %s: %s",
                self.name, str(e),
            )
            self.message_post(
                body=f'<b>⚠️ Refresh Status Gagal</b><br/>{str(e)}',
            )

    # ══════════════════════════════════════════════════════════════════════
    # CRON: Batch Update Tracking
    # ══════════════════════════════════════════════════════════════════════

    @api.model
    def _abj_cron_update_biteship_tracking(self):
        """
        Cron job: Update tracking status for all active Biteship shipments.
        Runs as fallback — webhook is the primary source of truth.
        """
        _logger.info("ABJ_BITESHIP CRON: Starting tracking update batch...")

        # Find all pickings with active Biteship shipments
        active_pickings = self.search([
            ('abj_shipment_id', '!=', False),
            ('abj_pickup_status', 'not in', list(ABJ_BITESHIP_TERMINAL_STATUSES)),
        ], limit=50)  # Process max 50 per run to avoid API rate limits

        if not active_pickings:
            _logger.info("ABJ_BITESHIP CRON: No active shipments to update.")
            return

        api_service = self.env['abj.biteship.api']
        updated_count = 0
        error_count = 0

        for picking in active_pickings:
            try:
                tracking_id = picking.abj_biteship_tracking_id or picking.abj_shipment_id
                if picking.abj_biteship_tracking_id:
                    result = api_service.abj_get_tracking(tracking_id)
                else:
                    result = api_service.abj_retrieve_order(tracking_id)

                picking._abj_update_from_tracking_response(result)
                updated_count += 1

            except Exception as e:
                error_count += 1
                _logger.warning(
                    "ABJ_BITESHIP CRON: Failed to update %s: %s",
                    picking.name, str(e),
                )
            # Small delay between API calls to be respectful
            # (Odoo cron runs in a single transaction)

        _logger.info(
            "ABJ_BITESHIP CRON: Completed. Updated: %d, Errors: %d",
            updated_count, error_count,
        )

    # ══════════════════════════════════════════════════════════════════════
    # HELPER: Build Biteship Order Payload
    # ══════════════════════════════════════════════════════════════════════

    def _abj_build_biteship_payload(self, config):
        """
        Build the JSON payload for Biteship POST /v1/orders endpoint.

        Args:
            config (dict): Configuration from abj.biteship.api._abj_get_config()

        Returns:
            dict: Complete order creation payload.
        """
        self.ensure_one()
        partner = self.partner_id
        sale = self.sale_id

        # ── Validate destination ──
        if not partner.zip:
            raise UserError(
                f'Kode pos pelanggan "{partner.name}" belum diisi.\n'
                'Silakan lengkapi data alamat di form Contact.'
            )

        # ── Build items from stock moves ──
        items = []
        for move in self.move_ids.filtered(lambda m: m.state != 'cancel'):
            weight_gram = int((move.product_id.weight or 0.0) * move.product_uom_qty * 1000)
            if weight_gram <= 0:
                raise UserError(
                    f'Berat produk "{move.product_id.name}" harus lebih dari 0.\n'
                    'Silakan isi berat produk (kg) di master produk.'
                )
            items.append({
                'name': move.product_id.name[:50],
                'description': (move.product_id.description_sale or move.product_id.name)[:100],
                'value': int(move.product_id.list_price or 0),
                'weight': int((move.product_id.weight or 0.1) * 1000),  # per unit in grams
                'quantity': int(move.product_uom_qty),
                'length': int(getattr(move.product_id, 'product_length', 0) or 10),
                'width': int(getattr(move.product_id, 'product_width', 0) or 10),
                'height': int(getattr(move.product_id, 'product_height', 0) or 10),
            })

        if not items:
            raise UserError('Tidak ada barang untuk dikirim.')

        # ── Determine courier from sale order or carrier ──
        courier_company = ''
        courier_type = ''

        if sale and sale.abj_selected_courier_code:
            courier_company = sale.abj_selected_courier_code
            courier_type = sale.abj_selected_service or 'reg'
        elif self.carrier_id and self.carrier_id.delivery_type == 'abj_biteship':
            courier_company = self.carrier_id.abj_biteship_courier_code or ''
            courier_type = self.carrier_id.abj_biteship_service_type or 'reg'

        if not courier_company:
            raise UserError(
                'Kurir belum dipilih.\n'
                'Silakan pilih kurir melalui "Get Shipping Rates" di Sales Order, '
                'atau atur di Delivery Method.'
            )

        # ── Delivery type ──
        delivery_type = self.abj_delivery_type_mode or 'now'

        # ── Build address ──
        dest_address = self._abj_format_address(partner)

        payload = {
            # Shipper
            'shipper_contact_name': config.get('sender_name', ''),
            'shipper_contact_phone': config.get('sender_phone', ''),
            'shipper_contact_email': config.get('sender_email', ''),
            'shipper_organization': config.get('sender_org', ''),
            # Origin
            'origin_contact_name': config.get('sender_name', ''),
            'origin_contact_phone': config.get('sender_phone', ''),
            'origin_address': config.get('origin_address', ''),
            'origin_postal_code': int(config.get('origin_postal_code', 0)),
            # Destination
            'destination_contact_name': partner.name,
            'destination_contact_phone': partner.phone or partner.mobile or '',
            'destination_contact_email': partner.email or '',
            'destination_address': dest_address,
            'destination_postal_code': int(partner.zip or 0),
            # Courier
            'courier_company': courier_company.lower(),
            'courier_type': courier_type.lower(),
            # Delivery
            'delivery_type': delivery_type,
            'order_note': f'Ref: {self.name}',
            # Items
            'items': items,
            # Metadata for traceability
            'metadata': {
                'odoo_picking': self.name,
                'odoo_sale_order': sale.name if sale else '',
            },
        }

        return payload

    def _abj_format_address(self, partner):
        """Format partner address into a single string."""
        parts = filter(None, [
            partner.street,
            partner.street2,
            partner.city,
            partner.state_id.name if partner.state_id else '',
            partner.zip,
        ])
        return ', '.join(parts) or partner.name

    # ══════════════════════════════════════════════════════════════════════
    # HELPER: Update from Tracking/Webhook Response
    # ══════════════════════════════════════════════════════════════════════

    def _abj_update_from_tracking_response(self, data):
        """
        Update picking fields from a Biteship tracking or order response.
        Handles idempotency: skips if status is unchanged.

        Args:
            data (dict): Biteship API response (tracking or order).
        """
        self.ensure_one()

        # ── Extract status ──
        new_status = data.get('status', '')
        if not new_status:
            # Try nested courier data
            courier = data.get('courier', {})
            new_status = courier.get('status', '') if isinstance(courier, dict) else ''

        # ── Idempotency check ──
        if new_status and self.abj_delivery_status == new_status:
            _logger.debug(
                "ABJ_BITESHIP: Status unchanged for %s: %s",
                self.name, new_status,
            )
            return

        vals = {}

        # ── Update status ──
        if new_status:
            vals['abj_delivery_status'] = new_status
            status_key = new_status.lower()
            if status_key in ABJ_BITESHIP_STATUS_MAP:
                vals['abj_pickup_status'] = ABJ_BITESHIP_STATUS_MAP[status_key][0]

        # ── Update waybill if available ──
        courier_data = data.get('courier', {})
        if isinstance(courier_data, dict):
            waybill = courier_data.get('waybill_id', '')
            if waybill and waybill != self.abj_tracking_number:
                vals['abj_tracking_number'] = waybill
                vals['carrier_tracking_ref'] = waybill

            tracking_id = courier_data.get('tracking_id', '')
            if tracking_id and tracking_id != self.abj_biteship_tracking_id:
                vals['abj_biteship_tracking_id'] = tracking_id

            driver_name = courier_data.get('driver_name', '')
            driver_phone = courier_data.get('driver_phone', '')
        else:
            driver_name = ''
            driver_phone = ''

        # ── Update price if changed ──
        price = data.get('price', 0)
        if price and float(price) != self.abj_shipping_cost:
            vals['abj_shipping_cost'] = float(price)

        if vals:
            self.write(vals)

        # ── Post chatter update ──
        if new_status:
            status_info = ABJ_BITESHIP_STATUS_MAP.get(new_status.lower(), ('', f'📋 {new_status}'))
            emoji_label = status_info[1]

            body = f'<b>{emoji_label}</b><br/>'
            body += f'<b>Status:</b> {new_status}<br/>'
            if vals.get('abj_tracking_number'):
                body += f'<b>Resi:</b> {vals["abj_tracking_number"]}<br/>'
            if driver_name:
                body += f'<b>Driver:</b> {driver_name}<br/>'
            if driver_phone:
                body += f'<b>HP Driver:</b> {driver_phone}<br/>'
            if price:
                body += f'<b>Biaya:</b> Rp {float(price):,.0f}<br/>'

            self.message_post(body=body)

        _logger.info(
            "ABJ_BITESHIP: Updated picking %s → status=%s, waybill=%s",
            self.name, new_status, vals.get('abj_tracking_number', ''),
        )
