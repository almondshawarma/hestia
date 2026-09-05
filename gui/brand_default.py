"""brand_default.py — committed, brand-neutral fallback skin for the GUI.

hestia_gui.py loads this whenever there's no local brand.py, so a fresh clone renders in a
clean generic dark look with zero setup. Same contract as visualization/scenes/brand_default.py:
fill the PALETTE roles (not literal names) + FONTS. Copy this to brand.py (gitignored) and edit
to your own tokens.
"""

# Colour ROLES, so any skin fills the same slots.
PALETTE = {
    "bg":     "#0E0E12",   # window background
    "accent": "#4C86C6",   # primary accent (header, emphasis)   — generic blue
    "ink":    "#EAEAEA",   # primary text
    "ground": "#444A54",   # structural
    "flow":   "#6FA3CC",   # anything live / flowing (the update dot)
    "warm":   "#C6884C",   # secondary warm
    "muted":  "#7A7A85",   # de-emphasized but readable (labels)
}

# "" → let Tk pick a default; a name is used only if that family is installed.
FONTS = {
    "mono":    "Consolas",   # values, PV names, labels
    "display": "",           # header title (falls back to mono)
    "body":    "",
}
