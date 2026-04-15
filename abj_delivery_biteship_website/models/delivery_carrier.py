# -*- coding: utf-8 -*-
import json
import logging
from psycopg2 import IntegrityError

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Datetime

_logger = logging.getLogger(__name__)

# TTL for shipping rates cache (in seconds)
ABJ_CACHE_TTL = 120

class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    # ══════════════════════════════════════════════════════════════════════
    # WEBSITE INTERFACE: rate_shipment
    # ══════════════════════════════════════════════════════════════════════

    def abj_biteship_rate_shipment(self, order):
        """
        Website-optimized rate_shipment with dual-layer caching.
        Level 1: Request-level memory cache (prevents redundant DB/API hits in one page load)
        Level 2: DB-level persistent cache (ir.config_parameter)
        """
        self.ensure_one()
        
        # ── 1. Validation ──
        partner = order.partner_shipping_id or order.partner_id
        dest_postal = partner.zip
        if not dest_postal:
            return {
                'success': False,
                'price': 0.0,
                'error_message': 'Alamat pengiriman belum lengkap (Kode Pos Kosong).',
                'warning_message': False,
            }

        # ── 2. Build Cache Key ──
        cache_key = self._abj_biteship_build_cache_key(order)

        # ── 3. Level 1 Cache: Memory (Per Request) ──
        # Since Odoo calls rate_shipment sequentially for each carrier in one request,
        # we store the first result in self.env to share it immediately.
        if not hasattr(self.env, 'abj_biteship_req_cache'):
            # Using a dictionary to store multiple orders/keys if needed in one request
            self.env.abj_biteship_req_cache = {}
        
        if cache_key in self.env.abj_biteship_req_cache:
            _logger.debug("ABJ_BITESHIP: Request-Level Cache HIT for %s", self.name)
            pricing = self.env.abj_biteship_req_cache[cache_key]
        else:
            # ── 4. Level 2 Cache: DB (ir.config_parameter) ──
            cached_data = self._abj_get_biteship_cache(cache_key)
            
            if cached_data:
                _logger.debug("ABJ_BITESHIP: DB Cache HIT for order %s", order.name)
                pricing = cached_data
            else:
                _logger.debug("ABJ_BITESHIP: Cache MISS. Fetching total rates...")
                pricing = self._abj_fetch_all_biteship_rates(order)
                if pricing:
                    self._abj_set_biteship_cache(cache_key, pricing)
            
            # Store in Memory for the remainder of this request
            self.env.abj_biteship_req_cache[cache_key] = pricing

        if not pricing:
            return {
                'success': False,
                'price': 0.0,
                'error_message': 'Layanan tidak tersedia untuk rute ini.',
                'warning_message': False,
            }

        # ── 5. Find matching rate for THIS carrier ──
        target_courier = self.abj_biteship_courier_code
        target_service = self._abj_normalize_service_code(self.abj_biteship_service_type)
        
        matching_rate = False
        for rate in pricing:
            api_courier = rate.get('courier_code', '').lower()
            api_service = rate.get('courier_service_code', '').lower()
            
            if api_courier == target_courier and api_service == target_service:
                matching_rate = rate
                break
        
        if matching_rate:
            price = matching_rate.get('price', 0)
            duration = matching_rate.get('duration', '')
            return {
                'success': True,
                'price': float(price),
                'error_message': False,
                'warning_message': f"Estimasi: {duration}" if duration else False,
            }

        return {
            'success': False,
            'price': 0.0,
            'error_message': 'Layanan tidak tersedia.',
            'warning_message': False,
        }

    # ══════════════════════════════════════════════════════════════════════
    # CACHING & NORMALIZATION HELPERS
    # ══════════════════════════════════════════════════════════════════════

    def _abj_biteship_build_cache_key(self, order):
        """Build a robust cache key based on route, weight, and transaction state."""
        partner = order.partner_shipping_id or order.partner_id
        
        total_weight_gram = sum(
            (line.product_id.weight or 0.1) * line.product_uom_qty * 1000
            for line in order.order_line
            if line.product_id and line.product_id.type != 'service'
        )
        
        origin_zip = order.warehouse_id.partner_id.zip or ''
        dest_zip = partner.zip or ''
        db_name = self.env.cr.dbname
        return f"abj_bs_{db_name}_{origin_zip}_{dest_zip}_{int(total_weight_gram)}_{int(order.amount_total)}"

    def _abj_normalize_service_code(self, service_key):
        """Extract 'reg' from 'jne__reg'."""
        if service_key and '__' in service_key:
            return service_key.split('__')[-1]
        return service_key or ''

    def _abj_get_biteship_cache(self, key):
        """Retrieve and validate JSON cache with Timezone-safe Datetime."""
        param = self.env['ir.config_parameter'].sudo().get_param(key)
        if not param:
            return False
        
        try:
            data = json.loads(param)
            timestamp = data.get('ts', 0)
            if Datetime.now().timestamp() - timestamp > ABJ_CACHE_TTL:
                return False
            return data.get('pricing', [])
        except (ValueError, KeyError, TypeError):
            return False

    def _abj_set_biteship_cache(self, key, pricing):
        """
        Store pricing with Odoo-compliant timestamp.
        Uses UPSERT pattern to avoid IntegrityError (Race Condition).
        """
        param_model = self.env['ir.config_parameter'].sudo()
        data = {
            'ts': Datetime.now().timestamp(),
            'pricing': pricing
        }
        val = json.dumps(data)
        
        # Pattern: Try searching first to avoid direct create collision
        existing = param_model.search([('key', '=', key)], limit=1)
        if existing:
            existing.write({'value': val})
        else:
            try:
                param_model.create({'key': key, 'value': val})
            except IntegrityError:
                # Fallback: Another request created it milliseconds ago
                self.env.cr.rollback()
                param_model.search([('key', '=', key)], limit=1).write({'value': val})

    def _abj_fetch_all_biteship_rates(self, order):
        """Call core API to fetch ALL available rates."""
        api_service = self.env['abj.biteship.api']
        try:
            config = api_service._abj_get_config()
        except Exception:
            return []

        origin_postal = config.get('origin_postal_code', '')
        partner = order.partner_shipping_id or order.partner_id
        dest_postal = partner.zip
        
        if not origin_postal or not dest_postal:
            return []

        items = []
        for line in order.order_line.filtered(lambda l: l.product_id and l.product_id.type != 'service'):
            weight_gram = int((line.product_id.weight or 0.1) * 1000)
            items.append({
                'name': line.product_id.name[:50],
                'value': int(line.price_unit),
                'weight': weight_gram,
                'quantity': int(line.product_uom_qty),
                'length': int(getattr(line.product_id, 'product_length', 0) or 10),
                'width': int(getattr(line.product_id, 'product_width', 0) or 10),
                'height': int(getattr(line.product_id, 'product_height', 0) or 10),
            })
            
        if not items:
            return []

        try:
            couriers = config.get('default_couriers', 'jne,sicepat,anteraja,jnt,tiki,pos,lion,ninja')
            result = api_service.abj_get_rates(
                origin_postal_code=origin_postal,
                destination_postal_code=dest_postal,
                items=items,
                couriers=couriers,
            )
            return result.get('pricing', [])
        except Exception as e:
            _logger.error("ABJ_BITESHIP_WEBSITE: Error fetching rates: %s", str(e))
            return []
