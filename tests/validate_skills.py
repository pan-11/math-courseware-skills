"""Run the official validator and inspect bundle metadata, links and Python syntax."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if importlib.util.find_spec('yaml') is None:
    sys.path.insert(0, str(ROOT / 'tests/vendor'))
import yaml


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--validator', required=True, type=Path)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('official_validator', args.validator)
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    results = []
    for folder in sorted((ROOT / 'skills').iterdir()):
        if not folder.is_dir():
            continue
        passed, message = validator.validate_skill(folder)
        if not passed:
            raise ValueError(folder.name + ': ' + message)
        metadata = yaml.safe_load((folder / 'agents/openai.yaml').read_text(encoding='utf-8'))
        interface = metadata['interface']
        assert 25 <= len(interface['short_description']) <= 64, folder.name
        assert '$' + folder.name in interface['default_prompt'], folder.name
        links = 0
        for path in folder.rglob('*.md'):
            body = path.read_text(encoding='utf-8')
            assert '\ufffd' not in body, str(path)
            for target in re.findall(r'\[[^\]\n]*\]\(([^)\n]+)\)', body):
                if target.startswith(('http:', 'https:', '#')):
                    continue
                relative = target.strip('<>').split('#', 1)[0]
                assert (path.parent / relative).resolve().exists(), (str(path), target)
                links += 1
        for path in folder.rglob('*.py'):
            compile(path.read_text(encoding='utf-8'), str(path), 'exec')
        results.append({'skill': folder.name, 'official_validator': 'PASS', 'local_links': links})
    assert {item['skill'] for item in results} == {
        'math-courseware-' + name for name in
        ('studio', 'analyze', 'plan', 'video', 'video-writer', 'video-assets',
         'video-director', 'video-storyboard', 'video-prompts',
         'pages', 'editable', 'documents')}
    print(json.dumps({'status': 'PASS', 'skills': results, 'yaml_version': yaml.__version__}, indent=2))


if __name__ == '__main__':
    main()
