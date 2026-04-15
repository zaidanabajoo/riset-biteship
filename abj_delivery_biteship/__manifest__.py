# -*- coding: utf-8 -*-
{
    'name': 'ABJ Delivery Biteship',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Delivery',
    'summary': 'Integrasi Pengiriman Biteship – Rates, Shipment, Tracking & Webhook',
    'description': """
        Modul integrasi Odoo 19 dengan Biteship API:
        - Kalkulasi ongkos kirim multi-kurir (JNE, SiCepat, AnterAja, dll.)
        - Pembuatan order pengiriman otomatis
        - Request pickup otomatis
        - Tracking real-time via API & Webhook
        - Cron job fallback untuk sync status
    """,
    'author': 'PT. Abajoo Transformasi Teknologi, Zaidan Habitullah Husni',
    'website': 'https://abajoo.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'sale',
        'stock',
        'delivery',
        'stock_delivery',
        'contacts',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/abj_cron_data.xml',
        'wizards/abj_biteship_rate_wizard_views.xml',
        'views/res_config_settings_views.xml',
        'views/delivery_carrier_views.xml',
        'views/sale_order_views.xml',
        'views/stock_picking_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
