"""Recover numbers from positioned PDF glyphs, never concatenate merged cells.

Spaces embedded inside printed numbers have zero/small physical gaps; distinct
columns have larger gaps. Unknown measures remain unscored even when legible.
"""
import math
import re

MONEY = re.compile(r'^(?:\(?-?\$?\d[\d,]*(?:\.\d+)?\)?|[-–—])$')
FIELDS = ('budget', 'forecast', 'forecast_variance', 'current_ytd_actual',
          'actual_percent_of_forecast', 'forecast_available', 'prior_ytd_actual')


def positioned_tokens(page, boxes):
    tokens = []
    for box in boxes:
        if not box:
            continue
        chars = [c for c in page.chars if c['text'].strip()
                 and box[0] - .1 <= c['x0'] and c['x1'] <= box[2] + .1
                 and box[1] <= (c['top'] + c['bottom']) / 2 < box[3]]
        lines = []
        for c in sorted(chars, key=lambda c: (c['top'], c['x0'])):
            line = next((line for line in lines if abs(line[0]['top'] - c['top']) < 2), None)
            if line is None:
                lines.append([c])
            else:
                line.append(c)
        for line in lines:
            groups = []
            for c in sorted(line, key=lambda c: c['x0']):
                if not groups or c['x0'] - groups[-1][-1]['x1'] > max(2, c['size'] * .65):
                    groups.append([])
                groups[-1].append(c)
            for group in groups:
                token = ''.join(c['text'] for c in group)
                if MONEY.fullmatch(token) or re.fullmatch(r'\d+(?:\.\d+)?%', token):
                    tokens.append({'text': token, 'x0': round(group[0]['x0'], 3),
                                   'x1': round(group[-1]['x1'], 3),
                                   'top': round(group[0]['top'], 3)})
    return sorted(tokens, key=lambda t: (round(t['top'] / 3), t['x0']))


def numeric(token):
    if token in ('-', '–', '—'):
        return 0.0
    value = token.replace('$', '').replace(',', '').replace('%', '')
    if value.startswith('(') and value.endswith(')'):
        value = '-' + value[1:-1]
    result = float(value)
    if not math.isfinite(result) or abs(result) > 10_000_000_000:
        raise ValueError('Unbounded numeric cell')
    return result


def typed_operating_fields(context, header, tokens):
    """Only release a known seven-column expense table with independent controls."""
    header = re.sub(r'\s+', ' ', header).lower()
    texts = [t['text'] for t in tokens]
    if ('operating results - expenses' not in context.lower()
            or not all(s in header for s in ('prior ytd', 'current ytd', 'projection'))
            or len(texts) != 7 or not texts[4].endswith('%')
            or any('%' in t for i, t in enumerate(texts) if i != 4)):
        return None, ['untyped_source_row']
    fields = dict(zip(FIELDS, map(numeric, texts)))
    errors = []
    if abs(fields['budget'] - fields['forecast'] - fields['forecast_variance']) > 2:
        errors.append('budget_forecast_variance_control')
    if abs(fields['forecast'] - fields['current_ytd_actual'] - fields['forecast_available']) > 2:
        errors.append('forecast_available_control')
    if fields['forecast'] and abs(fields['current_ytd_actual'] / fields['forecast'] * 100
                                  - fields['actual_percent_of_forecast']) > .16:
        errors.append('actual_percentage_control')
    return fields, errors
