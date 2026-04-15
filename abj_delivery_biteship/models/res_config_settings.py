# -*- coding: utf-8 -*-
"""
Configuration Settings for Biteship Integration
================================================
Stores API credentials and sender information
via ir.config_parameter (System Parameters).
"""
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ── Biteship API Credentials ─────────────────────────────────────────
    abj_biteship_api_key = fields.Char(
        string='Biteship API Key',
        config_parameter='abj_biteship.api_key',
        help='API Key dari dashboard Biteship. '
             'Format: biteship_live.xxx atau biteship_test.xxx',
    )
    abj_biteship_base_url = fields.Char(
        string='Biteship Base URL',
        config_parameter='abj_biteship.base_url',
        default='https://api.biteship.com',
        help='Base URL API Biteship. '
             'Production: https://api.biteship.com',
    )

    # ── Sender / Shipper Information ─────────────────────────────────────
    abj_biteship_sender_name = fields.Char(
        string='Nama Pengirim',
        config_parameter='abj_biteship.sender_name',
        help='Nama kontak pengirim yang akan tercetak di label pengiriman.',
    )
    abj_biteship_sender_phone = fields.Char(
        string='No. HP Pengirim',
        config_parameter='abj_biteship.sender_phone',
        help='Nomor telepon pengirim.',
    )
    abj_biteship_sender_email = fields.Char(
        string='Email Pengirim',
        config_parameter='abj_biteship.sender_email',
    )
    abj_biteship_sender_org = fields.Char(
        string='Organisasi / Nama Toko',
        config_parameter='abj_biteship.sender_org',
        help='Nama organisasi atau toko pengirim.',
    )

    # ── Origin Address ───────────────────────────────────────────────────
    abj_biteship_origin_address = fields.Char(
        string='Alamat Asal (Origin)',
        config_parameter='abj_biteship.origin_address',
        help='Alamat lengkap gudang / toko pengirim.',
    )
    abj_biteship_origin_postal_code = fields.Char(
        string='Kode Pos Asal',
        config_parameter='abj_biteship.origin_postal_code',
        help='Kode pos lokasi pengirim. Digunakan untuk kalkulasi ongkir.',
    )

    # ── Default Couriers ─────────────────────────────────────────────────
    abj_biteship_default_couriers = fields.Char(
        string='Kurir Default',
        config_parameter='abj_biteship.default_couriers',
        default='jne,sicepat,anteraja',
        help='Daftar kode kurir yang akan ditampilkan saat cek ongkir, '
             'pisahkan dengan koma. Contoh: jne,sicepat,anteraja,tiki,ninja',
    )
