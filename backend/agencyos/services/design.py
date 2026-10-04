"""Colour/typography utilities used by the UI Designer and the reviewers (WCAG contrast)."""
from __future__ import annotations

COLOR_HEX = {
    "black": "#0b0b0c", "white": "#ffffff", "gold": "#c9a45c", "green": "#2f6b4f", "dark green": "#173b2f",
    "emerald": "#1f6f54", "navy": "#14213d", "blue": "#2457d6", "red": "#b3261e", "burgundy": "#6d1f2f",
    "purple": "#6b4bd8", "pink": "#d6457f", "orange": "#e46f2c", "yellow": "#e3b505", "teal": "#137a7f",
    "turquoise": "#1aa6a6", "grey": "#6b7280", "gray": "#6b7280", "beige": "#e9dfcf", "cream": "#f6f0e4",
    "brown": "#6b4a2f", "silver": "#b8bcc4", "charcoal": "#24272b", "sand": "#d8c3a5", "terracotta": "#c0623b",
    "olive": "#5f6b2f",
}

# Each palette colour carries a family so avoided colours can be filtered out.
PALETTES = {
    "luxury": {
        "background": ("#0f1513", "dark green"), "surface": ("#16201c", "dark green"),
        "primary": ("#c9a45c", "gold"), "accent": ("#1f6f54", "emerald"), "text": ("#f3eee4", "cream"),
        "muted": ("#b9b2a5", "beige"), "border": ("#2b3a34", "dark green"),
        "fonts": ("'Cormorant Garamond', Georgia, serif", "'Inter', system-ui, sans-serif"),
    },
    "modern": {
        "background": ("#ffffff", "white"), "surface": ("#f5f7fa", "grey"), "primary": ("#2457d6", "blue"),
        "accent": ("#137a7f", "teal"), "text": ("#111418", "black"), "muted": ("#5b6470", "grey"),
        "border": ("#e3e7ec", "grey"), "fonts": ("'Inter', system-ui, sans-serif", "'Inter', system-ui, sans-serif"),
    },
    "warm": {
        "background": ("#fbf7f0", "cream"), "surface": ("#f2e9db", "beige"), "primary": ("#b4532a", "terracotta"),
        "accent": ("#5f6b2f", "olive"), "text": ("#2a211b", "brown"), "muted": ("#6d5f52", "brown"),
        "border": ("#e5d8c5", "beige"), "fonts": ("'Fraunces', Georgia, serif", "'Inter', system-ui, sans-serif"),
    },
    "bold": {
        "background": ("#0d0b1a", "navy"), "surface": ("#17142b", "navy"), "primary": ("#7c5cff", "purple"),
        "accent": ("#ff7a3d", "orange"), "text": ("#f5f3ff", "white"), "muted": ("#b7b0d9", "purple"),
        "border": ("#2a2547", "navy"), "fonts": ("'Space Grotesk', system-ui, sans-serif", "'Inter', system-ui, sans-serif"),
    },
}

ALTERNATES = {  # family -> replacement used when a family is avoided
    "gold": ("#9fb8ad", "sage"), "emerald": ("#6d1f2f", "burgundy"), "dark green": ("#14181f", "charcoal"),
    "blue": ("#137a7f", "teal"), "purple": ("#2457d6", "blue"), "orange": ("#d6457f", "pink"),
    "terracotta": ("#6d1f2f", "burgundy"), "teal": ("#2f6b4f", "green"), "olive": ("#14213d", "navy"),
}


def style_key(style: str | None) -> str:
    s = (style or "").lower()
    if "lux" in s or "elegan" in s:
        return "luxury"
    if "warm" in s or "welcom" in s:
        return "warm"
    if "bold" in s or "vibrant" in s:
        return "bold"
    return "modern"


def _lum(hex_: str) -> float:
    h = hex_.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted([_lum(a), _lum(b)], reverse=True)
    return round((la + 0.05) / (lb + 0.05), 2)


def best_on(bg: str) -> str:
    return "#0b0b0c" if contrast(bg, "#0b0b0c") >= contrast(bg, "#ffffff") else "#ffffff"


def color_hex(name: str) -> str | None:
    if name.startswith("#") and len(name) == 7:
        return name
    return COLOR_HEX.get(name.lower())


def build_palette(style: str | None, colors: list[str], avoid: list[str]) -> tuple[dict, dict, list[str]]:
    """Return (colors, fonts, decisions)."""
    key = style_key(style)
    base = PALETTES[key]
    decisions = [f"Base palette '{key}' chosen from style preference '{style or 'unspecified'}'."]
    out: dict[str, str] = {}
    avoid_l = {a.lower() for a in avoid}
    for role, val in base.items():
        if role == "fonts":
            continue
        hx, fam = val
        if fam in avoid_l or any(a in fam for a in avoid_l):
            alt = ALTERNATES.get(fam)
            if alt:
                decisions.append(f"Replaced {fam} for '{role}' with {alt[1]} because the client asked to avoid {fam}.")
                hx = alt[0]
        out[role] = hx
    wanted = [c for c in (color_hex(c) for c in colors) if c]
    if wanted:
        out["primary"] = wanted[0]
        decisions.append(f"Primary colour set to client choice {colors[0]}.")
        if len(wanted) > 1:
            out["accent"] = wanted[1]
            decisions.append(f"Accent colour set to client choice {colors[1]}.")
    # A primary that disappears into the background is useless for CTAs: swap with accent if that reads better.
    if contrast(out["primary"], out["background"]) < 3 and contrast(out["accent"], out["background"]) > contrast(out["primary"], out["background"]):
        out["primary"], out["accent"] = out["accent"], out["primary"]
        decisions.append("Swapped primary/accent so call-to-action buttons stand out against the background.")
    # Guarantee readable text and button labels.
    if contrast(out["text"], out["background"]) < 7:
        out["text"] = best_on(out["background"])
        decisions.append("Text colour adjusted for AAA body contrast.")
    out["on_primary"] = best_on(out["primary"])
    # Emphasis colour for eyebrows/links: first brand colour that meets 4.5:1 on the background.
    out["emphasis"] = next((c for c in (out["primary"], out["accent"]) if contrast(c, out["background"]) >= 4.5), out["text"])
    if contrast(out["muted"], out["background"]) < 4.5:
        out["muted"] = out["text"]
        decisions.append("Muted text promoted to body colour to keep 4.5:1 contrast.")
    return out, {"heading": base["fonts"][0], "body": base["fonts"][1]}, decisions
