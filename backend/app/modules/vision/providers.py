"""Vision provider abstraction (mock-first).

``VisionProvider.analyze_crop_image()`` returns a normalized ``VisionResult``.
The mock is deterministic and speaks UNCERTAIN language only — possible
conditions are "-like symptoms (uncertain)" and every observation carries
"(uncertain)". Forbidden everywhere: dosages, mixing, combinations,
prescriptions, fertilizer rates, spray schedules, definitive diagnosis,
autonomous actions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.core.config import get_settings


class ProviderError(Exception):
    """Provider failure — carries no secrets or payloads."""


@dataclass
class VisionResult:
    """Normalized analysis result (uncertainty is structural, not cosmetic)."""

    possible_condition: str | None = None
    confidence: float | None = None
    observations: list[str] = field(default_factory=list)
    quality: str | None = None  # good | usable | poor
    needs_info: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    is_mock: bool = True


class VisionProvider(ABC):
    """Image-analysis seam."""

    @abstractmethod
    def analyze_crop_image(
        self,
        images: list[bytes],
        language: str,
        crop_name: str | None = None,
    ) -> VisionResult:
        """Observe photos; return UNCERTAIN findings only."""
        raise NotImplementedError


class MockVisionProvider(VisionProvider):
    """Deterministic dev/test vision (labelled, free, never a diagnosis)."""

    def analyze_crop_image(
        self,
        images: list[bytes],
        language: str,
        crop_name: str | None = None,
    ) -> VisionResult:
        _ = (images, language, crop_name)  # mock ignores pixels by design
        return VisionResult(
            possible_condition="Leaf spot-like symptoms (uncertain — not a diagnosis)",
            confidence=0.35,
            observations=[
                "leaf spots observed (uncertain)",
                "yellowing observed (uncertain)",
                "wilting observed (uncertain)",
            ],
            quality="usable",
            needs_info=[
                "close-up photo of affected leaf (uncertain — more detail may help observation)",
            ],
            next_steps=[
                "monitor the crop and compare with new photos (uncertain)",
                "consult your local agriculture expert for field verification (uncertain)",
            ],
            is_mock=True,
        )


class DisabledVisionProvider(VisionProvider):
    """Fail-closed vision (marks rows failed, never fabricates)."""

    def analyze_crop_image(
        self,
        images: list[bytes],
        language: str,
        crop_name: str | None = None,
    ) -> VisionResult:
        raise ProviderError("Vision provider is disabled.")


def get_vision_provider(name: str | None = None) -> VisionProvider:
    """Factory seam (mock by default; ``disabled`` fails closed)."""
    provider = (name or get_settings().vision_provider).lower()
    if provider == "mock":
        return MockVisionProvider()
    if provider == "disabled":
        return DisabledVisionProvider()
    raise ProviderError(f"Unknown vision provider: {provider}")


DISCLAIMER = {
    "mr": "ही तपासणी निदान नाही — केवळ अनिश्चित निरीक्षणे. अचूक माहितीसाठी स्थानिक कृषी तज्ज्ञांचा सल्ला घ्या.",
    "hi": "यह जाँच निदान नहीं है — केवल अनिश्चित अवलोकन। सटीक जानकारी के लिए स्थानीय कृषि विशेषज्ञ से सलाह लें।",
    "en": "This check is not a diagnosis — uncertain observations only. Consult your local agriculture expert for confirmation.",
}


def disclaimer_for(language: str) -> str:
    """Not-a-diagnosis disclaimer (every response carries it)."""
    return DISCLAIMER.get(language, DISCLAIMER["mr"])
