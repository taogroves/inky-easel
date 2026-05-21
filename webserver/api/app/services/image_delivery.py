"""Human-readable image delivery settings derived from frame storage."""

from __future__ import annotations

from pydantic import BaseModel


class ImageDeliveryOut(BaseModel):
    storage: str
    format: str
    compression: str
    posterize_note: str | None = None


def image_delivery_for_frame(has_sd_card: bool | None) -> ImageDeliveryOut:
    if has_sd_card is None:
        return ImageDeliveryOut(
            storage="Unknown",
            format="—",
            compression="Will be reported on the frame's next check-in.",
            posterize_note=None,
        )
    if has_sd_card:
        return ImageDeliveryOut(
            storage="microSD card",
            format="PNG",
            compression="Lossless PNG (no JPEG artifacts)",
            posterize_note=(
                "Inbox drawings can use posterize (sharp pixels) when enabled on the inbox schedule item; "
                "other image slides use dithered PNG."
            ),
        )
    return ImageDeliveryOut(
        storage="Internal flash only",
        format="JPEG",
        compression="Lossy JPEG — quality 85 (weather 80), 4:2:0 chroma subsampling",
        posterize_note=None,
    )
