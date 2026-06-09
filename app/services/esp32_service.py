"""
esp32_service.py – Communicate with ESP32 microcontrollers on vending machines.

The ESP32 exposes a small HTTP server. We POST a dispense command and wait
for an acknowledgement. If the machine is offline the command is queued in
MongoDB and executed when the machine next polls or reconnects.
"""
import asyncio
from datetime import datetime
from typing import Any

import httpx
from app.config import settings
from app.database import get_collection
from app.utils.logger import logger


# ── Low-level HTTP call ───────────────────────────────────────────────────────

async def _post_to_esp32(endpoint: str, payload: dict) -> dict:
    """Send a JSON POST request to the ESP32 and return the JSON response."""
    async with httpx.AsyncClient(timeout=settings.ESP32_TIMEOUT_SECONDS) as client:
        resp = await client.post(endpoint, json=payload)
        resp.raise_for_status()
        return resp.json()


# ── Dispense ─────────────────────────────────────────────────────────────────

async def send_dispense_command(
    machine_doc: dict,
    order_id: str,
    items: list[dict[str, Any]],
) -> dict:
    """
    Send a dispense command to the ESP32.

    items: [{"product_id": "...", "quantity": 1}, ...]

    Returns {"success": True/False, "message": "..."}.
    If the machine is unreachable the command is queued.
    """
    endpoint = _resolve_esp32_endpoint(machine_doc)

    payload = {
        "command": "dispense",
        "order_id": order_id,
        "items": items,
        "timestamp": datetime.utcnow().isoformat(),
    }

    for attempt in range(1, settings.ESP32_RETRY_ATTEMPTS + 1):
        try:
            logger.info(f"[ESP32] Dispense attempt {attempt}/{settings.ESP32_RETRY_ATTEMPTS} → {endpoint}")
            result = await _post_to_esp32(endpoint, payload)
            logger.info(f"[ESP32] Response: {result}")
            return {"success": True, "message": result.get("message", "OK"), "raw": result}

        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            logger.warning(f"[ESP32] Attempt {attempt} failed: {exc}")
            if attempt < settings.ESP32_RETRY_ATTEMPTS:
                await asyncio.sleep(2 ** attempt)  # exponential back-off

    # All attempts failed – queue the command
    await _queue_dispense_command(machine_doc["_id"], order_id, items, payload)
    return {"success": False, "message": "Machine unreachable. Command queued."}


def _resolve_esp32_endpoint(machine_doc: dict) -> str:
    """Return the full dispense URL for the machine."""
    if machine_doc.get("esp32_endpoint"):
        return machine_doc["esp32_endpoint"]
    ip = machine_doc.get("esp32_ip", "")
    if not ip:
        raise ValueError(f"No ESP32 address configured for machine {machine_doc.get('machine_code')}")
    return f"http://{ip}/dispense"


async def _queue_dispense_command(
    machine_id: Any,
    order_id: str,
    items: list,
    payload: dict,
) -> None:
    """Persist a failed dispense command for later retry."""
    col = get_collection("pending_commands")
    await col.insert_one({
        "machine_id": str(machine_id),
        "order_id": order_id,
        "items": items,
        "payload": payload,
        "status": "queued",
        "created_at": datetime.utcnow(),
        "last_attempt_at": datetime.utcnow(),
    })
    logger.warning(f"[ESP32] Command queued for machine {machine_id}, order {order_id}")


# ── Machine status poll ───────────────────────────────────────────────────────

async def poll_machine_status(machine_doc: dict) -> bool:
    """Ping the ESP32 and return True if it is reachable."""
    try:
        ip = machine_doc.get("esp32_ip", "")
        endpoint = machine_doc.get("esp32_endpoint") or (f"http://{ip}/status" if ip else None)
        if not endpoint:
            return False
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(endpoint)
            return resp.status_code == 200
    except Exception:
        return False


# ── Pending command processor ─────────────────────────────────────────────────

async def process_pending_commands(machine_doc: dict) -> None:
    """
    Called when a machine comes back online.
    Attempt to flush queued commands for that machine.
    """
    col = get_collection("pending_commands")
    machine_id = str(machine_doc["_id"])
    cursor = col.find({"machine_id": machine_id, "status": "queued"})

    async for cmd in cursor:
        result = await send_dispense_command(machine_doc, cmd["order_id"], cmd["items"])
        new_status = "completed" if result["success"] else "queued"
        await col.update_one(
            {"_id": cmd["_id"]},
            {"$set": {"status": new_status, "last_attempt_at": datetime.utcnow()}},
        )
