"""Deterministic checks; teaching and visual review remain explicit human/agent work."""
import importlib.util
from pathlib import Path
import shutil
import sys
from . import state


def doctor():
    data = {'python': sys.executable, 'python_version': sys.version.split()[0],
            'modules': {x: importlib.util.find_spec(x) is not None for x in
                        ['pptx', 'docx', 'PIL', 'pypdf', 'reportlab']},
            'officecli': shutil.which('officecli'), 'soffice': shutil.which('soffice'),
            'native_render_verified': False, 'wps': None, 'kaiti': None}
    if sys.platform == 'win32':
        import winreg
        for hive in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
            try:
                with winreg.OpenKey(hive, r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\wpp.exe') as key:
                    data['wps'] = winreg.QueryValue(key, None)
            except OSError:
                pass
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts') as key:
                data['kaiti'] = winreg.QueryValueEx(key, 'KaiTi (TrueType)')[0]
        except OSError:
            pass
    return data


def validate(project):
    errors = []
    data = state.load_project(project)
    records = {name: state.read_json(state.resolve(project, '_state/' + name + '.json')) for name in state.RECORDS}
    problems = records['math'].get('problems', [])
    assets = records['assets'].get('assets', [])
    pages = records['pages'].get('pages', [])
    math_ids = {x['math_id'] for x in problems}
    asset_ids = {x['asset_id']: x for x in assets}
    for items, key in [(problems, 'math_id'), (assets, 'asset_id'), (pages, 'page_id')]:
        ids = [x.get(key) for x in items]
        if len(set(ids)) != len(ids) or None in ids:
            errors.append('Missing or duplicate ' + key)
    orders = [p.get('order') for p in pages]
    if orders and (len(set(orders)) != len(orders) or any(not isinstance(x, int) or x < 1 for x in orders)):
        errors.append('Page order must be distinct positive integers')
    for page in pages:
        for math_id in page.get('math_ids', []):
            if math_id not in math_ids:
                errors.append(f'{page["page_id"]}: unknown math {math_id}')
        for ref in page.get('asset_refs', []):
            asset = asset_ids.get(ref['asset_id'])
            if not asset or asset.get('version') != ref.get('version'):
                errors.append(f'{page["page_id"]}: invalid asset version {ref}')
        units = page.get('text_units', [])
        if len({u['unit_id'] for u in units}) != len(units):
            errors.append(page['page_id'] + ': duplicate text units')
        for unit in units:
            if not isinstance(unit.get('text'), str) or not unit['text'].strip():
                errors.append(page['page_id'] + ': empty required text')
    for asset in assets:
        for file in asset.get('files', []):
            try:
                if state.sha256(state.resolve(project, file['path'])) != file['sha256']:
                    errors.append(asset['asset_id'] + ': image hash differs')
            except (OSError, ValueError):
                errors.append(asset['asset_id'] + ': missing or invalid image path')
    for name, artifact in data.get('artifacts', {}).items():
        try:
            if state.sha256(state.resolve(project, artifact['path'])) != artifact['sha256']:
                errors.append(name + ': artifact changed outside registered version')
        except (OSError, ValueError):
            errors.append(name + ': artifact missing')
    return {'ok': not errors, 'errors': errors, 'pages': len(pages), 'assets': len(assets),
            'math_problems': len(problems), 'visual_and_teaching_review': 'not established by this check'}
