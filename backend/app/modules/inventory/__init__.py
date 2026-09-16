"""Per-variant stock levels + immutable movement audit (Step 16).

Stock truth note: ``inventory`` is the actual availability source.
``ProductVariant.stock_qty`` (catalogue) is left untouched as a legacy
display field — Step 16 never reads or writes it.
"""
