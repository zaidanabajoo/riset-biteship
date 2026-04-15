# -*- coding: utf-8 -*-
{
    'name': 'ABJ Delivery Biteship – Website eCommerce',
    'version': '19.0.1.0.0',
    'category': 'Website/Website',
    'summary': 'Extension eCommerce untuk Biteship – Checkout Integration & Rate Caching',
    'description': """
        Extension module untuk ABJ Delivery Biteship:
        - Integrasi Biteship Rates ke eCommerce Checkout
        - Implementasi 1-carrier-per-service (JNE REG, SiCepat BEST, dll.)
        - Caching layer untuk optimasi API (1 API call per checkout load)
        - Seed data untuk kurir-kurir populer
    """,
    'author': 'PT. Abajoo Transformasi Teknologi, Zaidan Habitullah Husni',
    'website': 'https://abajoo.com',
    'license': 'LGPL-3',
    'depends': [
        'abj_delivery_biteship',
        'website_sale',
        'website_sale_delivery',
    ],
    'data': [
        'data/abj_carrier_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
