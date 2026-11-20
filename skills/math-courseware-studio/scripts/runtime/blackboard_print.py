"""Plan physical stickers once and impose those same pieces on two paper sizes."""
import hashlib
import math
import statistics
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageChops, ImageFont


PAPER = {'A4': (210, 297), 'A3': (420, 297)}
TARGET_MM = {'title': 55, 'stage': 49, 'prompt': 50, 'method': 48,
             'conclusion': 47, 'formula': 41, 'diagram_label': 29}
PRINT_ROLES = set(TARGET_MM) | {'diagram', 'support'}
GRAPHICS = {'image', 'dots', 'arrow', 'brace', 'blank'}
OVERLAP = 10
LEFT, TOP, FOOT = 14, 17, 24  # leave room outside the art for registration and a ruler
POINTS_PER_MM = 72 / 25.4


def _role(asset):
    if 'print_role' in asset:
        role = asset['print_role']
    elif asset['kind'] in GRAPHICS:
        role = 'diagram' if asset['kind'] in {'image', 'dots'} else 'support'
    elif asset['kind'] == 'card':
        role = 'formula'
    else:
        role = {'title': 'title', 'display': 'stage', 'reading': 'prompt'}.get(asset.get('role'), 'method')
    if role not in PRINT_ROLES:
        raise ValueError(f"Unknown print_role for {asset['id']}: {role}")
    return role


def _visible(image):
    box = image.getchannel('A').getbbox()
    if not box:
        raise ValueError('An empty sticker cannot be printed')
    return image.crop(box)


def _ink_height(image):
    r, g, b, a = image.split()
    dark = ImageChops.lighter(ImageChops.lighter(r, g), b).point(lambda n: 255 if n < 100 else 0)
    box = ImageChops.multiply(dark, a.point(lambda n: 255 if n > 200 else 0)).getbbox()
    return box[3] - box[1] if box else 0


def _text_scale(asset, image, fonts, factor=1):
    role = _role(asset)
    if role not in TARGET_MM:
        raise ValueError(f"Text sticker {asset['id']} needs a text print_role")
    if role == 'formula':
        # Match the same nominal digit across equations, standalone operators and stacked fractions.
        is_card = asset['kind'] == 'card'
        font_role = 'math' if is_card else asset['role']
        size = asset.get('params', {}).get('size', 190 if is_card else 210 if asset['kind'] == 'pill' else 240)
        face = ImageFont.truetype(fonts[font_role]['path'], round(size * factor * (285 / 235 if is_card else 1)))
        bounds = face.getbbox('0')
        letter = bounds[3] - bounds[1]
    else:
        letter = _ink_height(image)
    if not letter:
        raise ValueError('No measurable letter height: ' + asset['id'])
    return TARGET_MM[role] / letter


def _board_scales(data, anchors, drawn_widths):
    """The same board coordinate scale preserves the relationships between related graphics."""
    candidates = {}
    graphics = {a['id']: a for a in data['assets'] if a['kind'] in GRAPHICS}
    for board in data['layout']['boards']:
        items = board['items']
        explicit = [anchors[i['id']] / i['w'] for i in items if 'print_width_mm' in graphics.get(i['id'], {})]
        references = [anchors[i['id']] / i['w'] for i in items if i['id'] in anchors]
        widths = {i['id']: i['w'] * drawn_widths[i['id']] for i in items if i['id'] in graphics}
        diagrams = [w for key, w in widths.items() if _role(graphics[key]) != 'support']
        if explicit or references:
            scale = statistics.median(explicit or references)
        else:
            scale = 160 / max(diagrams) if diagrams else 55 / max(widths.values())
        for item in items:
            candidates.setdefault(item['id'], []).append(item['w'] * scale)
    return {key: statistics.median(widths) for key, widths in candidates.items()}


def _copies(data):
    counts = Counter()
    for board in data['layout']['boards']:
        counts |= Counter(i['id'] for i in board['items'])
    return counts


