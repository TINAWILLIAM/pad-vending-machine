# 🩸 Pad Vending Machine – Backend

Production-ready **FastAPI** backend for an IoT-enabled sanitary pad vending machine system.  
Handles authentication, OTP, payments (Razorpay), ESP32 communication, stock management, and order history.

---

## 📁 Project Structure

```
pad-vending-backend/
├── app/
│   ├── main.py              # FastAPI app factory + router registration
│   ├── config.py            # Pydantic settings (reads .env)
│   ├── database.py          # Motor async MongoDB client
│   ├── models/
│   │   ├── user_model.py
│   │   ├── product_model.py
│   │   ├── machine_model.py
│   │   ├── cart_model.py
│   │   └── order_model.py
│   ├── routes/
│   │   ├── auth_routes.py      # POST /auth/send-otp, /auth/verify-otp
│   │   ├── location_routes.py  # POST /location/update, GET /location/nearest-machine
│   │   ├── product_routes.py   # CRUD /products
│   │   ├── cart_routes.py      # /cart/add, /cart/remove, /cart/{user_id}
│   │   ├── order_routes.py     # /order/create, /order/{id}, /order/history/{user_id}
│   │   ├── payment_routes.py   # POST /payment/create-order
│   │   ├── webhook_routes.py   # POST /payment/webhook  ← Razorpay only
│   │   ├── machine_routes.py   # /machine CRUD + stock
│   │   └── iot_routes.py       # /iot ESP32 communication
│   ├── services/
│   │   ├── otp_service.py
│   │   ├── razorpay_service.py
│   │   ├── esp32_service.py
│   │   ├── order_service.py
│   │   └── machine_service.py
│   └── utils/
│       ├── logger.py
│       ├── location_utils.py
│       ├── payment_verification.py
│       └── qr_generator.py
├── scripts/
│   ├── start_dev.ps1         # PowerShell: start backend
│   ├── start_tunnel.ps1      # PowerShell: Cloudflare tunnel + QR
│   ├── generate_qr.py        # CLI QR code generator
│   └── seed_data.py          # Seed products and demo machine
├── .env                      # Environment variables (copy from below)
├── requirements.txt
└── README.md
```

---

## ⚡ Quick Start

