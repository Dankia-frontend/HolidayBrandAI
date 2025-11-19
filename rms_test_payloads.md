# RMS API Test Payloads

All endpoints require authentication via Bearer token in the Authorization header.

**Authentication Header:**
```
Authorization: Bearer aIUTD3R0t1
```

---

## 1️⃣ Search Availability

**Endpoint:** `POST /api/rms/search`

**Description:** Search for available rooms with pricing.

### Test Case 1: Basic Search (All Rooms)

```json
{
  "arrival": "2025-11-15",
  "departure": "2025-11-16",
  "adults": 2,
  "children": 0
}
```

**cURL:**
```bash
curl -X POST "http://localhost:8000/api/rms/search" \
  -H "Authorization: Bearer aIUTD3R0t1" \
  -H "Content-Type: application/json" \
  -d '{
    "arrival": "2025-11-15",
    "departure": "2025-11-16",
    "adults": 2,
    "children": 0
  }'
```

---

### Test Case 2: Search Specific Room Type (Deluxe)

```json
{
  "arrival": "2025-11-15",
  "departure": "2025-11-17",
  "adults": 2,
  "children": 1,
  "room_keyword": "deluxe"
}
```

**cURL:**
```bash
curl -X POST "http://localhost:8000/api/rms/search" \
  -H "Authorization: Bearer aIUTD3R0t1" \
  -H "Content-Type: application/json" \
  -d '{
    "arrival": "2025-11-15",
    "departure": "2025-11-17",
    "adults": 2,
    "children": 1,
    "room_keyword": "deluxe"
  }'
```

---

### Test Case 3: Search Suite Rooms

```json
{
  "arrival": "2025-12-20",
  "departure": "2025-12-25",
  "adults": 4,
  "children": 2,
  "room_keyword": "suite"
}
```

**cURL:**
```bash
curl -X POST "http://localhost:8000/api/rms/search" \
  -H "Authorization: Bearer aIUTD3R0t1" \
  -H "Content-Type: application/json" \
  -d '{
    "arrival": "2025-12-20",
    "departure": "2025-12-25",
    "adults": 4,
    "children": 2,
    "room_keyword": "suite"
  }'
```

---

### Expected Response Format:

```json
{
  "available": [
    {
      "category_id": 4,
      "category_name": "Deluxe Room",
      "rate_plan_id": 1417,
      "rate_plan_name": "OTA",
      "price": 140.00,
      "total_price": 140.00,
      "currency": "USD"
    },
    {
      "category_id": 5,
      "category_name": "Deluxe Suite",
      "rate_plan_id": 1419,
      "rate_plan_name": "Standard",
      "price": 210.00,
      "total_price": 210.00,
      "currency": "USD"
    }
  ],
  "message": "Found 2 available room(s)"
}
```

---

## 2️⃣ Create Reservation

**Endpoint:** `POST /api/rms/reservations`

**Description:** Create a new booking.

### Test Case 1: Basic Reservation

```json
{
  "category_id": 4,
  "rate_plan_id": 1417,
  "arrival": "2025-11-15",
  "departure": "2025-11-16",
  "adults": 2,
  "children": 0,
  "guest": {
    "firstName": "John",
    "lastName": "Doe",
    "email": "john.doe@example.com",
    "phone": "+1234567890",
    "address": {
      "street": "123 Main St",
      "city": "New York",
      "state": "NY",
      "postcode": "10001",
      "country": "USA"
    }
  }
}
```

**cURL:**
```bash
curl -X POST "http://localhost:8000/api/rms/reservations" \
  -H "Authorization: Bearer aIUTD3R0t1" \
  -H "Content-Type: application/json" \
  -d '{
    "category_id": 4,
    "rate_plan_id": 1417,
    "arrival": "2025-11-15",
    "departure": "2025-11-16",
    "adults": 2,
    "children": 0,
    "guest": {
      "firstName": "John",
      "lastName": "Doe",
      "email": "john.doe@example.com",
      "phone": "+1234567890"
    }
  }'
```

---

### Test Case 2: Family Reservation with Address

```json
{
  "category_id": 5,
  "rate_plan_id": 1419,
  "arrival": "2025-12-20",
  "departure": "2025-12-23",
  "adults": 2,
  "children": 2,
  "guest": {
    "firstName": "Jane",
    "lastName": "Smith",
    "email": "jane.smith@example.com",
    "phone": "+1987654321",
    "address": {
      "street": "456 Oak Avenue",
      "city": "Los Angeles",
      "state": "CA",
      "postcode": "90001",
      "country": "USA"
    }
  }
}
```

---

### Expected Response Format:

```json
{
  "confirmationNumber": "RMS-123456",
  "reservationId": 789,
  "status": "CONFIRMED",
  "arrival": "2025-11-15",
  "departure": "2025-11-16",
  "totalAmount": 140.00,
  "currency": "USD",
  "guest": {
    "firstName": "John",
    "lastName": "Doe",
    "email": "john.doe@example.com"
  }
}
```

---

## 3️⃣ Get Reservation Details

**Endpoint:** `GET /api/rms/reservations/{reservation_id}`

**Description:** Retrieve booking details.

### Test Case 1: Get Existing Reservation

**cURL:**
```bash
curl -X GET "http://localhost:8000/api/rms/reservations/789" \
  -H "Authorization: Bearer aIUTD3R0t1"
```

---

### Expected Response Format:

