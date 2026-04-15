# -*- coding: utf-8 -*-
"""
Biteship API Service Layer (AbstractModel)
==========================================
Centralized API communication with Biteship.
All HTTP interactions are routed through this model.

Endpoints used:
- POST /v1/rates/couriers       → Fetch shipping rates
- POST /v1/orders               → Create shipment order
- GET  /v1/orders/:id           → Retrieve order details
- GET  /v1/trackings/:id        → Get tracking by Biteship tracking ID
- GET  /v1/trackings/:waybill/couriers/:code  → Public tracking
"""
import json
import logging
import time

import requests

from odoo import api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
ABJ_DEFAULT_BASE_URL = 'https://api.biteship.com'
ABJ_REQUEST_TIMEOUT = 30  # seconds
ABJ_MAX_RETRIES = 3
ABJ_RETRY_BACKOFF = 2  # exponential backoff multiplier


class AbjBiteshipApi(models.AbstractModel):
    _name = 'abj.biteship.api'
    _description = 'ABJ Biteship API Service Layer'

    # ══════════════════════════════════════════════════════════════════════
    # CONFIGURATION
    # ══════════════════════════════════════════════════════════════════════

    @api.model
    def _abj_get_config(self):
        """
        Retrieve Biteship API configuration from ir.config_parameter.

        Returns:
            dict: Configuration with keys:
                - api_key (str)
                - base_url (str)
                - sender_name (str)
                - sender_phone (str)
                - sender_email (str)
                - sender_org (str)
                - origin_address (str)
                - origin_postal_code (str)
                - default_couriers (str)
        Raises:
            UserError: If API key is not configured.
        """
        ICP = self.env['ir.config_parameter'].sudo()
        config = {
            'api_key': ICP.get_param('abj_biteship.api_key', '').strip(),
            'base_url': ICP.get_param(
                'abj_biteship.base_url', ABJ_DEFAULT_BASE_URL
            ).strip().rstrip('/'),
            'sender_name': ICP.get_param('abj_biteship.sender_name', '').strip(),
            'sender_phone': ICP.get_param('abj_biteship.sender_phone', '').strip(),
            'sender_email': ICP.get_param('abj_biteship.sender_email', '').strip(),
            'sender_org': ICP.get_param('abj_biteship.sender_org', '').strip(),
            'origin_address': ICP.get_param('abj_biteship.origin_address', '').strip(),
            'origin_postal_code': ICP.get_param('abj_biteship.origin_postal_code', '').strip(),
            'default_couriers': ICP.get_param('abj_biteship.default_couriers', 'jne,sicepat,anteraja').strip(),
        }
        if not config['api_key']:
            raise UserError(
                'API Key Biteship belum dikonfigurasi.\n'
                'Silakan isi di Settings → Biteship.'
            )
        return config

    # ══════════════════════════════════════════════════════════════════════
    # HTTP REQUEST ENGINE
    # ══════════════════════════════════════════════════════════════════════

    @api.model
    def _abj_make_request(self, method, endpoint, payload=None, retry=True):
        """
        Make an HTTP request to Biteship API with retry and logging.

        Args:
            method (str): HTTP method ('GET' or 'POST').
            endpoint (str): API endpoint path (e.g., '/v1/rates/couriers').
            payload (dict, optional): JSON payload for POST requests.
            retry (bool): Whether to retry on transient failures.

        Returns:
            dict: Parsed JSON response.

        Raises:
            UserError: On non-retryable errors or after max retries.
        """
        config = self._abj_get_config()
        url = f"{config['base_url']}{endpoint}"
        headers = {
            'Authorization': config['api_key'],
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        max_attempts = ABJ_MAX_RETRIES if retry else 1
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                _logger.info(
                    "ABJ_BITESHIP [%s] %s %s | Attempt %d/%d | Payload: %s",
                    method, url, endpoint, attempt, max_attempts,
                    json.dumps(payload, default=str) if payload else 'N/A',
                )
                if method.upper() == 'POST':
                    response = requests.post(
                        url, headers=headers, json=payload,
                        timeout=ABJ_REQUEST_TIMEOUT,
                    )
                elif method.upper() == 'GET':
                    response = requests.get(
                        url, headers=headers,
                        timeout=ABJ_REQUEST_TIMEOUT,
                    )
                elif method.upper() == 'DELETE':
                    response = requests.delete(
                        url, headers=headers,
                        timeout=ABJ_REQUEST_TIMEOUT,
                    )
                else:
                    raise UserError(f'Unsupported HTTP method: {method}')

                _logger.info(
                    "ABJ_BITESHIP [RESPONSE] %s %s | Status: %d | Body: %s",
                    method, endpoint, response.status_code,
                    response.text[:500],
                )

                # ── Handle non-2xx responses ──
                if response.status_code >= 400:
                    error_body = {}
                    try:
                        error_body = response.json()
                    except (ValueError, KeyError):
                        pass
                    error_msg = error_body.get('error', '') or error_body.get('message', '')
                    if not error_msg:
                        error_msg = f"HTTP {response.status_code}: {response.text[:200]}"

                    # 4xx = client error, don't retry
                    if 400 <= response.status_code < 500:
                        raise UserError(f'Biteship Error: {error_msg}')

                    # 5xx = server error, retry
                    last_error = error_msg
                    if attempt < max_attempts:
                        wait_time = ABJ_RETRY_BACKOFF ** attempt
                        _logger.warning(
                            "ABJ_BITESHIP [RETRY] Server error %d, retrying in %ds...",
                            response.status_code, wait_time,
                        )
                        time.sleep(wait_time)
                        continue
                    raise UserError(
                        f'Biteship Server Error setelah {max_attempts} percobaan: {error_msg}'
                    )

                return response.json()

            except requests.exceptions.Timeout:
                last_error = 'Request timeout'
                _logger.warning(
                    "ABJ_BITESHIP [TIMEOUT] %s %s | Attempt %d/%d",
                    method, endpoint, attempt, max_attempts,
                )
                if attempt < max_attempts:
                    wait_time = ABJ_RETRY_BACKOFF ** attempt
                    time.sleep(wait_time)
                    continue
                raise UserError(
                    f'Koneksi ke Biteship timeout setelah {max_attempts} percobaan.\n'
                    'Silakan coba lagi nanti.'
                )

            except requests.exceptions.ConnectionError:
                last_error = 'Connection error'
                _logger.error(
                    "ABJ_BITESHIP [CONNECTION_ERROR] %s %s | Attempt %d/%d",
                    method, endpoint, attempt, max_attempts,
                )
                if attempt < max_attempts:
                    wait_time = ABJ_RETRY_BACKOFF ** attempt
                    time.sleep(wait_time)
                    continue
                raise UserError(
                    'Gagal terhubung ke server Biteship.\n'
                    'Periksa koneksi internet dan coba lagi.'
                )

            except requests.exceptions.RequestException as e:
                _logger.error(
                    "ABJ_BITESHIP [REQUEST_ERROR] %s %s | %s",
                    method, endpoint, str(e),
                )
                raise UserError(f'Biteship API Error: {str(e)}')

        # Should not reach here, but just in case
        raise UserError(f'Biteship API Error: {last_error}')

    # ══════════════════════════════════════════════════════════════════════
    # PUBLIC API METHODS
    # ══════════════════════════════════════════════════════════════════════

    @api.model
    def abj_get_rates(self, origin_postal_code, destination_postal_code, items, couriers=None):
        """
        Fetch shipping rates from Biteship.

        Args:
            origin_postal_code (str/int): Origin postal code.
            destination_postal_code (str/int): Destination postal code.
            items (list[dict]): List of items, each with:
                - name (str)
                - value (int): Item value in IDR
                - weight (int): Weight in grams
                - quantity (int)
                - length (int, optional): cm
                - width (int, optional): cm
                - height (int, optional): cm
            couriers (str, optional): Comma-separated courier codes.
                Defaults to configured default_couriers.

        Returns:
            dict: Full API response with 'pricing' list.

        Raises:
            UserError: On validation or API errors.
        """
        if not origin_postal_code:
            raise UserError('Kode pos asal (origin) belum diisi di Settings → Biteship.')
        if not destination_postal_code:
            raise UserError('Kode pos tujuan (destination) belum diisi.')

        # Validate items
        if not items:
            raise UserError('Tidak ada item untuk dikirim.')
        for item in items:
            if not item.get('weight') or item['weight'] <= 0:
                raise UserError(
                    f"Berat produk \"{item.get('name', '?')}\" harus lebih dari 0.\n"
                    "Silakan isi berat produk terlebih dahulu."
                )

        if not couriers:
            config = self._abj_get_config()
            couriers = config['default_couriers']

        payload = {
            'origin_postal_code': int(origin_postal_code),
            'destination_postal_code': int(destination_postal_code),
            'couriers': couriers,
            'items': items,
        }

        return self._abj_make_request('POST', '/v1/rates/couriers', payload)

    @api.model
    def abj_create_shipment(self, payload):
        """
        Create a shipment order on Biteship.

        The payload should follow Biteship's order creation format:
        - shipper_contact_name, shipper_contact_phone, shipper_contact_email
        - shipper_organization
        - origin_contact_name, origin_contact_phone, origin_address, origin_postal_code
        - destination_contact_name, destination_contact_phone, destination_address, destination_postal_code
        - courier_company, courier_type
        - delivery_type ('now' or 'scheduled')
        - items (list)

        Args:
            payload (dict): Full order creation payload.

        Returns:
            dict: API response with order details (id, waybill_id, tracking_id, etc.)
        """
        # Validate essential fields
        required_fields = [
            'origin_contact_name', 'origin_contact_phone',
            'origin_address', 'origin_postal_code',
            'destination_contact_name', 'destination_contact_phone',
            'destination_address', 'destination_postal_code',
            'courier_company', 'courier_type',
            'items',
        ]
        missing = [f for f in required_fields if not payload.get(f)]
        if missing:
            raise UserError(
                'Data pengiriman tidak lengkap.\n'
                f"Field yang kosong: {', '.join(missing)}"
            )

        return self._abj_make_request('POST', '/v1/orders', payload)

    @api.model
    def abj_get_tracking(self, tracking_id):
        """
        Retrieve tracking information by Biteship tracking ID.

        Args:
            tracking_id (str): Biteship internal tracking ID
                (from order creation response: courier.tracking_id).

        Returns:
            dict: Tracking status and history.
        """
        if not tracking_id:
            raise UserError('Tracking ID tidak tersedia.')

        return self._abj_make_request('GET', f'/v1/trackings/{tracking_id}', retry=False)

    @api.model
    def abj_retrieve_order(self, order_id):
        """
        Retrieve full order details from Biteship.

        Args:
            order_id (str): Biteship order ID.

        Returns:
            dict: Full order details including status, courier info, etc.
        """
        if not order_id:
            raise UserError('Order ID Biteship tidak tersedia.')

        return self._abj_make_request('GET', f'/v1/orders/{order_id}', retry=False)

    @api.model
    def abj_get_tracking_public(self, waybill_id, courier_code):
        """
        Retrieve tracking via public endpoint (no Biteship order required).

        Args:
            waybill_id (str): Courier waybill/AWB number.
            courier_code (str): Courier company code (e.g., 'jne').

        Returns:
            dict: Tracking status and history.
        """
        if not waybill_id or not courier_code:
            raise UserError('Nomor resi dan kode kurir harus diisi.')

        return self._abj_make_request(
            'GET',
            f'/v1/trackings/{waybill_id}/couriers/{courier_code}',
            retry=False,
        )
