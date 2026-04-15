# -*- coding: utf-8 -*-
"""
Unit Tests for abj_delivery_biteship Module
=============================================
Tests cover:
- Rate fetching (success / error / zero weight)
- Shipment creation (success / timeout)
- Webhook processing (status / waybill / idempotency)
"""
import json
import logging
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


# ── Mock Biteship API Responses ──────────────────────────────────────────
MOCK_RATES_RESPONSE = {
    'success': True,
    'object': 'courier_pricing',
    'message': 'Success to retrieve courier pricing',
    'pricing': [
        {
            'company': 'jne',
            'courier_name': 'JNE',
            'courier_code': 'jne',
            'courier_service_name': 'Reguler',
            'courier_service_code': 'reg',
            'service_type': 'standard',
            'shipping_fee': 15000,
            'price': 15000,
            'duration': '2 - 3 days',
            'description': 'Layanan reguler',
            'insurance_fee': 0,
        },
        {
            'company': 'sicepat',
            'courier_name': 'SiCepat',
            'courier_code': 'sicepat',
            'courier_service_name': 'BEST (Besok Sampai Tujuan)',
            'courier_service_code': 'best',
            'service_type': 'overnight',
            'shipping_fee': 25000,
            'price': 25000,
            'duration': '1 days',
            'description': 'Besok sampai tujuan',
            'insurance_fee': 1000,
        },
    ],
}

MOCK_CREATE_SHIPMENT_RESPONSE = {
    'success': True,
    'message': 'Order successfully created',
    'object': 'order',
    'id': '5dd599ebdefcd4158eb8470b',
    'status': 'confirmed',
    'courier': {
        'tracking_id': '6de509ebdefgh4158ij3451c',
        'waybill_id': 'WYB-1112223333443',
        'company': 'jne',
        'type': 'reg',
    },
    'price': 15000,
}

MOCK_TRACKING_RESPONSE = {
    'success': True,
    'object': 'tracking',
    'id': '6de509ebdefgh4158ij3451c',
    'waybill_id': 'WYB-1112223333443',
    'courier': {
        'company': 'jne',
        'tracking_id': '6de509ebdefgh4158ij3451c',
        'waybill_id': 'WYB-1112223333443',
        'driver_name': 'Budi',
        'driver_phone': '081234567890',
    },
    'status': 'picked',
}


