"""Human-readable image delivery settings derived from frame storage."""

from __future__ import annotations

from pydantic import BaseModel


class ImageDeliveryOut(BaseModel):
    storage: str
    format: str
    compression: str


def image_delivery_for_frame(has_sd_card: bool | None) -> ImageDeliveryOut:
    if has_sd_card is None:
        return ImageDeliveryOut(
            storage="Unknown",
            format="PNG",
            compression="Server-side six-color Stucki dithering; frame-side dithering disabled.",
        )
    if has_sd_card:
        return ImageDeliveryOut(
            storage="microSD card",
            format="PNG",
            compression="Server-side six-color Stucki dithering; frame-side dithering disabled.",
        )
    return ImageDeliveryOut(
        storage="Internal flash only",
        format="PNG",
        compression="Server-side six-color Stucki dithering; frame-side dithering disabled.",
    )
