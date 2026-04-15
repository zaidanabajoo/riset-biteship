# ABJ Delivery Biteship — Odoo 19

Modul integrasi **Odoo 19** dengan **Biteship API** untuk manajemen pengiriman end-to-end.

## 🎯 Fitur Utama

| Fitur | Deskripsi |
|---|---|
| **Cek Ongkir (Rates)** | Hitung ongkos kirim multi-kurir langsung dari Sales Order |
| **Buat Pengiriman** | Create shipment & request pickup otomatis dari Delivery Order |
| **Tracking Real-time** | Update status via **Webhook** (primary) + Cron (fallback) |
| **Wizard Tarif** | Pilih kurir & layanan dari daftar tarif Biteship |
| **Multi-kurir** | JNE, SiCepat, AnterAja, J&T, Ninja, Tiki, dan lainnya |

---

## 📦 Instalasi

1. Copy folder `abj_delivery_biteship` ke direktori `custom/` addons Odoo
2. Restart Odoo server
3. Buka menu **Apps** → Cari "Biteship" → Klik **Install**

---

## ⚙️ Konfigurasi

### 1. API Key

1. Daftar di [dashboard.biteship.com](https://dashboard.biteship.com)
2. Generate API Key (format: `biteship_live.xxx` atau `biteship_test.xxx`)
3. Buka **Settings** → cari section **Integrasi Logistik: Biteship**
4. Isi:
   - **API Key Biteship** → paste API key
   - **Base URL** → `https://api.biteship.com` (default)
   - **Kurir Default** → `jne,sicepat,anteraja` (pisahkan dengan koma)

### 2. Data Pengirim

Lengkapi data pengirim di Settings → Biteship:
- Nama Pengirim
- No. HP
- Email
- Organisasi / Nama Toko

### 3. Alamat Asal (Origin)

- **Alamat Gudang** → Alamat lengkap pengirim
- **Kode Pos Asal** → Kode pos gudang/toko (WAJIB untuk cek ongkir)

### 4. Webhook (PENTING!)

1. Buka [dashboard.biteship.com](https://dashboard.biteship.com) → menu **Webhook**
2. Tambahkan URL:
   ```
   https://your-odoo-domain.com/abj/biteship/webhook
   ```
3. Aktifkan event:
   - ✅ `order.status`
   - ✅ `order.price`
   - ✅ `order.waybill_id`

> ⚠️ **PENTING**: Domain Odoo harus bisa diakses publik (HTTPS).

---

## 🔄 Penggunaan

### Flow 1: Cek Ongkir dari Sales Order

1. Buka Sales Order (draft)
2. Klik tombol **🚚 Get Shipping Rates**
3. Wizard tampil dengan daftar tarif (diurutkan termurah)
4. Pilih tarif → klik **Pilih Tarif** atau **Termurah**
5. Kurir, layanan, dan biaya tersimpan di Sales Order

### Flow 2: Buat Pengiriman dari Delivery Order

1. Konfirmasi Sales Order → Delivery Order terbuat
2. Validate picking (pastikan barang ready)
3. Klik tombol **📦 Create Shipment & Request Pickup**
4. Sistem akan:
   - Create order di Biteship
   - Trigger pickup otomatis (delivery_type: now)
   - Simpan nomor resi (waybill), order ID, tracking ID
5. Update status berjalan otomatis via webhook

### Flow 3: Tracking

- **Otomatis**: Webhook update status real-time ke chatter
- **Manual**: Klik **🔄 Refresh Status** di Delivery Order
- **Cron**: Backup sync setiap 30 menit (untuk shipment aktif)

---

## 🧩 Field Extensions

### Sale Order
| Field | Deskripsi |
|---|---|
| `abj_shipping_cost` | Biaya pengiriman terpilih |
| `abj_selected_courier` | Nama kurir terpilih |
| `abj_selected_service` | Kode layanan terpilih |

### Stock Picking (Delivery Order)
| Field | Deskripsi |
|---|---|
| `abj_tracking_number` | Nomor resi / waybill (customer-facing) |
| `abj_shipment_id` | Biteship Order ID |
| `abj_biteship_tracking_id` | Biteship internal tracking ID |
| `abj_courier_name` | Nama kurir |
| `abj_service_type` | Tipe layanan |
| `abj_pickup_status` | Status pengiriman (selection) |
| `abj_delivery_status` | Status mentah dari Biteship |
| `abj_shipping_cost` | Biaya pengiriman aktual |

### Delivery Carrier
| Field | Deskripsi |
|---|---|
| `abj_biteship_courier_code` | Kode kurir Biteship |
| `abj_biteship_service_type` | Kode tipe layanan |

---

## 🔌 API Endpoints Biteship yang Digunakan

| Method | Endpoint | Deskripsi |
|---|---|---|
| `POST` | `/v1/rates/couriers` | Cek ongkir |
| `POST` | `/v1/orders` | Buat order pengiriman |
| `GET` | `/v1/orders/:id` | Detail order |
| `GET` | `/v1/trackings/:id` | Tracking by Biteship ID |
| `GET` | `/v1/trackings/:waybill/couriers/:code` | Tracking publik |

---

## 🔑 Perbedaan Penting: ID Biteship

| Field | API Key | Deskripsi |
|---|---|---|
| `abj_shipment_id` | `id` (order response) | ID order internal Biteship |
| `abj_biteship_tracking_id` | `courier.tracking_id` | ID tracking internal (untuk API) |
| `abj_tracking_number` | `courier.waybill_id` | Nomor resi kurir (untuk customer) |

---

## 🧪 Testing

```bash
# Run unit tests
python odoo-bin -c riset.conf \
  --test-enable \
  --test-tags abj_delivery_biteship \
  -i abj_delivery_biteship \
  --stop-after-init
```

---

## 📋 Dependencies

- `base`
- `sale`
- `stock`
- `delivery`
- `stock_delivery`
- `contacts`

---

## 📝 Catatan Teknis

1. **Webhook = Source of Truth**: Cron hanya sebagai fallback
2. **Idempotency**: Webhook handler cek status sebelum update (skip jika sama)
3. **Retry**: API calls retry max 3x dengan exponential backoff (2s, 4s, 8s)
4. **Timeout**: Semua API call pakai timeout 30 detik
5. **Logging**: Semua request/response tercatat di log (`ABJ_BITESHIP`)
6. **Guard**: Tidak bisa create shipment dua kali untuk picking yang sama

---

## 📄 Lisensi

LGPL-3

## 👤 Author

**Abajoo** — [abajoo.com](https://abajoo.com)
