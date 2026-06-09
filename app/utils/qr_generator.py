"""
qr_generator.py – Generate QR code images for machine URLs
"""
import qrcode
from PIL import Image
from pathlib import Path
from app.utils.logger import logger


def generate_machine_qr(machine_id: str, frontend_url: str, output_dir: str = "qr_codes") -> str:
    """
    Generate a QR code PNG for a specific machine.
    The QR encodes: {frontend_url}?machine={machine_id}
    Returns the file path of the generated image.
    """
    url = f"{frontend_url}?machine={machine_id}"
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img: Image.Image = qr.make_image(fill_color="black", back_color="white")
    file_path = f"{output_dir}/machine_{machine_id}.png"
    img.save(file_path)

    logger.info(f"QR code saved → {file_path}  (URL: {url})")
    return file_path
