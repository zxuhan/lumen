from app.layers import LayerDocument, LayerKind, LayerMissing, resolve_layer
from app.ratios import Ratio, parts_of

MIN_CROP = 32


class EditError(Exception):
    """Params are valid but can't apply to the current canvas, e.g. the crop area is too small."""


def flip(document: LayerDocument, layer_id: str | None, direction: str) -> LayerDocument:
    """Flip in place. x/y is the top-left of the unscaled box; negative scale keeps the center."""
    doc = document.model_copy(deep=True)
    layer = resolve_layer(doc, layer_id)
    if direction == "horizontal":
        layer.transform.scale_x *= -1
    else:
        layer.transform.scale_y *= -1
    return doc


def set_opacity(document: LayerDocument, layer_id: str | None, opacity: float) -> LayerDocument:
    doc = document.model_copy(deep=True)
    resolve_layer(doc, layer_id).opacity = opacity
    return doc


def set_visible(document: LayerDocument, layer_id: str | None, visible: bool) -> LayerDocument:
    doc = document.model_copy(deep=True)
    resolve_layer(doc, layer_id).visible = visible
    return doc


def set_text(
    document: LayerDocument,
    layer_id: str | None,
    text: str,
    *,
    font_size: float | None = None,
    fill: str | None = None,
) -> LayerDocument:
    """Change a text layer's copy, optionally its font size and color. Without a layer id, uses
    the topmost visible text layer."""
    doc = document.model_copy(deep=True)
    layer = _resolve_text(doc, layer_id)
    layer.text = text
    layer.name = text[:12] or layer.name
    if font_size is not None:
        layer.font_size = font_size
    if fill is not None:
        layer.fill = fill
    return doc


def _resolve_text(document: LayerDocument, layer_id: str | None):
    if layer_id:
        layer = resolve_layer(document, layer_id)
        if layer.kind is not LayerKind.TEXT:
            raise EditError("Copy can only be changed on text layers")
        return layer
    for layer in reversed(document.layers):
        if layer.kind is LayerKind.TEXT and layer.visible:
            return layer
    raise LayerMissing("No editable text layer")


def scale(
    document: LayerDocument,
    layer_id: str | None,
    *,
    factor: float | None = None,
    scale_x: float | None = None,
    scale_y: float | None = None,
    x: float | None = None,
    y: float | None = None,
) -> LayerDocument:
    """factor is a relative multiplier; scale_x / scale_y are absolute and keep any existing flip.

    Corner-drag scaling also moves the center, so x/y are written together with the scale and a
    single history entry undoes the whole change.
    """
    doc = document.model_copy(deep=True)
    transform = resolve_layer(doc, layer_id).transform
    if x is not None:
        transform.x = x
    if y is not None:
        transform.y = y
    if factor is not None:
        transform.scale_x *= factor
        transform.scale_y *= factor
        return doc
    if scale_x is not None:
        transform.scale_x = _with_sign(transform.scale_x, scale_x)
    if scale_y is not None:
        transform.scale_y = _with_sign(transform.scale_y, scale_y)
    return doc


def rotate(
    document: LayerDocument,
    layer_id: str | None,
    *,
    angle: float | None = None,
    rotation: float | None = None,
) -> LayerDocument:
    doc = document.model_copy(deep=True)
    transform = resolve_layer(doc, layer_id).transform
    transform.rotation = transform.rotation + angle if angle is not None else rotation or 0
    return doc


def move(
    document: LayerDocument,
    layer_id: str | None,
    *,
    x: float | None = None,
    y: float | None = None,
    dx: float | None = None,
    dy: float | None = None,
) -> LayerDocument:
    """Move a layer's top-left corner. x/y are absolute coordinates; dx/dy are relative offsets."""
    doc = document.model_copy(deep=True)
    transform = resolve_layer(doc, layer_id).transform
    transform.x = x if x is not None else transform.x + (dx or 0)
    transform.y = y if y is not None else transform.y + (dy or 0)
    return doc


def reorder(document: LayerDocument, layer_id: str | None, place: str) -> LayerDocument:
    """The end of the layer list is drawn last, i.e. it is visually frontmost."""
    doc = document.model_copy(deep=True)
    target = resolve_layer(doc, layer_id)
    layers = list(doc.layers)
    index = next(i for i, layer in enumerate(layers) if layer.id == target.id)
    if place == "top":
        layers.append(layers.pop(index))
    elif place == "bottom":
        layers.insert(0, layers.pop(index))
    elif place == "up" and index < len(layers) - 1:
        layers[index], layers[index + 1] = layers[index + 1], layers[index]
    elif place == "down" and index > 0:
        layers[index], layers[index - 1] = layers[index - 1], layers[index]
    doc.layers = layers
    return doc


def crop(
    document: LayerDocument,
    *,
    ratio: Ratio | None = None,
    rect: tuple[float, float, float, float] | None = None,
) -> LayerDocument:
    """Crop the canvas. Layers are only shifted; pixels are clipped to the canvas when rendering."""
    if ratio is not None:
        left, right = parts_of(ratio)
        x, y, width, height = _fit_ratio(document.width, document.height, left, right)
    elif rect is not None:
        nx, ny, nw, nh = rect
        x, y = nx * document.width, ny * document.height
        width, height = nw * document.width, nh * document.height
    else:
        raise EditError("A ratio or crop box is required")

    x, y, width, height = _as_pixels(x, y, width, height, document.width, document.height)
    if width < MIN_CROP or height < MIN_CROP:
        raise EditError(f"Crop area too small; the shortest side must be at least {MIN_CROP} px")

    doc = document.model_copy(deep=True)
    for layer in doc.layers:
        layer.transform.x -= x
        layer.transform.y -= y
    doc.width = width
    doc.height = height
    return doc


def _with_sign(current: float, magnitude: float) -> float:
    sign = 1 if current >= 0 else -1
    return abs(magnitude) * sign


def _fit_ratio(canvas_w: int, canvas_h: int, rw: int, rh: int) -> tuple[float, float, float, float]:
    if canvas_w * rh >= canvas_h * rw:
        height = float(canvas_h)
        width = height * rw / rh
    else:
        width = float(canvas_w)
        height = width * rh / rw
    return (canvas_w - width) / 2, (canvas_h - height) / 2, width, height


def _as_pixels(
    x: float, y: float, width: float, height: float, canvas_w: int, canvas_h: int
) -> tuple[int, int, int, int]:
    left = max(0, int(round(x)))
    top = max(0, int(round(y)))
    right = min(canvas_w, int(round(x + width)))
    bottom = min(canvas_h, int(round(y + height)))
    return left, top, max(0, right - left), max(0, bottom - top)


__all__ = [
    "EditError",
    "crop",
    "flip",
    "move",
    "reorder",
    "rotate",
    "scale",
    "set_opacity",
    "set_text",
    "set_visible",
]
