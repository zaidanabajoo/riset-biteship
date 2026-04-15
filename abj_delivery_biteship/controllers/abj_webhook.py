# -*- coding: utf-8 -*-
"""
Biteship Webhook Controller
============================
Receives POST webhooks from Biteship for:
- order.status  → Tracking status updates
- order.price   → Price changes
- order.waybill_id → Waybill/AWB number updates

Endpoint: POST /abj/biteship/webhook

Phase 1: Lenient mode — accepts anything, returns "ok".
Phase 2: Full processing with idempotent updates.
"""
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class AbjBiteshipWebhook(http.Controller):

    @http.route(
        '/abj/biteship/webhook',
        type='http',
        auth='public',
        methods=['GET', 'POST'],
        csrf=False,
    )
    def abj_biteship_webhook(self, **kwargs):
        """
        Main webhook endpoint for Biteship events.
        Uses type='http' (NOT type='json') for maximum compatibility.
        Biteship may send empty body during webhook verification.

        Returns plain "ok" to satisfy Biteship handshake.
        """
        # ── Phase 1: Safe payload parsing ──
        try:
            raw_body = request.httprequest.get_data(as_text=True)
            payload = json.loads(raw_body) if raw_body else {}
        except Exception:
            payload = {}

        _logger.info(
            "ABJ_BITESHIP WEBHOOK RECEIVED: %s",
            json.dumps(payload, default=str) if payload else '(empty)',
        )

        # ── If empty payload (Biteship verification handshake) → just return ok ──
        if not payload:
            return "ok"

        # ── Phase 2: Process the event ──
        try:
            event = payload.get('event', '')
            order_id = payload.get('order_id', '')

            if not order_id:
                _logger.warning("ABJ_BITESHIP WEBHOOK: Missing order_id, ignoring.")
                return "ok"

            # ── Find the related picking ──
            PickingModel = request.env['stock.picking'].sudo()
            picking = PickingModel.search(
                [('abj_shipment_id', '=', order_id)], limit=1,
            )

            if not picking:
                _logger.warning(
                    "ABJ_BITESHIP WEBHOOK: No picking found for order_id=%s",
                    order_id,
                )
                return "ok"

            # ── Route by event type ──
            if event == 'order.status':
                self._abj_handle_status_event(picking, payload)
            elif event == 'order.price':
                self._abj_handle_price_event(picking, payload)
            elif event == 'order.waybill_id':
                self._abj_handle_waybill_event(picking, payload)
            else:
                _logger.info(
                    "ABJ_BITESHIP WEBHOOK: Unknown event '%s', processing generically.",
                    event,
                )
                self._abj_handle_status_event(picking, payload)

            _logger.info(
                "ABJ_BITESHIP WEBHOOK: Processed event=%s for picking=%s (order_id=%s)",
                event, picking.name, order_id,
            )

        except Exception as e:
            # ⚠️ NEVER raise — always return "ok" to Biteship
            _logger.error(
                "ABJ_BITESHIP WEBHOOK: Error processing payload: %s",
                str(e), exc_info=True,
            )

        return "ok"

    # ══════════════════════════════════════════════════════════════════════
    # EVENT HANDLERS
    # ══════════════════════════════════════════════════════════════════════

    def _abj_handle_status_event(self, picking, payload):
        """Handle order.status webhook event."""
        new_status = payload.get('status', '')

        # ── Idempotency: skip if status unchanged ──
        if new_status and picking.abj_delivery_status == new_status:
            _logger.debug(
                "ABJ_BITESHIP WEBHOOK: Status unchanged for %s: %s",
                picking.name, new_status,
            )
            return

        vals = {}

        if new_status:
            vals['abj_delivery_status'] = new_status
            # Map to selection field
            from odoo.addons.abj_delivery_biteship.models.stock_picking import ABJ_BITESHIP_STATUS_MAP
            status_key = new_status.lower()
            if status_key in ABJ_BITESHIP_STATUS_MAP:
                vals['abj_pickup_status'] = ABJ_BITESHIP_STATUS_MAP[status_key][0]

        # ── Update waybill if provided ──
        waybill = payload.get('courier_waybill_id', '')
        if waybill and waybill != picking.abj_tracking_number:
            vals['abj_tracking_number'] = waybill
            vals['carrier_tracking_ref'] = waybill

        # ── Update tracking ID ──
        tracking_id = payload.get('courier_tracking_id', '')
        if tracking_id and tracking_id != picking.abj_biteship_tracking_id:
            vals['abj_biteship_tracking_id'] = tracking_id

        # ── Update price if provided ──
        price = payload.get('order_price', 0)
        if price and float(price) != picking.abj_shipping_cost:
            vals['abj_shipping_cost'] = float(price)

        if vals:
            picking.write(vals)

        # ── Build chatter message ──
        emoji_map = {
            'confirmed': '✅',
            'allocated': '📋',
            'picking_up': '🚶',
            'picked': '📦',
            'dropping_off': '🚚',
            'delivered': '✅',
            'rejected': '❌',
            'cancelled': '🚫',
            'returned': '↩️',
            'on_hold': '⏸️',
            'courier_not_found': '⚠️',
        }
        emoji = emoji_map.get(new_status.lower(), '📋') if new_status else '📋'

        body = f'<b>{emoji} Webhook Update</b><br/>'
        body += f'<b>Event:</b> {payload.get("event", "")}<br/>'
        body += f'<b>Status:</b> {new_status}<br/>'

        courier_company = payload.get('courier_company', '')
        if courier_company:
            body += f'<b>Kurir:</b> {courier_company}<br/>'

        driver_name = payload.get('courier_driver_name', '')
        if driver_name:
            body += f'<b>Driver:</b> {driver_name}<br/>'

        driver_phone = payload.get('courier_driver_phone', '')
        if driver_phone:
            body += f'<b>HP Driver:</b> {driver_phone}<br/>'

        if waybill:
            body += f'<b>Resi:</b> {waybill}<br/>'

        picking.message_post(body=body)

    def _abj_handle_price_event(self, picking, payload):
        """Handle order.price webhook event."""
        new_price = payload.get('price', 0)
        if not new_price:
            return

        # ── Idempotency ──
        if float(new_price) == picking.abj_shipping_cost:
            return

        old_price = picking.abj_shipping_cost
        picking.write({'abj_shipping_cost': float(new_price)})

        shipping_fee = payload.get('shippment_fee', 0)
        body = (
            f'<b>💰 Update Harga Pengiriman</b><br/>'
            f'<b>Harga Lama:</b> Rp {old_price:,.0f}<br/>'
            f'<b>Harga Baru:</b> Rp {float(new_price):,.0f}<br/>'
        )
        if shipping_fee:
            body += f'<b>Ongkir:</b> Rp {float(shipping_fee):,.0f}<br/>'

        picking.message_post(body=body)

    def _abj_handle_waybill_event(self, picking, payload):
        """Handle order.waybill_id webhook event."""
        new_waybill = payload.get('courier_waybill_id', '')
        if not new_waybill:
            return

        # ── Idempotency ──
        if new_waybill == picking.abj_tracking_number:
            return

        old_waybill = picking.abj_tracking_number or '(kosong)'
        vals = {
            'abj_tracking_number': new_waybill,
            'carrier_tracking_ref': new_waybill,
        }

        tracking_id = payload.get('courier_tracking_id', '')
        if tracking_id:
            vals['abj_biteship_tracking_id'] = tracking_id

        # Update status if provided
        status = payload.get('status', '')
        if status:
            vals['abj_delivery_status'] = status
            from odoo.addons.abj_delivery_biteship.models.stock_picking import ABJ_BITESHIP_STATUS_MAP
            status_key = status.lower()
            if status_key in ABJ_BITESHIP_STATUS_MAP:
                vals['abj_pickup_status'] = ABJ_BITESHIP_STATUS_MAP[status_key][0]

        picking.write(vals)

        picking.message_post(
            body=(
                f'<b>📝 Update Nomor Resi</b><br/>'
                f'<b>Resi Lama:</b> {old_waybill}<br/>'
                f'<b>Resi Baru:</b> {new_waybill}<br/>'
            ),
        )
