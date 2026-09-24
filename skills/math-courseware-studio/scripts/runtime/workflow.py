"""Read-only course/module dependency checks; content judgment stays with the Skills."""
from pathlib import Path

from . import state

MODES = ('full_course', 'selected_modules')
VIDEO_STEPS = ('video-script', 'video-assets', 'video-director', 'video-board',
               'video-style', 'video-prompts', 'video-upload')
STEPS = ('analysis', 'blueprint', *VIDEO_STEPS, 'cover', 'asset', 'pages', 'page-image',
         'image-export', 'editable-handoff', 'editable-import', 'editable-build',
         'documents', 'collect', 'complete')
BLUEPRINT_COVERAGE = {'teaching_flow', 'activities', 'assessment', 'story_math',
                      'timing', 'page_budget', 'video_inventory', 'source_mapping'}
OWNERS = {'analysis': 'analyze', 'blueprint': 'plan', 'cover': 'plan', 'asset': 'plan',
          'pages': 'pages', 'page-image': 'pages', 'image-export': 'pages',
          'editable-handoff': 'editable', 'editable-import': 'editable',
          'editable-build': 'editable', 'documents': 'documents',
          'video-script': 'video-writer', 'video-assets': 'video-assets',
          'video-director': 'video-director', 'video-board': 'video-storyboard',
          'video-style': 'video-assets', 'video-prompts': 'video-prompts',
          'video-upload': 'video-prompts'}


def initialize(project, mode=None, evidence=''):
    if mode not in (*MODES, None) or (mode and not evidence.strip()):
        raise ValueError('An explicit workflow mode requires actual scope evidence')
    path = state.resolve(project, '_state/workflow.json')
    if path.exists():
        return state.read_json(path)
    record = {'schema_version': '1.0', 'project_mode': mode or 'unclassified',
              'scope_evidence': evidence, 'current_task': {'mode': mode or 'unclassified',
                  'modules': ['studio'] if mode == 'full_course' else [], 'evidence': evidence},
              'stages': {}, 'inputs': {}, 'videos': {}}
    state.write_json(path, record)
    return record


def load(project):
    path = state.resolve(project, '_state/workflow.json')
    if path.exists():
        return state.read_json(path)
    manifest = state.resolve(project, 'manifest.json')
    if manifest.exists():
        return state.read_json(manifest).get('workflow', {})
    return {}


def summary(project):
    data = load(project)
    task = data.get('current_task', {})
    return {'project_mode': data.get('project_mode', 'unclassified'),
            'task_mode': task.get('mode', 'unclassified'), 'modules': task.get('modules', []),
            'focus': task.get('focus'), 'recorded_stages': sorted(data.get('stages', {})),
            'note': 'Recorded artifacts are not completed stages; use workflow-check for a target step.'}