```json
{
  "reservationId": 789,
  "confirmationNumber": "RMS-123456",
  "status": "CONFIRMED",
  "arrival": "2025-11-15",
  "departure": "2025-11-16",
  "category": {
    "id": 4,
    "name": "Deluxe Room"
  },
  "ratePlan": {
    "id": 1417,
    "name": "OTA"
  },
  "guest": {
    "firstName": "John",
    "lastName": "Doe",
    "email": "john.doe@example.com",
    "phone": "+1234567890"
  },
  "totalAmount": 140.00,
  "currency": "USD"
}
```

---

## 4️⃣ Cancel Reservation

**Endpoint:** `DELETE /api/rms/reservations/{reservation_id}`

**Description:** Cancel an existing booking.

### Test Case 1: Cancel Reservation

**cURL:**
```bash
curl -X DELETE "http://localhost:8000/api/rms/reservations/789" \
  -H "Authorization: Bearer aIUTD3R0t1"
```

---

### Expected Response Format:

```json
{
  "success": true,
  "message": "Reservation 789 cancelled successfully",
  "reservationId": 789,
  "cancellationDate": "2025-11-10T10:30:00Z"
}
```

---

## 5️⃣ Get Cache Statistics

**Endpoint:** `GET /api/rms/cache/stats`

**Description:** View cached data statistics (for debugging).

### Test Case 1: Get Stats

**cURL:**
```bash
curl -X GET "http://localhost:8000/api/rms/cache/stats" \
  -H "Authorization: Bearer aIUTD3R0t1"
```

---

### Expected Response Format:

```json
{
  "property_id": 1,
  "agent_id": 1010,
  "categories_count": 10,
  "rate_ids_count": 25,
  "last_refresh": "2025-11-10T03:00:00Z",
  "needs_refresh": false
}
```

---

## 6️⃣ Manually Refresh Cache

**Endpoint:** `POST /api/rms/cache/refresh`

**Description:** Force cache refresh (normally runs at 3 AM daily).

### Test Case 1: Refresh Cache

**cURL:**
```bash
curl -X POST "http://localhost:8000/api/rms/cache/refresh" \
  -H "Authorization: Bearer aIUTD3R0t1"
```

---

### Expected Response Format:

```json
{
  "message": "Cache refreshed successfully"
}
```

---

## 🔒 Authentication Error Response

If you provide an invalid or missing token:

```json
{
  "detail": "Invalid authentication token"
}
```

**HTTP Status:** `401 Unauthorized`

---

## 📌 Testing Tips

1. **Use Postman or Thunder Client:**
   - Set Authorization type to "Bearer Token"
   - Use token: `aIUTD3R0t1`

2. **Test in Order:**
   - First: `/cache/stats` (verify cache is loaded)
   - Second: `/search` (check availability)
   - Third: `/reservations` (create booking)
   - Fourth: `/reservations/{id}` (verify booking)

3. **Date Format:**
   - Always use `YYYY-MM-DD` format
   - Ensure arrival < departure

4. **Error Handling:**
   - Invalid dates → `400 Bad Request`
   - No availability → Empty `available` array
   - Missing token → `401 Unauthorized`

---

## 🧪 Postman Collection

Import this JSON into Postman:

```json
{
  "info": {
    "name": "RMS API Tests",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "auth": {
    "type": "bearer",
    "bearer": [
      {
        "key": "token",
        "value": "aIUTD3R0t1",
        "type": "string"
      }
    ]
  },
  "item": [
    {
      "name": "Search Availability",
      "request": {
        "method": "POST",
        "header": [],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"arrival\": \"2025-11-15\",\n  \"departure\": \"2025-11-16\",\n  \"adults\": 2,\n  \"children\": 0\n}",
          "options": {
            "raw": {
              "language": "json"
            }
          }
        },
        "url": {
          "raw": "http://localhost:8000/api/rms/search",
          "protocol": "http",
          "host": ["localhost"],
          "port": "8000",
          "path": ["api", "rms", "search"]
        }
      }
    },
    {
      "name": "Create Reservation",
      "request": {
        "method": "POST",
        "header": [],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"category_id\": 4,\n  \"rate_plan_id\": 1417,\n  \"arrival\": \"2025-11-15\",\n  \"departure\": \"2025-11-16\",\n  \"adults\": 2,\n  \"children\": 0,\n  \"guest\": {\n    \"firstName\": \"John\",\n    \"lastName\": \"Doe\",\n    \"email\": \"john.doe@example.com\",\n    \"phone\": \"+1234567890\"\n  }\n}",
          "options": {
            "raw": {
              "language": "json"
            }
          }
        },
        "url": {
          "raw": "http://localhost:8000/api/rms/reservations",
          "protocol": "http",
          "host": ["localhost"],
          "port": "8000",
          "path": ["api", "rms", "reservations"]
        }
      }
    },
    {
      "name": "Get Cache Stats",
      "request": {
        "method": "GET",
        "header": [],
        "url": {
          "raw": "http://localhost:8000/api/rms/cache/stats",
          "protocol": "http",
          "host": ["localhost"],
          "port": "8000",
          "path": ["api", "rms", "cache", "stats"]
        }
      }
    }
  ]
}
```

---

## ✅ Success Criteria

- ✅ All requests include `Authorization: Bearer aIUTD3R0t1`
- ✅ Search returns available rooms sorted by price
- ✅ Create reservation returns confirmation number
- ✅ Get reservation shows booking details
- ✅ Cache stats shows loaded data
- ✅ Invalid token returns 401 error