def _prepare(data, assets_dir, spool, render_native):
    full_text_widths, drawn_widths = {}, {}
    for asset in data['assets']:
        with Image.open(assets_dir / asset['file']) as source:
            visible = _visible(source.convert('RGBA'))
            if asset['kind'] not in GRAPHICS:
                full_text_widths[asset['id']] = source.width * _text_scale(asset, visible, data['fonts'])
            elif 'print_width_mm' in asset:
                target = asset['print_width_mm']
                if isinstance(target, bool) or not isinstance(target, (int, float)) or not math.isfinite(target) or target <= 0:
                    raise ValueError('Expected positive finite print_width_mm: ' + asset['id'])
                full_text_widths[asset['id']] = target * source.width / visible.width
            if asset['kind'] in GRAPHICS:
                drawn_widths[asset['id']] = visible.width / source.width
            if 'print_width_mm' in asset and asset['kind'] not in GRAPHICS:
                raise ValueError('print_width_mm applies to graphics: ' + asset['id'])
    board_widths = _board_scales(data, full_text_widths, drawn_widths)
    copies = _copies(data)
    pieces = []
    for index, asset in enumerate(data['assets']):
        key, kind, role = asset['id'], asset['kind'], _role(asset)
        with Image.open(assets_dir / asset['file']) as source:
            picture = _visible(source.convert('RGBA'))
            if kind in GRAPHICS:
                board_width = board_widths.get(key)
                fallback = 160 if role == 'diagram' else 55
                width = asset.get('print_width_mm', board_width * picture.width / source.width if board_width else fallback)
                scale = width / picture.width
            else:
                scale = _text_scale(asset, picture, data['fonts'])
        if 25.4 / scale < 300 and kind != 'image':
            if render_native is None:
                raise ValueError('High-resolution native redraw required for ' + key)
            factor = math.ceil(300 * scale / 25.4 * 1.02)
            picture = _visible(render_native(asset, factor).convert('RGBA'))
            scale = width / picture.width if kind in GRAPHICS else _text_scale(asset, picture, data['fonts'], factor)
            if 25.4 / scale < 299.5:
                raise ValueError('Native artwork below 300 DPI after redraw: ' + key)
        rgb = Image.new('RGB', picture.size, 'white')
        rgb.paste(picture, mask=picture.getchannel('A'))
        rgb.save(spool / f'{index}.png')
        pieces.append({'id': key, 'copies': max(1, copies[key]), 'print_role': role, 'width_mm': round(picture.width * scale, 5),
                       'height_mm': round(picture.height * scale, 5), 'effective_dpi': round(25.4 / scale, 2),
                       'ink_height_mm': round(_ink_height(picture) * scale, 2) if kind not in GRAPHICS else None,
                       'pixels': list(picture.size), 'pixels_sha256': hashlib.sha256(rgb.tobytes()).hexdigest(),
                       'tiles': {paper: [] for paper in PAPER}})
    return pieces


def _segments(length, capacity):
    count = 1 + math.ceil(max(0, length - capacity) / (capacity - OVERLAP))
    return [(i * (capacity - OVERLAP), min(capacity, length - i * (capacity - OVERLAP))) for i in range(count)]


def _pages(pieces, paper):
    width, height = PAPER[paper]
    right, bottom = width - LEFT, height - FOOT
    pages, current = [], []
    x, y, row_height = LEFT, TOP, 0
    copies = ((index, piece, number) for index, piece in enumerate(pieces)
              for number in range(1, piece['copies'] + 1))
    for index, piece, copy in copies:
        w, h = piece['width_mm'], piece['height_mm']
        room_w, room_h = right - LEFT, bottom - TOP
        cols, rows = _segments(w, room_w), _segments(h, room_h)
        turned_cols, turned_rows = _segments(h, room_w), _segments(w, room_h)
        rotate = len(turned_cols) * len(turned_rows) < len(cols) * len(rows)
        if rotate:
            w, h = h, w
            cols, rows = turned_cols, turned_rows
        separate = len(cols) > 1 or len(rows) > 1
        if separate:
            if current:
                pages.append(current)
                current = []
            x, y, row_height = LEFT, TOP, 0
        elif x + w > right:
            x, y, row_height = LEFT, y + row_height + 4, 0
        if not separate and y + h > bottom:
            pages.append(current)
            current = []
            x, y, row_height = LEFT, TOP, 0
        for r, (sy, th) in enumerate(rows, 1):
            for c, (sx, tw) in enumerate(cols, 1):
                # Display axes are (source y, original width - source x) after turning 90°.
                source = [piece['width_mm'] - sy - th, sx, th, tw] if rotate else [sx, sy, tw, th]
                tile = {'page': len(pages) + 1, 'copy': copy, 'row': r, 'column': c, 'rows': len(rows), 'columns': len(cols),
                        'rotation': 90 if rotate else 0, 'x_mm': round(x, 5), 'y_mm': round(y, 5), 'source_mm': source}
                if separate:
                    pages.append([(index, tile)])
                else:
                    current.append((index, tile))
        if not separate:
            x += w + 4
            row_height = max(row_height, h)
    if current:
        pages.append(current)
    return pages


