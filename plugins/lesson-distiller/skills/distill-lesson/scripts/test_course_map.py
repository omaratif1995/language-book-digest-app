"""Full-book regressions: lesson-only batches cannot claim all PDF pages."""
import json
import unittest

import test_study_pack as fixtures
import study_pack as pack
import validate_course_map as course


class CourseMapTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.StudyPackTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.bundle = self.fixture.bundle()
        self.sheet = self.fixture.root / 'L01_Studysheet_v1.html'
        self.sheet.write_text(pack.render_html(self.bundle), encoding='utf-8')
        self.path = self.fixture.root / 'Course_Map_v1.json'
        self.data = {'schema_version': 2, 'lesson_id': 'COURSE', 'source_sha256': pack.file_hash(self.fixture.source),
                     'page_count': 2, 'bundles': [{'id': 'L12', 'inventory': self.fixture.inventory_path.name,
                       'lesson': self.fixture.lesson_path.name, 'review': self.fixture.review_path.name, 'sheet': self.sheet.name}],
                     'pages': [{'pdf_index': 0, 'folio': '1', 'category': 'lesson', 'status': 'reviewed', 'destination': 'L12'},
                               {'pdf_index': 1, 'folio': '2', 'category': 'front_matter', 'status': 'reviewed', 'reason': 'Synthetic publisher credits'}]}

    def run_map(self):
        self.path.write_text(json.dumps(self.data), encoding='utf-8')
        return course.validate_course(self.path, self.fixture.source, page_count=2)

    def test_all_pages_declared(self):
        self.assertEqual(self.run_map(), (2, 1))

    def test_unassigned_module_page_fails(self):
        self.data['pages'].pop()
        with self.assertRaises(pack.PackError):
            self.run_map()

    def test_module_cannot_claim_uncovered_lesson_home(self):
        self.data['pages'][1].update(category='module', destination='L12')
        with self.assertRaisesRegex(pack.PackError, 'does not cover'):
            self.run_map()

    def test_stale_or_modified_sheet_fails(self):
        self.sheet.write_text(self.sheet.read_text(encoding='utf-8').replace('Betriebsausflug', 'the missing example'), encoding='utf-8')
        with self.assertRaisesRegex(pack.PackError, 'differs'):
            self.run_map()

    def test_pending_page_fails(self):
        self.data['pages'][1]['status'] = 'pending'
        with self.assertRaisesRegex(pack.PackError, 'not reviewed'):
            self.run_map()


if __name__ == '__main__':
    unittest.main()
