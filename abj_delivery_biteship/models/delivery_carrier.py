# -*- coding: utf-8 -*-
"""
Delivery Carrier Extension for Biteship
========================================
Adds 'abj_biteship' delivery_type and implements
the rate_shipment interface for delivery.carrier.

Service type keys use format: {courier_code}__{service_code}
This ensures uniqueness and enables filtering by courier.
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

# ── Biteship Service Types (keyed as courier__service for uniqueness) ────
# Format: ('courier_code__service_code', '[COURIER] Service Name')
ABJ_BITESHIP_SERVICE_TYPES = [
    # ── Gojek ──
    ('gojek__instant', '[Gojek] Instant'),
    ('gojek__same_day', '[Gojek] Same Day'),
    # ── Grab ──
    ('grab__instant', '[Grab] Instant'),
    ('grab__same_day', '[Grab] Same Day'),
    ('grab__instant_car', '[Grab] Instant Car'),
    # ── Deliveree ──
    ('deliveree__tronton_wing_box', '[Deliveree] Tronton Wing Box'),
    ('deliveree__tronton_box', '[Deliveree] Tronton Box'),
    ('deliveree__fuso_heavy', '[Deliveree] Fuso Heavy'),
    ('deliveree__fuso_light', '[Deliveree] Fuso Lite'),
    ('deliveree__cdd_box', '[Deliveree] CDD Box'),
    ('deliveree__cdd_pickup', '[Deliveree] CDD Pickup'),
    ('deliveree__cde_frozen', '[Deliveree] CDE Frozen'),
    ('deliveree__cde_flammable', '[Deliveree] CDE Flammable'),
    ('deliveree__cde_chemical', '[Deliveree] CDE Chemical'),
    ('deliveree__engkel_box', '[Deliveree] Engkel Box'),
    ('deliveree__engkel_pickup', '[Deliveree] Engkel Pickup'),
    ('deliveree__small_box', '[Deliveree] Small Box'),
    ('deliveree__pickup', '[Deliveree] Pickup'),
    ('deliveree__van', '[Deliveree] Van'),
    ('deliveree__economy', '[Deliveree] Economy'),
    # ── JNE ──
    ('jne__reg', '[JNE] Reguler (REG)'),
    ('jne__yes', '[JNE] YES – Express Next Day'),
    ('jne__oke', '[JNE] OKE – Ongkos Kirim Ekonomis'),
    ('jne__jtr', '[JNE] JTR – Trucking min 10kg'),
    ('jne__jtr_150_250', '[JNE] JTR 150-250CC'),
    ('jne__jtr_150', '[JNE] JTR Motor <150CC'),
    ('jne__jtr_250', '[JNE] JTR Motor >250CC'),
    # ── TIKI ──
    ('tiki__eko', '[TIKI] EKO – Ekonomi'),
    ('tiki__sds', '[TIKI] SDS – Same Day'),
    ('tiki__reg', '[TIKI] REG – Reguler'),
    ('tiki__ons', '[TIKI] ONS – One Night Service'),
    ('tiki__t15', '[TIKI] Motor <150CC'),
    ('tiki__t25', '[TIKI] Motor <250CC'),
    ('tiki__t60', '[TIKI] Motor <600CC'),
    ('tiki__trc', '[TIKI] Trucking'),
    # ── Ninja Express ──
    ('ninja__standard', '[Ninja] Standard'),
    # ── Lion Parcel ──
    ('lion__reg_pack', '[Lion] Reg Pack'),
    ('lion__land_pack', '[Lion] Land Pack'),
    ('lion__one_pack', '[Lion] One Pack'),
    ('lion__jago_pack', '[Lion] Jago Pack'),
    ('lion__docu_pack', '[Lion] Docu Pack'),
    ('lion__big_pack', '[Lion] Big Pack'),
    # ── RaRa ──
    ('rara__instant', '[RaRa] Instant'),
    # ── SiCepat ──
    ('sicepat__reg', '[SiCepat] Reguler'),
    ('sicepat__best', '[SiCepat] BEST – Besok Sampai'),
    ('sicepat__sds', '[SiCepat] SDS – Same Day'),
    ('sicepat__gokil', '[SiCepat] GOKIL – Kargo'),
    # ── J&T Express ──
    ('jnt__ez', '[J&T] EZ – Reguler'),
    # ── ID Express ──
    ('idexpress__reg', '[ID Express] Reguler'),
    ('idexpress__smd', '[ID Express] Same Day'),
    ('idexpress__idtruck', '[ID Express] ID Truck'),
    # ── RPX ──
    ('rpx__sdp', '[RPX] Same Day Package'),
    ('rpx__mdp', '[RPX] Mid Day Package'),
    ('rpx__ndp', '[RPX] Next Day Package'),
    ('rpx__rgp', '[RPX] Reguler Package'),
    ('rpx__pas', '[RPX] Paket Ambil Suka-suka'),
    ('rpx__ecp', '[RPX] Economy Delivery'),
    ('rpx__hwp', '[RPX] Heavy Weight'),
    # ── JDL Express ──
    ('jdl__reg', '[JDL] Reguler'),
    # ── Wahana ──
    ('wahana__normal', '[Wahana] Normal'),
    # ── POS Indonesia ──
    ('pos__kilat_khusus', '[POS] Kilat Khusus'),
    ('pos__q9_same_day', '[POS] Q9 Same Day'),
    ('pos__same_day', '[POS] Same Day'),
    ('pos__next_day', '[POS] Next Day'),
    ('pos__jumbo_ekonomi', '[POS] Jumbo Ekonomi'),
    # ── AnterAja ──
    ('anteraja__reg', '[AnterAja] Reguler'),
    ('anteraja__same_day', '[AnterAja] Same Day'),
    ('anteraja__next_day', '[AnterAja] Next Day'),
    # ── SAP Express ──
    ('sap__reg', '[SAP] Reguler'),
    ('sap__ods', '[SAP] ODS – One Day Service'),
    ('sap__sds', '[SAP] SDS – Same Day'),
    ('sap__cargo', '[SAP] Cargo'),
    # ── Paxel ──
    ('paxel__small', '[Paxel] Small Package'),
    ('paxel__medium', '[Paxel] Medium Package'),
    ('paxel__large', '[Paxel] Large Package'),
    ('paxel__paxel_big', '[Paxel] Paxel Big'),
    # ── Borzo ──
    ('borzo__instant_bike', '[Borzo] Instant Bike'),
    ('borzo__instant_car', '[Borzo] Instant Car'),
    # ── Lalamove ──
    ('lalamove__motorcycle', '[Lalamove] Motorcycle'),
    ('lalamove__mpv', '[Lalamove] MPV'),
    ('lalamove__van', '[Lalamove] Van'),
    ('lalamove__truck', '[Lalamove] Truck'),
    ('lalamove__cdd_bak', '[Lalamove] CDD Bak'),
    ('lalamove__cdd_box', '[Lalamove] CDD Box'),
    ('lalamove__engkel_box', '[Lalamove] Engkel Box'),
    ('lalamove__engkel_bak', '[Lalamove] Engkel Bak'),
    # ── Sentral Cargo ──
    ('sentralcargo__land_electronic', '[Sentral] Land Electronic'),
    ('sentralcargo__land_non_electronic', '[Sentral] Land Non Electronic'),
    ('sentralcargo__air_electronic', '[Sentral] Air Electronic'),
    ('sentralcargo__air_non_electronic', '[Sentral] Air Non Electronic'),
    # ── Dash Express ──
    ('dash_express__same_day', '[Dash Express] Same Day'),
]

# ── Build lookup: courier_code → list of service keys ────────────────────
ABJ_SERVICE_BY_COURIER = {}
for _key, _label in ABJ_BITESHIP_SERVICE_TYPES:
    _courier = _key.split('__')[0]
    ABJ_SERVICE_BY_COURIER.setdefault(_courier, []).append(_key)


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
        help='Pilih kurir dari Biteship.',
    )
    abj_biteship_service_type = fields.Selection(
        selection=ABJ_BITESHIP_SERVICE_TYPES,
        string='Tipe Layanan Biteship',
        help='Pilih tipe layanan. Hanya layanan untuk kurir terpilih yang valid.',
    )

    # ── Onchange: Reset service when courier changes ─────────────────────
    @api.onchange('abj_biteship_courier_code')
    def _onchange_abj_biteship_courier_code(self):
        """Reset service type when courier changes + set domain filter."""
        self.abj_biteship_service_type = False
        if self.abj_biteship_courier_code:
            valid_services = ABJ_SERVICE_BY_COURIER.get(self.abj_biteship_courier_code, [])
            return {
                'domain': {
                    'abj_biteship_service_type': [('id', 'in', valid_services)],
                },
            }
        return {}

    # ══════════════════════════════════════════════════════════════════════
    # HELPER: Extract actual service code for API
    # ══════════════════════════════════════════════════════════════════════

    def _abj_get_actual_service_code(self):
        """
        Extract the actual Biteship service_code from the prefixed key.
        E.g., 'jne__reg' → 'reg', 'sicepat__best' → 'best'
        """
        self.ensure_one()
        if self.abj_biteship_service_type and '__' in self.abj_biteship_service_type:
            return self.abj_biteship_service_type.split('__', 1)[1]
        return self.abj_biteship_service_type or ''

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
            actual_service = self._abj_get_actual_service_code()
            if actual_service:
                for rate in pricing:
                    if rate.get('courier_service_code', '').lower() == actual_service.lower():
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

    # ══════════════════════════════════════════════════════════════════════
    # DELIVERY.CARRIER INTERFACE: send_shipping
    # ══════════════════════════════════════════════════════════════════════

    def abj_biteship_send_shipping(self, pickings):
        """
        Called when the shipment is confirmed to register the delivery
        cost and tracking number.
        """
        self.ensure_one()
        res = []
        for picking in pickings:
            res.append({
                'exact_price': picking.abj_shipping_cost or 0.0,
                'tracking_number': picking.abj_tracking_number or '',
            })
        return res