class Inspection:
    def __init__(self, project, data):
        self.project = Path(project)
        self.data = data
        self.issues = []
        self.visited = set()

    def need(self, condition, message):
        if not condition:
            self.issues.append(message)
        return bool(condition)

    def file(self, item, label):
        if not self.need(isinstance(item, dict) and bool(item.get('path')) and bool(item.get('sha256')),
                         label + ': real path and sha256 required'):
            return None
        try:
            path = state.resolve(self.project, item['path'])
            if not self.need(path.is_file() and path.stat().st_size > 0, label + ': missing or empty ' + item['path']):
                return None
            if not self.need(state.sha256(path) == item['sha256'], label + ': stale ' + item['path']):
                return None
            return path
        except (OSError, ValueError, TypeError):
            self.need(False, label + ': invalid file reference')
            return None

    def json_file(self, item, label):
        path = self.file(item, label)
        if path:
            try:
                data = state.read_json(path)
                if isinstance(data, dict):
                    return data
            except (ValueError, OSError):
                pass
            self.need(False, label + ': expected a JSON object')
        return {}

    def evidence(self, record, label, roles=(), approved=False):
        if not self.need(isinstance(record, dict) and bool(record.get('files')), label + ': missing deliverables'):
            return {}
        files = record.get('files', {})
        if not self.need(isinstance(files, dict), label + ': files must map roles to real files'):
            return {}
        for role in roles:
            self.need(role in files, label + ': missing ' + role)
        versions = {}
        for role, item in files.items():
            if self.file(item, label + '/' + role):
                versions[item['path']] = item['sha256']
        sources = record.get('source_versions', {})
        if self.need(isinstance(sources, dict), label + ': invalid source_versions'):
            for path, sha in sources.items():
                self.file({'path': path, 'sha256': sha}, label + '/source')
            versions.update(sources)
        review = self.json_file(record.get('review'), label + '/review')
        self.need(review.get('passed') is True, label + ': internal review not passed')
        reviewed = review.get('source_versions', {})
        self.need(isinstance(reviewed, dict) and all(reviewed.get(p) == h for p, h in versions.items()),
                  label + ': review does not cover current files and sources')
        # Direct material delivery needs no adoption gate, but cannot reuse a rejected version.
        history = state.read_lines(state.resolve(self.project, '_state/decisions.jsonl'))
        for item in files.values():
            if not isinstance(item, dict):
                continue
            latest = next((entry for entry in reversed(history)
                           if any(target.get('path') == item.get('path') and target.get('sha256') == item.get('sha256')
                                  for target in entry.get('targets', []))), None)
            self.need(latest is None or latest.get('decision') == 'approved',
                      label + ': current version was rejected: ' + str(item.get('path')))
        if approved:
            # Reuse existing course decisions; standalone tasks may retain the same decision format in a file.
            current = bool(files) and all(state.is_approved(self.project, item['path'])
                                         for item in files.values() if isinstance(item, dict) and item.get('path'))
            if not current:
                decision = self.json_file(record.get('approval'), label + '/approval')
                approved_files = {x.get('path'): x.get('sha256') for x in decision.get('targets', [])
                                  if isinstance(x, dict)}
                self.need(decision.get('decision') == 'approved' and bool(str(decision.get('user_evidence', '')).strip())
                          and all(approved_files.get(x.get('path')) == x.get('sha256') for x in files.values()),
                          label + ': actual adoption of these files is required')
        return files

    def stage(self, name, approved=False):
        record = self.data.get('stages', {}).get(name, {})
        if (name, approved) not in self.visited:
            self.visited.add((name, approved))
            self.evidence(record, name, approved=approved)
            if name == 'analysis':
                self.analysis(record)
            elif name == 'blueprint':
                ids = record.get('video_ids', [])
                self.need(isinstance(ids, list) and bool(ids) and len(set(ids)) == len(ids),
                          'blueprint: unique planned video_ids required')
                self.need(type(record.get('total_pages')) is int and record['total_pages'] > 0,
                          'blueprint: total page budget required')
                self.need(BLUEPRINT_COVERAGE <= set(record.get('coverage', [])),
                          'blueprint: teaching flow, activities, assessment, story/math, timing, pages, videos and source mapping required')
            elif name == 'pages':
                self.page_plan(record)
            elif name == 'shared-assets':
                choice = record.get('style_choice', {})
                selected = choice.get('selected')
                self.file(selected, 'shared-assets/selected-style')
                if isinstance(selected, dict):
                    self.visual({'files': {'selected': selected}}, 'shared-assets/selected-style')
                self.need(choice.get('kind') in ('existing', 'candidates'),
                          'shared-assets: record the existing adopted style or cover candidates')
                self.need(selected in record.get('files', {}).values(),
                          'shared-assets: selected style must belong to adopted actual files')
                if choice.get('kind') == 'candidates':
                    candidates = choice.get('candidates', [])
                    valid = isinstance(candidates, list) and len(candidates) == 4 and all(isinstance(x, dict) for x in candidates)
                    self.need(valid and len({x.get('sha256') for x in candidates}) == 4,
                              'shared-assets: four distinct real cover candidates required')
                    if valid:
                        for item in candidates:
                            self.visual({'files': {'candidate': item}}, 'shared-assets/cover-candidate')
                    self.need(selected in candidates, 'shared-assets: selected cover is outside candidates')
                self.visual(record, 'shared-assets')
            dependencies = {'blueprint': ('analysis',), 'video-preparation': ('blueprint',),
                'pages': ('blueprint', 'video-preparation'), 'images': ('pages', 'shared-assets'),
                'editable': ('pages', 'images'), 'documents': ('pages', 'images'),
                'delivery': ('editable', 'documents')}
            if self.data.get('current_task', {}).get('mode') == 'full_course':
                self.bind(record, name, *(self.data.get('stages', {}).get(dep, {})
                                         for dep in dependencies.get(name, ())))
                if name in ('images', 'editable', 'documents', 'delivery'):
                    self.output(record, name)
        return record

    def bind(self, record, label, *dependencies):
        sources = record.get('source_versions', {})
        for dependency in dependencies:
            for item in dependency.get('files', {}).values():
                self.need(sources.get(item.get('path')) == item.get('sha256'),
                          label + ': current dependency not bound: ' + str(item.get('path')))

    def page_plan(self, record):
        files = record.get('files', {})
        pointer = files.get('pages') if isinstance(files, dict) else None
        self.need(isinstance(pointer, dict) and pointer.get('path', '').replace('\\', '/') == '_state/pages.json',
                  'pages: use the actual canonical _state/pages.json')
        page_data = self.json_file(pointer, 'pages/canonical')
        pages = page_data.get('pages', [])
        plan = self.data.get('stages', {}).get('blueprint', {})
        self.need(len(pages) == plan.get('total_pages'), 'pages: all pages including videos must fit the adopted budget')
        ids = [p.get('page_id') for p in pages]
        orders = [p.get('order') for p in pages]
        self.need(bool(pages) and None not in ids and len(set(ids)) == len(ids)
                  and set(orders) == set(range(1, len(pages) + 1)), 'pages: unique IDs and complete display order required')
        mapped = set()
        planned = set(plan.get('video_ids', []))
        for page in pages:
            for vid in page.get('video_ids', []):
                mapped.add(vid)
                self.need(vid in planned, 'pages: unknown video ' + str(vid))
                objects = {x.get('object_id') for x in page.get('native_objects', [])}
                self.need('video-frame-' + vid in objects, 'pages: independent playback area missing for ' + vid)
        self.need(mapped == planned, 'pages: every planned video needs an actual page mapping')

    def visual(self, record, label):
        from PIL import Image
        images = [x for x in record.get('files', {}).values()
                  if Path(x.get('path', '')).suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp')]
        self.need(bool(images), label + ': actual images required; a list or prompt is insufficient')
        for item in images:
            path = self.file(item, label)
            if path:
                try:
                    with Image.open(path) as image:
                        image.verify()
                except (OSError, ValueError, SyntaxError):
                    self.need(False, label + ': invalid image bytes')

    def output(self, record, kind):
        files = record.get('files', {})
        expected = self.data.get('stages', {}).get('blueprint', {}).get('total_pages')
        if kind == 'images':
            pages = state.read_json(state.resolve(self.project, '_state/pages.json')).get('pages', [])
            self.need(len(pages) == expected, 'images: current full page count required')
            for page in pages:
                item = page.get('image', {})
                self.need(item in files.values(), 'images: each current page image must be in the reviewed deliverables')
                self.visual({'files': {'image': item}}, 'images/' + str(page.get('page_id')))
        elif kind == 'editable':
            from pptx import Presentation
            path = self.file(files.get('pptx'), 'editable/pptx')
            if path:
                try:
                    self.need(path.suffix.lower() == '.pptx' and len(Presentation(path).slides) == expected,
                              'editable: real PPTX with the full page count required')
                except Exception as exc:
                    self.need(False, 'editable: cannot read PPTX (' + type(exc).__name__ + ')')
        elif kind == 'documents':
            for role in ('classroom-script', 'lesson-presentation', 'lesson-plan'):
                path = self.file(files.get(role), 'documents/' + role)
                if path:
                    try:
                        if path.suffix.lower() == '.docx':
                            from docx import Document
                            doc = Document(path)
                            populated = bool(doc.tables or any(p.text.strip() for p in doc.paragraphs))
                        elif path.suffix.lower() == '.pdf':
                            from pypdf import PdfReader
                            populated = bool(PdfReader(path).pages)
                        else:
                            populated = path.suffix.lower() == '.md' and bool(path.read_text(encoding='utf-8').strip())
                        self.need(populated, 'documents/' + role + ': actual document required')
                    except Exception as exc:
                        self.need(False, 'documents/' + role + ': unreadable document (' + type(exc).__name__ + ')')
        elif kind == 'delivery':
            self.file(files.get('manifest'), 'delivery/manifest')
            self.playback(files.get('wps'), 'delivery/WPS', record.get('source_versions', {}))

    def playback(self, reference, label, required):
        report = self.json_file(reference, label)
        versions = report.get('source_versions', {})
        self.need(report.get('passed') is True and report.get('inspection') in ('actual', 'user_report')
                  and bool(report.get('basis')),
                  label + ': actual playback/display inspection or explicit user report required')
        self.need(bool(required) and all(versions.get(p) == sha for p, sha in required.items()),
                  label + ': inspection must cover current media and deliverables')

    def final_video(self, record, label):
        record = record or {}
        self.evidence(record, label, roles=('media', 'playback'), approved=True)
        files = record.get('files', {})
        path = self.file(files.get('media'), label + '/media')
        if path:
            with path.open('rb') as stream:
                header = stream.read(64)
            suffix = path.suffix.lower()
            # Container identity only, not a substitute for decoding, viewing or actual playback.
            valid = (suffix in ('.mp4', '.m4v', '.mov') and len(header) >= 16 and header[4:8] == b'ftyp'
                     or suffix in ('.webm', '.mkv') and header.startswith(b'\x1a\x45\xdf\xa3')
                     or suffix == '.avi' and header[:4] == b'RIFF' and header[8:12] == b'AVI ')
            self.need(valid, label + ': actual supported video container required, not a text plan')
        deck = self.data.get('stages', {}).get('editable', {}).get('files', {}).get('pptx', {})
        required = {x['path']: x['sha256'] for x in (files.get('media', {}), deck) if x.get('path') and x.get('sha256')}
        self.playback(files.get('playback'), label + '/playback', required)

    def analysis(self, record):
        source = self.json_file(record.get('source_review'), 'analysis/source_review')
        if source.get('kind') == 'requirements':
            self.need(bool(source.get('basis')) and bool(source.get('limitations')),
                      'analysis: requirements-only analysis must state basis and missing original materials')
            return
        self.need(source.get('kind') == 'uploaded_courseware', 'analysis: identify uploaded courseware or requirements')
        count = source.get('page_count')
        pages = source.get('page_map', [])
        self.need(type(count) is int and count > 0, 'analysis: original total page_count required')
        numbers = [p.get('page') for p in pages if isinstance(p, dict)] if isinstance(pages, list) else []
        self.need(type(count) is int and count > 0 and len(numbers) == count
                  and set(numbers) == set(range(1, count + 1))
                  and all(isinstance(p, dict) and p.get('role') for p in pages),
                  'analysis: page_map must cover every original page and function')
        for key in ('overall_quality', 'strengths', 'improvements', 'teaching_flow'):
            self.need(bool(source.get(key)), 'analysis: visible report missing ' + key)
        inventory = source.get('video_inventory', {})
        if not self.need(isinstance(inventory, dict), 'analysis: video inventory required'):
            return
        items = inventory.get('items', [])
        if not self.need(isinstance(items, list), 'analysis: video inventory items must be a list'):
            return
        ids, occurrences = [], 0
        for video in items:
            if not self.need(isinstance(video, dict), 'analysis: invalid video entry'):
                continue
            ids.append(video.get('video_id'))
            locations = video.get('pages', [])
            valid = isinstance(locations, list) and bool(locations) and all(
                type(p) is int and type(count) is int and 1 <= p <= count for p in locations)
            self.need(valid, 'analysis: video needs actual original page locations')
            occurrences += len(locations) if isinstance(locations, list) else 0
            for key in ('content', 'function', 'basis'):
                self.need(bool(video.get(key)), 'analysis: video missing ' + key)
            self.need(video.get('inspection') in ('viewed', 'partial', 'document_only', 'unavailable'),
                      'analysis: distinguish actual viewing/listening from inferred or unavailable content')
            if video.get('inspection') != 'viewed':
                self.need(bool(inventory.get('limitations')), 'analysis: unread video limitations must be visible')
        self.need(None not in ids and len(ids) == len(set(ids)), 'analysis: deduplicate video IDs')
        if inventory.get('complete') is True:
            self.need(inventory.get('unique_count') == len(ids), 'analysis: unique video count differs from inventory')
        else:
            self.need(inventory.get('complete') is False and bool(inventory.get('limitations')),
                      'analysis: incomplete video inventory needs explicit limitations')
            self.need(inventory.get('unique_count') is None, 'analysis: do not claim exact total for unknown video inventory')
        self.need(inventory.get('occurrence_count') == occurrences,
                  'analysis: video occurrence count differs from actual listed locations')

    def blueprint(self):
        self.stage('analysis')
        return self.stage('blueprint', approved=True)

    def video(self, video_id):
        reference = self.data.get('videos', {}).get(video_id)
        if reference:
            manifest = self.json_file(reference, 'video/' + str(video_id))
        else:
            path = self.project / 'manifest.json'
            manifest = state.read_json(path) if path.is_file() else {}
        self.need(bool(video_id) and manifest.get('video_id') == video_id, 'video: current video_id and manifest required')
        route = manifest.get('route')
        aliases = {'camera_movement_and_cut': 'shots', 'fixed_talking': 'talking'}
        route = aliases.get(route, route)
        self.need(route in ('shots', 'talking'), 'video: declare shots or talking route from actual content')
        return route, manifest.get('workflow', {})

    def video_step(self, step, video_id):
        if step == 'video-script':
            return
        route, video = self.video(video_id)
        if route not in ('shots', 'talking'):
            return
        if route == 'talking' and step in ('video-director', 'video-board', 'video-style'):
            self.need(False, step + ': not applicable to fixed talking; continue first frame and talking packet')
            return
        dependencies = {
            'video-assets': ['script', 'preview'] if route == 'shots' else ['script'],
            'video-director': ['script', 'voice', 'assets'],
            'video-board': ['director', 'assets'], 'video-style': ['assets', 'storyboard'],
            'video-prompts': ['script', 'voice', 'director', 'storyboard', 'style'],
            'video-upload': ['prompts']}
        if route == 'talking' and step == 'video-prompts':
            dependencies[step] = ['script', 'first-frame']
        products = video.get('products', {})
        chains = {'preview': ('script',), 'voice': ('script',),
                  'director': ('script', 'voice', 'assets'), 'storyboard': ('director', 'assets'),
                  'style': ('assets', 'storyboard'), 'first-frame': ('script',),
                  'prompts': ('script', 'first-frame') if route == 'talking'
                             else ('script', 'voice', 'director', 'storyboard', 'style')}
        checked = set()

        def inspect(name):
            if name in checked:
                return
            checked.add(name)
            record = products.get(name, {})
            self.evidence(record, str(video_id) + '/' + name,
                          approved=route != 'talking' and (
                              name in ('script', 'preview', 'assets', 'style', 'first-frame')
                              or (name == 'storyboard' and step in ('video-style', 'video-prompts', 'video-upload'))))
            if name in ('preview', 'assets', 'first-frame', 'storyboard'):
                self.visual(record, str(video_id) + '/' + name)
            if name == 'storyboard' and step in ('video-style', 'video-prompts', 'video-upload') and 'director' in products:
                director = dict(products['director'])
                # One grouped decision can cover both actual files; no separate approval round.
                director['approval'] = director.get('approval') or record.get('approval')
                self.evidence(director, str(video_id) + '/director-group-adoption', approved=True)
            # Imported later-stage products need only their real supplied dependencies.
            # Current registered sources cannot silently remain bound to preserved old versions.
            for dependency in chains.get(name, ()):
                if dependency in products:
                    self.bind(record, str(video_id) + '/' + name, products[dependency])
                    inspect(dependency)
            if name == 'script' and self.data.get('current_task', {}).get('mode') == 'full_course':
                self.bind(record, str(video_id) + '/script', self.data.get('stages', {}).get('blueprint', {}))

        for name in dependencies[step]:
            inspect(name)

    def preparation(self):
        plan = self.blueprint()
        ready = self.stage('video-preparation', approved=True)
        planned = plan.get('video_ids', [])
        self.need(set(ready.get('video_ids', [])) == set(planned), 'video-preparation: must cover all planned videos')
        for video_id in planned:
            route, video = self.video(video_id)
            roles = ['script', 'voice', 'frame_plan', 'prompts', 'production', 'classroom']
            if route == 'shots':
                roles += ['director', 'board_plan']
            prep = video.get('preparation', {})
            self.evidence(prep, str(video_id) + '/preparation', roles, approved=True)
            self.bind(prep, str(video_id) + '/preparation', plan, *video.get('products', {}).values())
            self.bind(ready, 'video-preparation', prep)
            for missing in prep.get('missing_assets', []):
                self.need(isinstance(missing, dict) and all(missing.get(k) for k in ('asset_id', 'reason', 'acquire', 'blocks')),
                          str(video_id) + ': missing assets need a concrete acquisition plan and affected work')

    def input(self, owner, roles=('source',)):
        records = self.data.get('inputs', {})
        entry = records.get(owner)
        if entry is None and owner.startswith('video-'):
            entry = records.get('video')
        self.evidence(entry, 'input/' + owner, roles)

    def route(self, requested=None):
        choice = self.data.get('route_choice', {})
        self.need(choice.get('route') in ('A', 'B') and bool(str(choice.get('user_evidence', '')).strip()),
                  'editable: actual explicit A/B choice required; a clear text-free refill request counts as B')
        if requested is not None:
            self.need(requested == choice.get('route'), 'editable: requested route differs from actual A/B choice')


def check(project, step, video_id=None, route=None):
    data = load(project)
    audit = Inspection(project, data)
    task = data.get('current_task', {})
    audit.need(step in STEPS, 'Unknown workflow step: ' + str(step))
    audit.need(data.get('schema_version') == '1.0', 'workflow: missing or unsupported index; classify and inspect existing results')
    audit.need(data.get('project_mode') in MODES and bool(str(data.get('scope_evidence', '')).strip()),
               'workflow: unclassified project scope; do not infer scope from the called Skill')
    mode = task.get('mode')
    audit.need(mode in MODES and bool(str(task.get('evidence', '')).strip()), 'workflow: actual current task scope required')
    if audit.issues:
        return {'allowed': False, 'step': step, 'mode': mode, 'issues': audit.issues}
    owner = OWNERS.get(step)
    if mode == 'selected_modules':
        modules = {m.removeprefix('math-courseware-') for m in task.get('modules', []) if isinstance(m, str)}
        audit.need(bool(modules), 'workflow: selected modules required')
        if owner:
            allowed = owner in modules or (owner.startswith('video-') and 'video' in modules)
            if step == 'asset':
                allowed = allowed or bool(modules & {'video', 'video-assets'})
            audit.need(allowed, 'workflow: ' + step + ' is outside the requested modules')
        if step in VIDEO_STEPS:
            audit.input(owner)
            audit.video_step(step, video_id)
        elif step in ('editable-import', 'editable-build'):
            audit.input('editable', ('deck', 'text') if step == 'editable-build' else ('deck',))
            audit.route(route)
        elif step == 'editable-handoff':
            audit.input('editable')
            audit.route(route)
        elif step in ('collect', 'complete'):
            if step == 'complete':
                # A local task cannot certify completion of its parent full course.
                audit.need(data.get('project_mode') != 'full_course', 'complete: restore full-course scope to check whole-course completion')
                audit.stage('delivery')
            else:
                for module in modules:
                    audit.input(module)
        elif owner:
            audit.input(owner)
    else:
        if step == 'blueprint':
            audit.stage('analysis')
        elif step in VIDEO_STEPS or step in ('cover', 'asset'):
            plan = audit.blueprint()
            if step in VIDEO_STEPS:
                audit.need(video_id in plan.get('video_ids', []), 'video: target is outside the adopted whole-course inventory')
                audit.video_step(step, video_id)
        elif step not in ('analysis', 'collect'):
            audit.preparation()
            if step != 'pages':
                audit.stage('pages', approved=True)
            if step == 'page-image':
                audit.stage('shared-assets', approved=True)
            if step in ('image-export', 'editable-handoff', 'editable-import', 'editable-build', 'documents', 'complete'):
                audit.stage('images', approved=True)
            if step.startswith('editable-'):
                audit.route(route)
            if step == 'complete':
                audit.stage('shared-assets', approved=True)
                for name in ('editable', 'documents', 'delivery'):
                    audit.stage(name)
                for vid in data.get('stages', {}).get('blueprint', {}).get('video_ids', []):
                    _, video = audit.video(vid)
                    audit.final_video(video.get('final', {}), vid + '/actual-video')
    return {'allowed': not audit.issues, 'step': step, 'mode': mode,
            'project_mode': data.get('project_mode'), 'issues': list(dict.fromkeys(audit.issues)),
            'completion_scope': 'whole_course' if mode == 'full_course' else 'selected_modules',
            'semantic_review': 'Files and recorded reviews checked; teaching, visuals and playback need actual inspection.'}


def require(project, step, video_id=None, route=None):
    result = check(project, step, video_id=video_id, route=route)
    if not result['allowed']:
        raise ValueError('Workflow blocked: ' + '; '.join(result['issues']))
    return result


def require_image(project, purpose):
    if purpose == 'test':
        return {'allowed': True, 'completion_scope': 'image_route_test_only'}
    steps = {'page': 'page-image', 'cover': 'cover', 'asset': 'asset',
             'erase': 'editable-handoff', 'repair': 'page-image'}
    if purpose not in steps:
        raise ValueError('Unknown image task purpose')
    if purpose == 'repair':
        data = load(project)
        task = data.get('current_task', {})
        modules = {m.removeprefix('math-courseware-') for m in task.get('modules', []) if isinstance(m, str)}
        if task.get('mode') == 'selected_modules' and 'editable' in modules and data.get('route_choice', {}).get('route') == 'B':
            return require(project, 'editable-handoff', route='B')
    return require(project, steps[purpose], route='B' if purpose == 'erase' else None)


def basis_paths(project):
    """Only actual canonical dependencies; external refill does not need an invented story."""
    data = load(project)
    full = data.get('current_task', {}).get('mode') == 'full_course'
    paths = ['_state/pages.json']
    pages = state.read_json(state.resolve(project, paths[0])).get('pages', [])
    for name, field, array, identifier in [('math', 'math_ids', 'problems', 'math_id'),
            ('story', 'story_ids', 'events', 'event_id'), ('assets', 'asset_refs', 'assets', 'asset_id')]:
        refs = [ref for page in pages for ref in page.get(field, [])]
        if full or refs:
            path = '_state/' + name + '.json'
            contents = state.read_json(state.resolve(project, path))
            records = {row[identifier]: row for row in contents.get(array, [])}
            for ref in refs:
                identity = ref['asset_id'] if isinstance(ref, dict) else ref
                if identity not in records or (isinstance(ref, dict) and records[identity].get('version') != ref.get('version')):
                    raise ValueError('Unknown or outdated ' + name + ' reference: ' + str(identity))
            paths.append(path)
    return paths
