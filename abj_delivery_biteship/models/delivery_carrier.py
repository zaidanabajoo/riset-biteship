# -*- coding: utf-8 -*-
"""
Delivery Carrier Extension for Biteship
========================================
Adds 'abj_biteship' delivery_type and implements
the rate_shipment interface for delivery.carrier.
"""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# ── Biteship Courier Codes ───────────────────────────────────────────────
ABJ_BITESHIP_COURIER_CODES = [
    ('gojek', 'Gojek'),
    ('grab', 'Grab'),
    ('deliveree', 'Deliveree'),
    ('jne', 'JNE'),
    ('tiki', 'TIKI'),
    ('ninja', 'Ninja Express'),
    ('lion', 'Lion Parcel'),
    ('rara', 'RaRa Delivery'),
    ('sicepat', 'SiCepat'),
    ('jnt', 'J&T Express'),
    ('idexpress', 'ID Express'),
    ('rpx', 'RPX'),
    ('jdl', 'JDL Express'),
    ('wahana', 'Wahana'),
    ('pos', 'POS Indonesia'),
    ('anteraja', 'AnterAja'),
    ('sap', 'SAP Express'),
    ('paxel', 'Paxel'),
    ('borzo', 'Borzo'),
    ('lalamove', 'Lalamove'),
    ('sentralcargo', 'Sentral Cargo'),
    ('dash_express', 'Dash Express'),
]