def _rectangles(piece, tile, page_height):
    x, y = tile['x_mm'], tile['y_mm']
    sx, sy, tw, th = tile['source_mm']
    if tile['rotation']:
        bounds = (x - sy + piece['height_mm'], page_height - y - sx - tw, piece['width_mm'], piece['height_mm'])
        return bounds, (x, page_height - y - tw, th, tw)
    image_bounds = (x - sx, page_height - y + sy - piece['height_mm'], piece['width_mm'], piece['height_mm'])
    clip = (x, page_height - y - th, tw, th)
    return image_bounds, clip


def _registration(canvas, tile, clip):
    x, y, w, h = clip
    # Marks on adjoining sheets map to the same coordinate halfway inside the shared 10 mm.
    mx, my = [], []
    if tile['column'] > 1:
        mx.append(x + OVERLAP / 2)
    if tile['column'] < tile['columns']:
        mx.append(x + w - OVERLAP / 2)
    if tile['row'] > 1:
        my.append(y + h - OVERLAP / 2)
    if tile['row'] < tile['rows']:
        my.append(y + OVERLAP / 2)
    for a in mx:
        for b, end in ((y - 3, y), (y + h, y + h + 3)):
            canvas.line(a, b, a, end)
    for b in my:
        for a, end in ((x - 3, x), (x + w, x + w + 3)):
            canvas.line(a, b, end, b)


def _write_pdf(path, paper, pages, pieces, spool):
    from reportlab.pdfgen.canvas import Canvas
    mm = POINTS_PER_MM
    width, height = PAPER[paper]
    canvas = Canvas(str(path), pagesize=(width * mm, height * mm), pageCompression=1)
    canvas.setTitle(path.stem)
    for page_number, placements in enumerate(pages, 1):
        canvas.setFont('Helvetica', 8)
        for index, tile in placements:
            piece = pieces[index]
            bounds, clip = _rectangles(piece, tile, height)
            canvas.saveState()
            crop = canvas.beginPath()
            crop.rect(*(v * mm for v in clip))
            canvas.clipPath(crop, stroke=0)
            bx, by, bw, bh = (v * mm for v in bounds)
            canvas.translate(bx, by)
            if tile['rotation']:
                canvas.rotate(tile['rotation'])
            canvas.drawImage(str(spool / f'{index}.png'), 0, 0, bw, bh)
            canvas.restoreState()
            x, y, w, h = clip
            canvas.saveState()
            canvas.scale(mm, mm)
            canvas.setLineWidth(0.2)
            _registration(canvas, tile, clip)
            canvas.restoreState()
            if tile['columns'] + tile['rows'] > 2:
                label = f"#{index+1:02d}-{tile['copy']}   R{tile['row']}/{tile['rows']}   C{tile['column']}/{tile['columns']}   |   10 mm overlap"
                canvas.drawString(x * mm, (y + h + 3.5) * mm, label)
        canvas.setLineWidth(0.6)
        canvas.line(LEFT * mm, 13 * mm, (LEFT + 100) * mm, 13 * mm)
        for end in (LEFT, LEFT + 100):
            canvas.line(end * mm, 12 * mm, end * mm, 14 * mm)
        canvas.drawString(LEFT * mm, 15 * mm, '100 mm   |   Print at 100%')
        canvas.drawRightString((width - LEFT) * mm, 13 * mm, f'{paper}   {page_number}/{len(pages)}')
        canvas.showPage()
    canvas.save()


def _name(title, paper):
    return f'《{title}》板贴打印版（{paper}）.pdf'


def export_print(data, assets_dir, output_dir, *, render_native=None):
    """Write into the exporter's private staging directory before publishing either paper."""
    assets_dir, output_dir = Path(assets_dir), Path(output_dir)
    files = {paper: _name(data['title'], paper) for paper in PAPER}
    if any((output_dir / filename).exists() for filename in files.values()):
        raise FileExistsError('Print PDF already exists')
    record = {'version': 1, 'files': files, 'sheets': {}, 'sha256': {}}
    with TemporaryDirectory() as temp:
        spool = Path(temp)
        pieces = _prepare(data, assets_dir, spool, render_native)
        record['pieces'] = pieces
        for paper, filename in files.items():
            pages = _pages(pieces, paper)
            for placements in pages:
                for index, tile in placements:
                    pieces[index]['tiles'][paper].append(tile)
            _write_pdf(output_dir / filename, paper, pages, pieces, spool)
            record['sheets'][paper] = len(pages)
            record['sha256'][paper] = hashlib.sha256((output_dir / filename).read_bytes()).hexdigest()
    return record


