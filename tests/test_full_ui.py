import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "web" / "index.html"
TOKENS_CSS = ROOT / "web" / "tokens.css"
CSS = ROOT / "web" / "styles.css"
MOTION_CSS = ROOT / "web" / "motion.css"
JS = ROOT / "web" / "app.js"


class FullUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = HTML.read_text(encoding="utf-8")
        cls.css = "".join(
            path.read_text(encoding="utf-8") for path in (TOKENS_CSS, CSS, MOTION_CSS)
        )
        cls.js = JS.read_text(encoding="utf-8")

    def test_semantic_surface_contains_every_live_record_area(self) -> None:
        for marker in (
            'class="skip-link"',
            '<header class="site-header">',
            'id="lab-apparatus"',
            'id="voice-presence"',
            'id="live-record"',
            'id="measurements-heading"',
            'id="deviations-heading"',
            'id="messages-heading"',
            'id="inventory-heading"',
            'id="timeline-heading"',
            '<footer class="site-footer">',
        ):
            self.assertIn(marker, self.html)

    def test_page_uses_only_local_assets_and_original_inline_svg(self) -> None:
        self.assertNotRegex(self.html, r'https?://')
        self.assertIn('<svg viewBox="0 0 760 580"', self.html)
        self.assertIn('<title id="apparatus-title">', self.html)
        self.assertIn('<desc id="apparatus-desc">', self.html)
        self.assertNotIn("World Labs", self.html)
        self.assertNotRegex(self.html, r'<(?:img|script|link)[^>]+https?://')

    def test_renderer_keeps_dynamic_content_out_of_inner_html(self) -> None:
        self.assertNotIn("innerHTML", self.js)
        self.assertIn("textContent", self.js)
        self.assertIn('fetchJson("/api/runs")', self.js)
        self.assertIn('fetchJson("/api/inventory")', self.js)
        self.assertIn("encodeURIComponent(selectedRunId)", self.js)
        self.assertNotRegex(self.js, r'fetch\([^)]*(?:POST|PUT|PATCH|DELETE)')

    def test_safety_and_purchase_language_remain_explicit(self) -> None:
        self.assertIn("outside the approved protocol range", self.js)
        self.assertIn("Automated protocol check", self.js)
        self.assertIn("Pending request — human approval required", self.js)
        for prohibited in ("order placed", "purchase complete", "safe to continue"):
            self.assertNotIn(prohibited, (self.html + self.js).lower())

    def test_motion_is_state_driven_and_reduced_motion_is_complete(self) -> None:
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css)
        self.assertIn("animation-duration: 0.01ms !important", self.css)
        self.assertIn("transition-duration: 0.01ms !important", self.css)
        self.assertIn('[data-state="running"]', self.css)
        self.assertIn('[data-voice-state="processing"]', self.css)
        keyframe_bodies = re.findall(r"@keyframes\s+[^{]+\{(.*?)\n\}", self.css, re.DOTALL)
        for body in keyframe_bodies:
            declarations = set(re.findall(r"\b([a-z-]+)\s*:", body))
            self.assertTrue(declarations <= {"transform", "opacity"}, declarations)

    def test_responsive_focus_and_control_requirements_exist(self) -> None:
        for query in (
            "@media (max-width: 1180px)",
            "@media (max-width: 900px)",
            "@media (max-width: 680px)",
            "@media (max-width: 420px)",
            ":focus-visible",
            "min-height: 48px",
            "overflow-x: hidden",
        ):
            self.assertIn(query, self.css)

    def test_banned_visual_patterns_are_absent(self) -> None:
        combined = self.html + self.css
        for pattern in (
            "background-clip: text",
            "backdrop-filter",
            "repeating-linear-gradient",
            "feTurbulence",
            "cursor: none",
            "border-radius: 32px",
            "border-radius: 40px",
        ):
            self.assertNotIn(pattern, combined)


if __name__ == "__main__":
    unittest.main()