@tagged('post_install', '-at_install')
class TestAbjBiteshipApi(TransactionCase):
    """Test cases for the Biteship API service layer."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # ── Set up config parameters ──
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_param('abj_biteship.api_key', 'biteship_test.test_key_123')
        ICP.set_param('abj_biteship.base_url', 'https://api.biteship.com')
        ICP.set_param('abj_biteship.sender_name', 'Test Store')
        ICP.set_param('abj_biteship.sender_phone', '081234567890')
        ICP.set_param('abj_biteship.sender_email', 'test@store.com')
        ICP.set_param('abj_biteship.sender_org', 'Test Org')
        ICP.set_param('abj_biteship.origin_address', 'Jl. Test No. 1')
        ICP.set_param('abj_biteship.origin_postal_code', '12440')
        ICP.set_param('abj_biteship.default_couriers', 'jne,sicepat')

    def test_abj_get_config(self):
        """Test configuration retrieval."""
        api_service = self.env['abj.biteship.api']
        config = api_service._abj_get_config()
        self.assertEqual(config['api_key'], 'biteship_test.test_key_123')
        self.assertEqual(config['base_url'], 'https://api.biteship.com')
        self.assertEqual(config['sender_name'], 'Test Store')
        self.assertEqual(config['origin_postal_code'], '12440')

    def test_abj_get_config_missing_key(self):
        """Test that missing API key raises UserError."""
        self.env['ir.config_parameter'].sudo().set_param('abj_biteship.api_key', '')
        api_service = self.env['abj.biteship.api']
        with self.assertRaises(UserError):
            api_service._abj_get_config()
        # Restore
        self.env['ir.config_parameter'].sudo().set_param(
            'abj_biteship.api_key', 'biteship_test.test_key_123',
        )

    @patch('odoo.addons.abj_delivery_biteship.models.abj_biteship_api.requests')
    def test_abj_get_rates_success(self, mock_requests):
        """Test successful rate fetching."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_RATES_RESPONSE
        mock_response.text = json.dumps(MOCK_RATES_RESPONSE)
        mock_requests.post.return_value = mock_response

        api_service = self.env['abj.biteship.api']
        result = api_service.abj_get_rates(
            origin_postal_code='12440',
            destination_postal_code='12240',
            items=[{
                'name': 'Test Product',
                'value': 100000,
                'weight': 500,
                'quantity': 1,
                'length': 10,
                'width': 10,
                'height': 10,
            }],
            couriers='jne,sicepat',
        )

        self.assertTrue(result.get('success'))
        self.assertEqual(len(result.get('pricing', [])), 2)
        self.assertEqual(result['pricing'][0]['courier_code'], 'jne')
        self.assertEqual(result['pricing'][0]['price'], 15000)

    def test_abj_get_rates_zero_weight(self):
        """Test that zero weight raises UserError."""
        api_service = self.env['abj.biteship.api']
        with self.assertRaises(UserError):
            api_service.abj_get_rates(
                origin_postal_code='12440',
                destination_postal_code='12240',
                items=[{
                    'name': 'Zero Weight Product',
                    'value': 100000,
                    'weight': 0,
                    'quantity': 1,
                }],
            )

    def test_abj_get_rates_missing_postal(self):
        """Test that missing postal code raises UserError."""
        api_service = self.env['abj.biteship.api']
        with self.assertRaises(UserError):
            api_service.abj_get_rates(
                origin_postal_code='',
                destination_postal_code='12240',
                items=[{'name': 'Test', 'value': 10000, 'weight': 500, 'quantity': 1}],
            )

    @patch('odoo.addons.abj_delivery_biteship.models.abj_biteship_api.requests')
    def test_abj_create_shipment_success(self, mock_requests):
        """Test successful shipment creation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_CREATE_SHIPMENT_RESPONSE
        mock_response.text = json.dumps(MOCK_CREATE_SHIPMENT_RESPONSE)
        mock_requests.post.return_value = mock_response

        api_service = self.env['abj.biteship.api']
        result = api_service.abj_create_shipment({
            'origin_contact_name': 'Test Store',
            'origin_contact_phone': '081234567890',
            'origin_address': 'Jl. Test No. 1',
            'origin_postal_code': 12440,
            'destination_contact_name': 'Customer',
            'destination_contact_phone': '089876543210',
            'destination_address': 'Jl. Customer No. 2',
            'destination_postal_code': 12240,
            'courier_company': 'jne',
            'courier_type': 'reg',
            'delivery_type': 'now',
            'items': [{
                'name': 'Product',
                'value': 100000,
                'weight': 500,
                'quantity': 1,
                'length': 10,
                'width': 10,
                'height': 10,
            }],
        })

        self.assertTrue(result.get('success'))
        self.assertEqual(result['id'], '5dd599ebdefcd4158eb8470b')
        self.assertEqual(result['courier']['waybill_id'], 'WYB-1112223333443')

    @patch('odoo.addons.abj_delivery_biteship.models.abj_biteship_api.requests')
    def test_abj_create_shipment_timeout(self, mock_requests):
        """Test shipment creation timeout handling."""
        import requests as req_lib
        mock_requests.post.side_effect = req_lib.exceptions.Timeout('Connection timed out')
        mock_requests.exceptions = req_lib.exceptions

        api_service = self.env['abj.biteship.api']
        with self.assertRaises(UserError) as ctx:
            api_service.abj_create_shipment({
                'origin_contact_name': 'Test',
                'origin_contact_phone': '081234567890',
                'origin_address': 'Test',
                'origin_postal_code': 12440,
                'destination_contact_name': 'Cust',
                'destination_contact_phone': '089876543210',
                'destination_address': 'Test',
                'destination_postal_code': 12240,
                'courier_company': 'jne',
                'courier_type': 'reg',
                'items': [{'name': 'P', 'value': 1000, 'weight': 100, 'quantity': 1}],
            })
        self.assertIn('timeout', str(ctx.exception).lower())

    def test_abj_create_shipment_missing_fields(self):
        """Test that missing required fields raise UserError."""
        api_service = self.env['abj.biteship.api']
        with self.assertRaises(UserError) as ctx:
            api_service.abj_create_shipment({
                'origin_contact_name': 'Test',
                # Missing many required fields
            })
        self.assertIn('tidak lengkap', str(ctx.exception).lower())


@tagged('post_install', '-at_install')
class TestAbjBiteshipWebhook(TransactionCase):
    """Test cases for webhook processing."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Set up config
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_param('abj_biteship.api_key', 'biteship_test.test_key_123')
        ICP.set_param('abj_biteship.origin_postal_code', '12440')

        # Create a test picking
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Customer Biteship',
            'zip': '12240',
            'phone': '089876543210',
            'street': 'Jl. Customer Test',
        })

        # Find picking type for outgoing
        picking_type = cls.env.ref('stock.picking_type_out', raise_if_not_found=False)
        if not picking_type:
            picking_type = cls.env['stock.picking.type'].search(
                [('code', '=', 'outgoing')], limit=1,
            )

        location_src = cls.env.ref('stock.stock_location_stock', raise_if_not_found=False)
        location_dest = cls.env.ref('stock.stock_location_customers', raise_if_not_found=False)

        cls.picking = cls.env['stock.picking'].create({
            'partner_id': cls.partner.id,
            'picking_type_id': picking_type.id if picking_type else False,
            'location_id': location_src.id if location_src else False,
            'location_dest_id': location_dest.id if location_dest else False,
            'abj_shipment_id': 'BITESHIP_TEST_ORDER_001',
            'abj_pickup_status': 'confirmed',
            'abj_delivery_status': 'confirmed',
        })

    def test_abj_webhook_status_update(self):
        """Test that webhook correctly updates picking status."""
        from odoo.addons.abj_delivery_biteship.models.stock_picking import ABJ_BITESHIP_STATUS_MAP

        # Simulate status update
        self.picking._abj_update_from_tracking_response({
            'status': 'picked',
            'courier': {
                'tracking_id': 'TRACK123',
                'waybill_id': 'WYB-999',
                'driver_name': 'Test Driver',
            },
            'price': 18000,
        })

        self.assertEqual(self.picking.abj_pickup_status, 'picked')
        self.assertEqual(self.picking.abj_delivery_status, 'picked')
        self.assertEqual(self.picking.abj_tracking_number, 'WYB-999')
        self.assertEqual(self.picking.abj_biteship_tracking_id, 'TRACK123')

    def test_abj_webhook_idempotency(self):
        """Test that duplicate webhook does not create duplicate chatter messages."""
        self.picking.write({
            'abj_delivery_status': 'picked',
            'abj_pickup_status': 'picked',
        })

        # Count existing messages
        msg_count_before = len(self.picking.message_ids)

        # Send same status — should skip update
        self.picking._abj_update_from_tracking_response({
            'status': 'picked',
        })

        msg_count_after = len(self.picking.message_ids)
        # No new message should be posted
        self.assertEqual(msg_count_before, msg_count_after)

    def test_abj_webhook_waybill_update(self):
        """Test waybill update via tracking response."""
        self.picking.write({
            'abj_delivery_status': 'confirmed',
            'abj_tracking_number': '',
        })

        self.picking._abj_update_from_tracking_response({
            'status': 'picked',
            'courier': {
                'waybill_id': 'NEW-WAYBILL-123',
                'tracking_id': 'NEW-TRACK-456',
            },
        })

        self.assertEqual(self.picking.abj_tracking_number, 'NEW-WAYBILL-123')
        self.assertEqual(self.picking.carrier_tracking_ref, 'NEW-WAYBILL-123')
        self.assertEqual(self.picking.abj_biteship_tracking_id, 'NEW-TRACK-456')

    def test_abj_shipment_guard(self):
        """Test that duplicate shipment creation is prevented."""
        self.picking.write({'abj_shipment_id': 'EXISTING_ORDER'})

        with self.assertRaises(UserError) as ctx:
            self.picking.action_abj_create_biteship_shipment()
        self.assertIn('sudah dibuat', str(ctx.exception).lower())