def _image_draws(page):
    """Read the actual clipped image draws emitted by ReportLab in page coordinates (points)."""
    stack, matrix, rect, clip = [], (1, 0, 0, 1, 0, 0), None, None
    for args, operator in page.get_contents().operations:
        if operator == b'q':
            stack.append((matrix, clip))
        elif operator == b'Q':
            matrix, clip = stack.pop()
        elif operator == b'cm':
            a, b, c, d, e, f = matrix
            g, h, i, j, k, l = map(float, args)
            matrix = (a*g+c*h, b*g+d*h, a*i+c*j, b*i+d*j, a*k+c*l+e, b*k+d*l+f)
        elif operator == b're':
            x, y, w, h = map(float, args)
            a, b, c, d, e, f = matrix
            if b or c or a <= 0 or d <= 0:
                raise ValueError('Unexpected transformed print clipping rectangle')
            rect = (a*x+e, d*y+f, w*a, h*d)
        elif operator in (b'W', b'W*'):
            clip = rect
        elif operator == b'Do':
            yield page['/Resources']['/XObject'][args[0]], matrix, clip


def _near(actual, expected):
    return actual is not None and len(actual) == len(expected) and all(abs(a-b) < .02 for a, b in zip(actual, expected))


def verify_print(data, output_dir, record):
    from pypdf import PdfReader
    pieces = record['pieces']
    if record.get('version') != 1 or [p['id'] for p in pieces] != [a['id'] for a in data['assets']]:
        raise ValueError('Printed pieces do not match the course assets')
    copies = _copies(data)
    if any(p['copies'] != max(1, copies[p['id']]) for p in pieces):
        raise ValueError('Printed quantity does not match simultaneous board use')
    for paper, (width, height) in PAPER.items():
        filename = _name(data['title'], paper)
        path = Path(output_dir) / filename
        if record['files'].get(paper) != filename or hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256'].get(paper):
            raise ValueError('Print PDF hash or filename mismatch: ' + paper)
        pages = _pages(pieces, paper)
        mapped = [[] for _ in pieces]
        checked_images = {}
        with path.open('rb') as stream:
            reader = PdfReader(stream)
            if len(reader.pages) != len(pages) or record['sheets'].get(paper) != len(pages):
                raise ValueError('Print page count mismatch: ' + paper)
            for page, placements in zip(reader.pages, pages):
                expected_size = [0, 0, width * POINTS_PER_MM, height * POINTS_PER_MM]
                if (not _near(list(map(float, page.mediabox)), expected_size)
                        or not _near(list(map(float, page.cropbox)), expected_size)
                        or page.rotation % 360 or float(page.get('/UserUnit', 1)) != 1):
                    raise ValueError('Wrong print paper or orientation: ' + paper)
                draws = list(_image_draws(page))
                if len(draws) != len(placements):
                    raise ValueError('Missing or extra printed images: ' + paper)
                for (obj, matrix, clip), (index, tile) in zip(draws, placements):
                    piece = pieces[index]
                    mapped[index].append(tile)
                    (x, y, w, h), crop = _rectangles(piece, tile, height)
                    affine = (0, w, -h, 0, x, y) if tile['rotation'] else (w, 0, 0, h, x, y)
                    transform = [v * POINTS_PER_MM for v in affine]
                    if not _near(matrix, transform) or not _near(clip, [v * POINTS_PER_MM for v in crop]):
                        raise ValueError('Incorrect physical placement or tile clip: ' + piece['id'])
                    ref = obj.indirect_reference.idnum
                    if ref not in checked_images:
                        checked_images[ref] = hashlib.sha256(obj.get_data()).hexdigest()
                    if list(piece['pixels']) != [obj['/Width'], obj['/Height']] or checked_images[ref] != piece['pixels_sha256']:
                        raise ValueError('Printed image differs from prepared artwork: ' + piece['id'])
                    pw, ph = piece['pixels']
                    if abs(w / h / (pw / ph) - 1) > .0001:
                        raise ValueError('Artwork aspect ratio changed: ' + piece['id'])
                    if abs(25.4 * pw / w - piece['effective_dpi']) > .05:
                        raise ValueError('Incorrect print resolution: ' + piece['id'])
        if any(p['tiles'].get(paper) != expected for p, expected in zip(pieces, mapped)):
            raise ValueError('Incorrect physical piece-to-page map: ' + paper)