# ── Biteship Service Types (unique across all couriers) ──────────────────
ABJ_BITESHIP_SERVICE_TYPES = [
    # ── Instant / Same Day ──
    ('instant', 'Instant'),
    ('same_day', 'Same Day'),
    ('instant_car', 'Instant Car'),
    ('instant_bike', 'Instant Bike'),
    ('SAME_DAY', 'Same Day (Dash Express)'),
    ('sds', 'Same Day Service (SDS)'),
    ('q9_same_day', 'Q9 Same Day (POS)'),
    # ── Regular / Standard ──
    ('reg', 'Reguler (REG)'),
    ('standard', 'Standard'),
    ('normal', 'Normal'),
    ('ez', 'EZ (J&T)'),
    # ── Express / Next Day ──
    ('yes', 'YES – Express Next Day (JNE)'),
    ('best', 'BEST – Besok Sampai (SiCepat)'),
    ('ons', 'ONS – One Night Service (TIKI)'),
    ('one_pack', 'One Pack (Lion)'),
    ('next_day', 'Next Day'),
    ('smd', 'Same Day (ID Express)'),
    # ── Economy ──
    ('oke', 'OKE – Ongkos Kirim Ekonomis (JNE)'),
    ('eko', 'EKO – Ekonomi (TIKI)'),
    ('economy', 'Economy'),
    ('gokil', 'GOKIL – Kargo (SiCepat)'),
    ('jumbo_ekonomi', 'Jumbo Ekonomi (POS)'),
    # ── Trucking / Cargo ──
    ('jtr', 'JTR – Trucking min 10kg (JNE)'),
    ('jtr_150', 'JTR 150 – Motor <150CC (JNE)'),
    ('jtr_250', 'JTR 250 – Motor >250CC (JNE)'),
    ('jtr_150_250', 'JTR 150-250 – Motor 150-250CC (JNE)'),
    ('trc', 'Trucking (TIKI)'),
    ('idtruck', 'ID Truck (ID Express)'),
    ('cargo', 'Cargo (SAP)'),
    # ── Motorcycle Shipping ──
    ('t15', 'Motor <150CC (TIKI)'),
    ('t25', 'Motor <250CC (TIKI)'),
    ('t60', 'Motor <600CC (TIKI)'),
    # ── POS Indonesia ──
    ('kilat_khusus', 'Kilat Khusus (POS)'),
    # ── SAP Express ──
    ('ods', 'ODS – One Day Service (SAP)'),
    # ── RPX ──
    ('sdp', 'SDP – Same Day Package (RPX)'),
    ('mdp', 'MDP – Mid Day Package (RPX)'),
    ('ndp', 'NDP – Next Day Package (RPX)'),
    ('rgp', 'RGP – Reguler Package (RPX)'),
    ('pas', 'PAS – Paket Ambil Suka-suka (RPX)'),
    ('ecp', 'ECP – Economy Delivery (RPX)'),
    ('hwp', 'HWP – Heavy Weight (RPX)'),
    # ── Lion Parcel ──
    ('reg_pack', 'Reg Pack (Lion)'),
    ('land_pack', 'Land Pack (Lion)'),
    ('jago_pack', 'Jago Pack (Lion)'),
    ('docu_pack', 'Docu Pack (Lion)'),
    ('big_pack', 'Big Pack (Lion)'),
    # ── Paxel ──
    ('small', 'Small Package (Paxel)'),
    ('medium', 'Medium Package (Paxel)'),
    ('large', 'Large Package (Paxel)'),
    ('paxel_big', 'Paxel Big'),
    # ── Lalamove ──
    ('motorcycle', 'Motorcycle (Lalamove)'),
    ('mpv', 'MPV (Lalamove)'),
    ('truck', 'Truck (Lalamove)'),
    # ── Deliveree / Lalamove Heavy ──
    ('van', 'Van'),
    ('pickup', 'Pickup'),
    ('small_box', 'Small Box'),
    ('engkel_box', 'Engkel Box'),
    ('engkel_pickup', 'Engkel Pickup'),
    ('engkel_bak', 'Engkel Bak'),
    ('cdd_box', 'CDD Box'),
    ('cdd_pickup', 'CDD Pickup'),
    ('cdd_bak', 'CDD Bak'),
    ('cde_frozen', 'CDE Frozen'),
    ('cde_flammable', 'CDE Flammable'),
    ('cde_chemical', 'CDE Chemical'),
    ('fuso_light', 'Fuso Lite'),
    ('fuso_heavy', 'Fuso Heavy'),
    ('tronton_box', 'Tronton Box'),
    ('tronton_wing_box', 'Tronton Wing Box'),
    # ── Sentral Cargo ──
    ('land_electronic', 'Land Electronic (Sentral)'),
    ('land_non_electronic', 'Land Non Electronic (Sentral)'),
    ('air_electronic', 'Air Electronic (Sentral)'),
    ('air_non_electronic', 'Air Non Electronic (Sentral)'),
]


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    # ── Add Biteship delivery type ───────────────────────────────────────
    delivery_type = fields.Selection(
        selection_add=[('abj_biteship', 'Biteship')],
        ondelete={'abj_biteship': 'set default'},
    )

    # ── Biteship-specific fields ─────────────────────────────────────────
    abj_biteship_courier_code = fields.Selection(
        selection=ABJ_BITESHIP_COURIER_CODES,
        string='Kode Kurir Biteship',
        help='Pilih kurir dari Biteship.\n'
             'Akan terisi otomatis saat memilih dari wizard tarif.',
    )
    abj_biteship_service_type = fields.Selection(
        selection=ABJ_BITESHIP_SERVICE_TYPES,
        string='Tipe Layanan Biteship',
        help='Pilih tipe layanan dari Biteship.\n'
             'Akan terisi otomatis saat memilih dari wizard tarif.',
    )

    # ══════════════════════════════════════════════════════════════════════
    # DELIVERY.CARRIER INTERFACE: rate_shipment
    # ══════════════════════════════════════════════════════════════════════

    def abj_biteship_rate_shipment(self, order):
        """
        Called by delivery.carrier to get shipping rate for a sale.order.
        This method name follows Odoo convention: {delivery_type}_rate_shipment.

        Args:
            order (sale.order): The sale order to calculate rate for.

        Returns:
            dict: {
                'success': bool,
                'price': float,
                'error_message': str or False,
                'warning_message': str or False,
            }
        """
        self.ensure_one()
        api_service = self.env['abj.biteship.api']

        try:
            config = api_service._abj_get_config()
        except Exception as e:
            return {
                'success': False,
                'price': 0.0,
                'error_message': str(e),
                'warning_message': False,
            }

        # ── Origin ──
        origin_postal = config.get('origin_postal_code', '')
        if not origin_postal:
            return {
                'success': False,
                'price': 0.0,
                'error_message': 'Kode pos asal belum diisi di Settings → Biteship.',
                'warning_message': False,
            }

        # ── Destination ──
        partner = order.partner_shipping_id or order.partner_id
        dest_postal = partner.zip
        if not dest_postal:
            return {
                'success': False,
                'price': 0.0,
                'error_message': f'Kode pos pelanggan "{partner.name}" belum diisi.',
                'warning_message': False,
            }

        # ── Build items ──
        items = []
        for line in order.order_line.filtered(
            lambda l: l.product_id and l.product_id.type != 'service'
        ):
            weight_gram = int((line.product_id.weight or 0.0) * 1000)
            if weight_gram <= 0:
                weight_gram = 100  # minimum fallback
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
            return {
                'success': False,
                'price': 0.0,
                'error_message': 'Tidak ada produk fisik untuk dikirim.',
                'warning_message': False,
            }

        # ── Courier filter ──
        couriers = self.abj_biteship_courier_code or config.get('default_couriers', 'jne')

        try:
            result = api_service.abj_get_rates(
                origin_postal_code=origin_postal,
                destination_postal_code=dest_postal,
                items=items,
                couriers=couriers,
            )

            pricing = result.get('pricing', [])
            if not pricing:
                return {
                    'success': False,
                    'price': 0.0,
                    'error_message': 'Tidak ada tarif yang tersedia untuk rute ini.',
                    'warning_message': False,
                }

            # ── Find matching service type or cheapest ──
            best_rate = None
            if self.abj_biteship_service_type:
                # Try to find the specific service type
                for rate in pricing:
                    if rate.get('courier_service_code', '').lower() == self.abj_biteship_service_type.lower():
                        best_rate = rate
                        break

            if not best_rate:
                # Fallback: cheapest available
                best_rate = min(pricing, key=lambda r: r.get('price', float('inf')))

            price = best_rate.get('price', 0)
            courier_name = best_rate.get('courier_name', '')
            service_name = best_rate.get('courier_service_name', '')
            duration = best_rate.get('duration', '')

            return {
                'success': True,
                'price': float(price),
                'error_message': False,
                'warning_message': f'{courier_name} {service_name} ({duration})' if courier_name else False,
            }

        except Exception as e:
            _logger.error("ABJ_BITESHIP rate_shipment error: %s", str(e))
            return {
                'success': False,
                'price': 0.0,
                'error_message': str(e),
                'warning_message': False,
            }

    # ══════════════════════════════════════════════════════════════════════
    # DELIVERY.CARRIER INTERFACE: get_tracking_link
    # ══════════════════════════════════════════════════════════════════════

    def abj_biteship_get_tracking_link(self, picking):
        """
        Return a tracking URL for the shipment.
        Called by delivery.carrier: {delivery_type}_get_tracking_link.
        """
        self.ensure_one()
        if picking.abj_tracking_number:
            return f'https://cekresi.com/?noresi={picking.abj_tracking_number}'
        return ''

    # ══════════════════════════════════════════════════════════════════════
    # DELIVERY.CARRIER INTERFACE: cancel_shipment
    # ══════════════════════════════════════════════════════════════════════

    def abj_biteship_cancel_shipment(self, pickings):
        """
        Cancel shipments in Biteship.
        Called by delivery.carrier: {delivery_type}_cancel_shipment.
        """
        # Biteship supports DELETE /v1/orders/:id but with limitations
        # For now, we just log the action
        for picking in pickings:
            if picking.abj_shipment_id:
                _logger.info(
                    "ABJ_BITESHIP: Cancel shipment requested for picking %s (order_id: %s)",
                    picking.name, picking.abj_shipment_id,
                )
                picking.message_post(
                    body='<b>⚠️ Pembatalan Pengiriman</b><br/>'
                         'Silakan batalkan order secara manual di dashboard Biteship.',
                )
