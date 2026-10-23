"""Story-first production boundaries, using retained synthetic files and fake HTTP only."""
import unittest
import subprocess
import types

import test_grouped_gates as group_fixtures
from test_image_api import Transport
from workflow_fixture import enable_modules
from runtime import state, workflow, prompts, image_api, autopilot, grouped_gates, story_adoption, automation_store as store


class StoryAdoptionTests(unittest.TestCase):
    def setUp(self):
        self.f = group_fixtures.GroupedGateTests('runTest')
        self.f.setUp()
        self.root = self.f.root

    def image_setup(self, route='builtin', policy='grouped_creative_v1'):
        self.f.image_setup(route, adopted_story=False)
        if policy != 'grouped_creative_v1':
            # Only used to inspect an isolated historical run, never production state.
            run = store.load_run(self.root)
            run['review_policy'] = policy
            store.save_run(self.root, run, 'synthetic-policy-fixture')

    def approve_stories(self):
        targets = [item for video in self.f.manifests.values()
                   for name in ('script', 'voice')
                   for item in video['workflow']['products'][name]['files'].values()]
        return state.record_approval(self.root, dict(targets=targets,
            user_evidence='Synthetic actual adoption of all full scenes and spoken lines'))

    def reject_story(self):
        target = next(iter(self.f.manifests['V001']['workflow']['products']['script']['files'].values()))
        state.record_approval(self.root, dict(targets=[target], decision='rejected',
            user_evidence='Synthetic request changes the ending: evidence must reach the classroom'))

    def test_core_story_approval_cannot_prepare_unread_complete_scripts(self):
        self.image_setup()
        self.assertTrue(state.is_approved(self.root, '_state/story.json'))
        with self.assertRaisesRegex(ValueError, 'story|script|voice'):
            self.f.prepare_image()

    def test_canonical_records_cannot_impersonate_full_text_through_layout_aliases(self):
        for layout in ('legacy', 'four-folders', 'five-folders'):
            self.setUp()
            if layout != 'legacy':
                self.root = self.root.with_name(self.root.name + '-' + layout)
                self.f.root = self.root
                state.init_project(self.root, 'Synthetic story aliases', mode='full_course',
                    scope_evidence='Synthetic whole story review', layout=layout)
                self.f.data = workflow.load(self.root)
            self.image_setup()
            self.approve_stories()
            for name in ('story', 'math', 'pages', 'assets'):
                with self.subTest(layout=layout, canonical=name):
                    logical = '_state/' + name + '.json'
                    physical = state.resolve(self.root, logical)
                    alias = (logical if name == 'story' else physical.relative_to(self.root).as_posix()
                             if name == 'math' else ('02_work/' + logical if layout != 'legacy' else './' + logical)
                             if name == 'pages' else str(physical))
                    item = {'path': alias, 'sha256': state.sha256(physical)}
                    products = self.f.manifests['V001']['workflow']['products']
                    products['script'] = self.f.record('impersonated-' + name + '-script', files={'text': item},
                        complete=True, sources=self.f.versions(self.f.data['stages']['blueprint']))
                    products['voice'] = self.f.record('impersonated-' + name + '-voice', files={'text': item},
                        verbatim=True, sources=self.f.versions(products['script']))
                    self.f.save_video('V001'); self.f.save(); self.approve_stories()
                    issues = story_adoption.inspect(self.root)['issues']
                    self.assertTrue(any('canonical' in issue for issue in issues), issues)
                    with self.assertRaisesRegex(ValueError, 'canonical'):
                        self.f.prepare_image()

    def test_real_structured_full_text_may_share_one_file_and_reference_canonical_sources(self):
        self.image_setup()
        for vid in self.f.ids:
            item = self.f.text('planning/' + vid + '-full-story.json',
                '{"scenes":[{"visual":"Child lays two equal tiles with a visible gap",'
                '"dialogue":"These tiles leave a gap. We must move them before reporting back."}]}')
            products = self.f.manifests[vid]['workflow']['products']
            products['script'] = self.f.record(vid + '-structured-script', files={'text': item}, complete=True,
                sources={**self.f.versions(self.f.data['stages']['blueprint']),
                         '_state/story.json': self.f.ref('_state/story.json')['sha256']})
            products['voice'] = self.f.record(vid + '-structured-voice', files={'text': item}, verbatim=True,
                sources=self.f.versions(products['script']))
            self.f.save_video(vid)
        self.f.save(); self.approve_stories()
        self.assertEqual(story_adoption.inspect(self.root)['issues'], [])
        self.assertTrue(self.f.prepare_image()['jobs'])

    def test_inspect_accepts_string_project_for_standalone_manifest(self):
        self.f.fixture(('talking',))
        self.f.data = enable_modules(self.root, ['video'])
        state.write_json(self.root / 'manifest.json', self.f.manifests['V001'])
        self.approve_stories()
        self.assertEqual(story_adoption.inspect(str(self.root))['issues'], [])

    def test_old_pending_candidate_cannot_submit_after_story_rejection(self):
        self.image_setup('openai_image_api')
        self.approve_stories()
        batch = self.f.prepare_image()
        self.reject_story()
        transport = Transport()
        with self.assertRaisesRegex(ValueError, 'story|script|voice'):
            image_api.run_job(self.root, batch['jobs'][0], transport, timeout=1, poll_interval=0)
        self.assertEqual(transport.posts, [])

    def test_first_builtin_registration_cannot_hide_unadopted_story(self):
        self.image_setup()
        self.approve_stories()
        batch = self.f.prepare_image()
        path = state.resolve(self.root, batch['jobs'][0])
        job = state.read_json(path)
        # Ordinary old jobs need the same check as creative candidates.
        job.pop('creative_candidate', None)
        state.write_json(path, job)
        self.reject_story()
        source = self.f.image('planning/actual-return.png')
        before = state.resolve(self.root, source['path']).read_bytes()
        with self.assertRaisesRegex(ValueError, 'story|script|voice'):
            image_api.register_builtin(self.root, dict(job_path=batch['jobs'][0],
                input_digest=job['input_digest'], image_path=str(state.resolve(self.root, source['path'])),
                tool_evidence='Synthetic received bytes, not proof of old dispatch'))
        self.assertEqual(state.read_json(path)['status'], 'pending')
        self.assertEqual(state.resolve(self.root, source['path']).read_bytes(), before)

    def test_talking_route_needs_actual_text_adoption(self):
        self.f.fixture(('talking',))
        self.f.start()
        self.assertFalse(workflow.check(self.root, 'video-assets', video_id='V001')['allowed'])
        self.approve_stories()
        self.assertTrue(workflow.check(self.root, 'video-assets', video_id='V001')['allowed'])
        self.assertFalse(workflow.check(self.root, 'video-director', video_id='V001')['allowed'])

    def test_talking_later_voice_rejection_blocks_prompt_use_and_upload(self):
        self.f.fixture(('talking',))
        videos = self.f.data['videos']
        self.f.data = enable_modules(self.root, ['video'])
        self.f.data['videos'] = videos
        products = self.f.manifests['V001']['workflow']['products']
        products['prompts'] = self.f.record('talking-prompt',
            sources=self.f.versions(products['script'], products['voice'], products['first-frame']))
        self.f.save_video('V001'); self.f.save(); self.approve_stories()
        for step in ('video-prompts', 'video-upload'):
            self.assertTrue(workflow.check(self.root, step, video_id='V001')['allowed'])
        state.record_approval(self.root, dict(targets=list(products['voice']['files'].values()),
            decision='rejected', user_evidence='Synthetic later rejection of current spoken wording'))
        for step in ('video-prompts', 'video-upload'):
            result = workflow.check(self.root, step, video_id='V001')
            self.assertFalse(result['allowed'], result)
            self.assertTrue(any('voice' in issue for issue in result['issues']))

    def test_manual_preview_and_assets_share_visual_adoption_after_text(self):
        self.f.fixture(('shots',))
        products = self.f.manifests['V001']['workflow']['products']
        products.pop('assets')
        self.f.save_video('V001'); self.f.save(); self.approve_stories()
        result = workflow.check(self.root, 'video-assets', video_id='V001')
        self.assertTrue(result['allowed'], result)
        state.record_approval(self.root, dict(targets=list(products['preview']['files'].values()),
            decision='rejected', user_evidence='Synthetic actual preview rejection'))
        self.assertFalse(workflow.check(self.root, 'video-assets', video_id='V001')['allowed'])

    def test_shots_current_voice_needs_adoption_for_prompts_and_upload(self):
        import test_workflow
        f = test_workflow.WorkflowTests('runTest'); f.setUp()
        f.data = enable_modules(f.root, ['video'])
        f.video(products=['script', 'voice', 'preview', 'assets', 'director', 'storyboard', 'style', 'prompts'])
        path = f.root / f.data['videos']['V001']['path']
        manifest = state.read_json(path)
        manifest['workflow']['products']['voice'].pop('approval')
        state.write_json(path, manifest)
        f.data['videos']['V001']['sha256'] = state.sha256(path)
        for step in ('video-prompts', 'video-upload'):
            self.assertFalse(f.allowed(step, video_id='V001'))

    def test_v2_story_group_exists_before_any_visual_and_reuses_actual_approval(self):
        self.f.fixture(('shots', 'talking'))
        self.f.start(review_policy='grouped_creative_v2')
        current = grouped_gates.snapshot(self.root, 'video-story')
        self.assertEqual(current['issues'], [])
        self.assertEqual(len(current['targets']), 4)
        self.assertFalse(grouped_gates.adopted(self.root, 'video-story')['approved'])
        self.approve_stories()
        self.assertTrue(grouped_gates.adopted(self.root, 'video-story')['approved'])

    def test_text_only_script_queue_does_not_need_image_authorization(self):
        self.f.fixture()
        self.f.start(tasks=[dict(id='write-story', step='video-script', video_id='V001',
            inputs=['planning/blueprint.md'], outputs=['script'], instruction='Write the actual full story')])
        action = autopilot.next_task(self.root, 'synthetic-author')
        self.assertEqual(action['action'], 'produce', action)
        self.assertFalse(action['external_submission_guard'])

    def test_old_script_queue_with_images_cannot_skip_story_approval(self):
        self.f.fixture()
        self.f.start(preferences={'image': dict(route='builtin', evidence='Synthetic route',
            authorization=dict(scope='run', purposes=['asset'], paid_generation=False,
                scope_evidence='Synthetic requested story preview'))},
            tasks=[dict(id='old-preview', step='video-script', video_id='V001', image_count=1,
                inputs=['planning/blueprint.md'], outputs=['preview'], instruction='Make an actual preview')])
        action = autopilot.next_task(self.root, 'synthetic-maker')
        self.assertEqual(action['action'], 'waiting', action)
        self.assertTrue(any('story' in issue or 'script' in issue for item in action['blocked']
                            for issue in item['issues']))

    def test_submitted_api_results_remain_recoverable_without_new_generation(self):
        for status in ('running', 'result_ready', 'download_failed', 'submission_unknown'):
            with self.subTest(status=status):
                self.setUp()
                self.image_setup('openai_image_api')
                self.approve_stories()
                batch = self.f.prepare_image()
                path = state.resolve(self.root, batch['jobs'][0])
                job = state.read_json(path)
                job.pop('story_basis', None)  # A genuinely pre-policy submitted job has no new binding.
                job.update(status=status, task_id='provider-test-id',
                           provider_image_url='https://example.com/synthetic.png')
                state.write_json(path, job)
                self.reject_story()
                transport = Transport()
                result = image_api.run_job(self.root, batch['jobs'][0], transport,
                    resume=True, timeout=1, poll_interval=0)
                self.assertEqual(result['status'], 'submission_unknown' if status == 'submission_unknown' else 'downloaded')
                self.assertFalse(any(endpoint == image_api.ENDPOINT for endpoint, _ in transport.posts))

    def test_independent_asset_module_does_not_need_unrelated_story(self):
        self.f.fixture()
        enable_modules(self.root, ['plan'])
        self.assertTrue(workflow.check(self.root, 'asset')['allowed'])

    def test_newly_adopted_replacement_text_does_not_reauthorize_old_pending_prompt(self):
        self.image_setup('openai_image_api')
        self.approve_stories()
        batch = self.f.prepare_image()
        products = self.f.manifests['V001']['workflow']['products']
        products['script'] = self.f.record('V001-revised-script', complete=True,
            sources=self.f.versions(self.f.data['stages']['blueprint']), asset_ids=['CHAR1', 'SCENE1', 'PROP1'])
        products['voice'] = self.f.record('V001-revised-voice', verbatim=True,
            sources=self.f.versions(products['script']))
        self.f.save_video('V001'); self.f.save()
        self.approve_stories()
        transport = Transport()
        with self.assertRaisesRegex(ValueError, 'story|script'):
            image_api.run_job(self.root, batch['jobs'][0], transport, timeout=1, poll_interval=0)
        self.assertEqual(transport.posts, [])

    def test_complete_text_flags_and_current_source_binding_are_required(self):
        for issue in ('complete', 'verbatim', 'voice-binding', 'other-video'):
            with self.subTest(issue=issue):
                self.setUp(); self.image_setup(); self.approve_stories()
                products = self.f.manifests['V002']['workflow']['products']
                if issue == 'complete': products['script']['complete'] = False
                elif issue == 'verbatim': products['voice']['verbatim'] = False
                elif issue == 'voice-binding': products['voice']['source_versions'] = {}
                else: products.pop('voice')
                self.f.save_video('V002'); self.f.save()
                with self.assertRaisesRegex(ValueError, 'script|voice'):
                    self.f.prepare_image()

    def test_reused_story_adoption_does_not_create_new_human_occurrence(self):
        self.f.fixture(); self.f.start(review_policy='grouped_creative_v2')
        self.approve_stories()
        task = self.f.group_task('video-story')
        autopilot.extend(self.root, [task], 'Synthetic add story task after already adopting full text')
        decisions = state.resolve(self.root, '_state/decisions.jsonl').read_bytes()
        action = autopilot.next_task(self.root, 'host')
        self.assertEqual(action['human_tasks'], [])
        current = next(t for t in store.load_run(self.root)['tasks'] if t['spec']['id'] == 'video-story')
        self.assertEqual(current['status'], 'done')
        self.assertNotIn('claim', current)
        self.assertTrue(current['reused_adoption'])
        self.assertEqual(state.resolve(self.root, '_state/decisions.jsonl').read_bytes(), decisions)
        self.reject_story()
        current = next(t for t in autopilot.status(self.root)['tasks'] if t['spec']['id'] == 'video-story')
        self.assertEqual(current['status'], 'stale')

    def test_unadopted_story_dispatches_once_and_actual_receipt_completes_it(self):
        self.f.fixture(); self.f.start(review_policy='grouped_creative_v2')
        snap = self.f.snapshot('video-story')
        packet = self.f.independent(snap)
        autopilot.extend(self.root, [self.f.group_task('video-story', packet)], 'Synthetic actual story review')
        first = autopilot.next_task(self.root, 'host')['human_tasks'][0]
        second = autopilot.next_task(self.root, 'host')['human_tasks'][0]
        self.assertEqual(first['claim'], second['claim'])
        decision = self.f.approve('video-story')
        result = autopilot.record(self.root, self.f.group_receipt(first, decision))
        self.assertEqual(result['status'], 'done')

    def test_v2_visual_targets_exclude_already_adopted_text(self):
        self.f.fixture(('talking',)); self.f.start(review_policy='grouped_creative_v2')
        self.approve_stories()
        story = self.f.snapshot('video-story')
        visual = self.f.snapshot('video-creative')
        self.assertEqual(visual['issues'], [])
        self.assertFalse({r['path'] for r in story['targets']} & {r['path'] for r in visual['targets']})
        self.assertTrue(all(visual['source_versions'].get(r['path']) == r['sha256'] for r in story['targets']))
        self.f.approve('video-creative')
        self.assertTrue(workflow.check(self.root, 'pages')['allowed'])

    def test_v1_snapshot_identity_matches_unchanged_historical_implementation(self):
        self.f.fixture(); self.f.start()
        source = subprocess.run(['git', 'show', 'HEAD:skills/math-courseware-studio/scripts/runtime/grouped_gates.py'],
            cwd=group_fixtures.ROOT, capture_output=True, check=True).stdout.decode('utf-8')
        previous = types.ModuleType('runtime.historical_grouped_gates')
        previous.__package__ = 'runtime'
        exec(compile(source, '<historical-grouped-gates>', 'exec'), previous.__dict__)
        self.assertEqual(previous.snapshot(self.root, 'video-creative'), self.f.snapshot())

    def test_legacy_approval_without_decision_id_still_counts_as_actual_adoption(self):
        self.image_setup()
        targets = [item for video in self.f.manifests.values() for name in ('script', 'voice')
                   for item in video['workflow']['products'][name]['files'].values()]
        state.append_line(state.resolve(self.root, '_state/decisions.jsonl'), dict(targets=targets,
            decision='approved', user_evidence='Synthetic actual legacy full text approval'))
        self.assertTrue(self.f.prepare_image()['jobs'])

    def test_old_pending_without_story_basis_is_preserved_but_not_newly_submitted(self):
        self.image_setup('openai_image_api'); self.approve_stories()
        batch = self.f.prepare_image()
        path = state.resolve(self.root, batch['jobs'][0])
        job = state.read_json(path)
        job.pop('story_basis')
        state.write_json(path, job)
        before = path.read_bytes()
        transport = Transport()
        with self.assertRaisesRegex(ValueError, 'story'):
            image_api.run_job(self.root, batch['jobs'][0], transport, timeout=1, poll_interval=0)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(transport.posts, [])

    def test_v2_story_group_needs_no_preview_asset_or_director(self):
        self.f.fixture(('shots', 'talking'))
        for vid, manifest in self.f.manifests.items():
            manifest['workflow'] = {'products': {key: value for key, value in manifest['workflow']['products'].items()
                                                if key in ('script', 'voice')}}
            self.f.save_video(vid)
        self.f.data['stages'].pop('shared-assets'); self.f.save()
        self.f.start(review_policy='grouped_creative_v2')
        self.assertEqual(self.f.snapshot('video-story')['issues'], [])
        self.assertTrue(self.f.snapshot()['issues'])

    def test_independent_talking_text_requires_adoption_without_full_course_or_run(self):
        self.f.fixture(('talking',))
        videos = self.f.data['videos']
        self.f.data = enable_modules(self.root, ['video'])
        self.f.data['videos'] = videos
        self.f.save()
        self.assertFalse(workflow.check(self.root, 'video-assets', video_id='V001')['allowed'])
        self.approve_stories()
        self.assertTrue(workflow.check(self.root, 'video-assets', video_id='V001')['allowed'])

    def test_v2_adopted_story_allows_actual_image_preparation_before_visual_adoption(self):
        self.f.fixture(('talking',))
        state.record_approval(self.root, dict(targets=[self.f.ref(path) for path in
            ('_state/math.json', '_state/story.json')], user_evidence='Synthetic adopted teaching core'))
        self.f.start(review_policy='grouped_creative_v2', preferences={'image': dict(route='builtin',
            evidence='Synthetic actual image route', authorization=dict(scope='run', purposes=['asset'],
                paid_generation=False, scope_evidence='Synthetic actual asset generation choice'))})
        self.f.approve('video-story')
        batch = self.f.prepare_image()
        job = state.read_json(state.resolve(self.root, batch['jobs'][0]))
        self.assertEqual(job['creative_candidate']['policy'], 'grouped_creative_v2')
        self.assertTrue(job['story_basis'])
        self.assertFalse(grouped_gates.adopted(self.root, 'video-creative')['approved'])


if __name__ == '__main__':
    unittest.main()