### 1. Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.10+ | [python.org](https://python.org) |
| MongoDB | 6.0+ | [mongodb.com](https://mongodb.com/try/download/community) |
| Git | any | [git-scm.com](https://git-scm.com) |

---

### 2. VS Code Setup

1. Open VS Code
2. **File → Open Folder** → select `pad-vending-backend/`
3. Install recommended extensions (VS Code will prompt):
   - **Python** (ms-python.python)
   - **Pylance** (ms-python.vscode-pylance)
   - **Thunder Client** (rangav.vscode-thunder-client) — for API testing
   - **MongoDB for VS Code** (mongodb.mongodb-vscode)

---

### 3. Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

---

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 5. Configure Environment

Edit `.env` with your credentials:

```env
# MongoDB
MONGO_URI=mongodb://localhost:27017
DB_NAME=pad_vending_db

# Email (Gmail App Password recommended)
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=your-email@gmail.com

# Razorpay (test keys from dashboard.razorpay.com)
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxx
RAZORPAY_KEY_SECRET=your-secret
RAZORPAY_WEBHOOK_SECRET=your-webhook-secret

# Frontend URL (Angular dev server)
FRONTEND_URL=http://localhost:4200
ALLOWED_ORIGINS=http://localhost:4200
```

---

### 6. Seed Initial Data

```bash
python scripts/seed_data.py
```

Creates:
- 3 products (Regular ₹10, Medium ₹15, XL ₹20)
- 1 demo machine with 50 units of each product

---

### 7. Start the Server

```bash
# Method A – direct
uvicorn app.main:app --reload --port 8000

# Method B – PowerShell script (Windows)
.\scripts\start_dev.ps1
```

Server runs at: **http://localhost:8000**  
Swagger docs: **http://localhost:8000/docs**  
ReDoc: **http://localhost:8000/redoc**

---

## 🔌 API Reference

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/send-otp` | Send 4-digit OTP to email |
| POST | `/auth/verify-otp` | Verify OTP, receive JWT |

### Location

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/location/update` | Submit GPS coords, get nearest machine |
| GET | `/location/nearest-machine?lat=&lon=` | Get nearest machine |

### Products

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/products?machine_id=` | List products with stock |
| POST | `/products` | Create product |
| GET | `/products/{id}` | Get product |
| PATCH | `/products/{id}` | Update product |
| DELETE | `/products/{id}` | Soft-delete product |

### Cart

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/cart/{user_id}?machine_id=` | Get cart |
| POST | `/cart/add` | Add to cart |
| POST | `/cart/remove` | Remove from cart |
| DELETE | `/cart/{user_id}?machine_id=` | Clear cart |

### Orders

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/order/create` | Create order from cart |
| GET | `/order/{order_id}` | Get order |
| GET | `/order/history/{user_id}` | Order history |
| POST | `/order/vend` | Trigger dispense (Vend Now) |

### Payment

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/payment/create-order` | Create Razorpay order |
| POST | `/payment/webhook` | Razorpay webhook (signature verified) |

### Machines

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/machine/register` | Register machine |
| GET | `/machine` | List all machines |
| GET | `/machine/{id}` | Get machine |
| PATCH | `/machine/{id}` | Update machine |
| POST | `/machine/nearest` | Nearest machine by GPS |
| PUT | `/machine/{id}/stock` | Set product stock |
| GET | `/machine/{id}/stock` | Get stock |

### IoT / ESP32

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/iot/status-update` | ESP32 heartbeat |
| GET | `/iot/pending-commands/{machine_id}` | ESP32 polls for commands |
| POST | `/iot/dispense-result` | ESP32 reports dispense result |
| POST | `/iot/command/dispense` | Admin: push dispense command |

---

## 📱 Development with Cloudflare Tunnel

```powershell
# 1. Start Angular frontend
ng serve

# 2. Start backend
uvicorn app.main:app --reload

# 3. Open tunnel to frontend (separate terminal)
.\scripts\start_tunnel.ps1

# 4. Scan the generated QR code with your phone
```

---

## 🧪 Testing the API

### Using Swagger UI
Open http://localhost:8000/docs and test endpoints interactively.

### Using curl

```bash
# Send OTP
curl -X POST http://localhost:8000/auth/send-otp \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'

# Verify OTP
curl -X POST http://localhost:8000/auth/verify-otp \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "otp": "1234"}'

# List products
curl http://localhost:8000/products

# Get nearest machine
curl "http://localhost:8000/location/nearest-machine?lat=12.97&lon=77.59"
```

---

## 🔒 Security Notes

- **Payment is ONLY confirmed via Razorpay webhook** (`/payment/webhook`)
- Webhook signature is verified with HMAC-SHA256 before any DB update
- Frontend never confirms payment status
- JWT tokens expire after 24 hours
- OTPs expire after 10 minutes and are single-use

---

## 🗃️ MongoDB Collections

| Collection | Purpose |
|------------|---------|
| `users` | Authenticated users |
| `otps` | Active OTPs (TTL index auto-expires) |
| `products` | Pad products |
| `machines` | Vending machines + stock |
| `carts` | User shopping carts |
| `orders` | All orders and status |
| `payments` | Razorpay payment records |
| `pending_commands` | Queued ESP32 commands |
| `machine_telemetry` | ESP32 health data |

---

## 🔄 Order Status Flow

```
PENDING_PAYMENT
    ↓ (webhook: payment.captured)
PAYMENT_VERIFIED
    ↓ (user clicks Vend Now)
DISPENSING
    ↓                    ↓
COMPLETED          FAILED_DISPENSE
                        ↓ (retry)
                    DISPENSING …
```

---

## 🛠️ Common Issues

**MongoDB connection refused**  
→ Start MongoDB service: `net start MongoDB` (Windows) or `brew services start mongodb-community`

**OTP email not sending**  
→ Use Gmail App Password (not your Gmail password). Enable 2FA first.

**Razorpay webhook not received locally**  
→ Use ngrok or Cloudflare Tunnel to expose port 8000 and set the webhook URL in Razorpay dashboard.

**ESP32 unreachable**  
→ Ensure ESP32 and backend are on the same network, or configure `esp32_endpoint` with a public URL.
