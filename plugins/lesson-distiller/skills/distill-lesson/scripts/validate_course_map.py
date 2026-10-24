"""Require a full PDF page map and accepted lesson bundles before a course release.

This verifies declared coverage, not whether page classifications are truthful.
"""
import argparse
from pathlib import Path
import sys

from study_pack import PackError, field, file_hash, load_json, obj, require, seq, validate_bundle


CONTENT = {'lesson', 'module', 'partner', 'reference', 'appendix'}
EXCLUDED = {'front_matter', 'duplicate', 'source_only'}


def validate_course(path, source, page_count=None):
    path, source = Path(path), Path(source)
    course, _ = load_json(path)
    require(course['lesson_id'] == 'COURSE', 'Course map lesson_id must be COURSE')
    require(field(course, 'source_sha256', 'course') == file_hash(source), 'Course source hash mismatch')
    if page_count is None:
        try:
            import pymupdf
        except ImportError as error:
            raise PackError('Full PDF page-count verification requires pymupdf') from error
        with pymupdf.open(source) as pdf:
            page_count = pdf.page_count
    require(type(course.get('page_count')) is int and course['page_count'] == page_count,
            'Course page_count does not match actual PDF')
    bundles = {}
    for entry in seq(course.get('bundles'), 'course.bundles', 1):
        obj(entry, 'bundle')
        bid = field(entry, 'id', 'bundle')
        require(bid not in bundles, 'Duplicate course bundle ID')
        paths = {name: path.parent / field(entry, name, bid) for name in ('inventory', 'lesson', 'review', 'sheet')}
        bundle = validate_bundle(paths['inventory'], paths['lesson'], paths['review'], source)
        require(bundle.lesson['lesson_id'] == bid, f'{bid}: bundle ID mismatch')
        require(bundle.reviewed and bundle.source_verified, f'{bid}: source/language review incomplete')
        require(paths['sheet'].is_file(), f'{bid}: rendered sheet missing')
        rendered = paths['sheet'].read_text(encoding='utf-8')
        require('<meta name="study-pack-status" content="reviewed">' in rendered, f'{bid}: sheet is not reviewed')
        # Match actual bytes to renderer output, preventing stale or hand-edited
        # sheets from borrowing the review of newer/different lesson data.
        from study_pack import render_html
        require(rendered == render_html(bundle), f'{bid}: sheet differs from reviewed data/template')
        bundles[bid] = bundle
    pages = seq(course.get('pages'), 'course.pages', page_count)
    require(len(pages) == page_count, 'Every PDF page must occur exactly once')
    seen, referenced = set(), set()
    for page in pages:
        obj(page, 'course page')
        index = page.get('pdf_index')
        require(type(index) is int and 0 <= index < page_count and index not in seen,
                'Invalid or duplicate course page index')
        seen.add(index)
        field(page, 'folio', f'PDF {index}')
        require(page.get('status') == 'reviewed', f'PDF {index}: page classification not reviewed')
        category = page.get('category')
        require(isinstance(category, str) and category in CONTENT | EXCLUDED, f'PDF {index}: unknown category')
        if category in CONTENT:
            destination = field(page, 'destination', f'PDF {index}')
            require(destination in bundles, f'PDF {index}: destination bundle missing')
            require(index in bundles[destination].inventory['scope_pages'], f'PDF {index}: destination does not cover this page')
            referenced.add(destination)
        else:
            field(page, 'reason', f'PDF {index}')
            if category == 'duplicate':
                duplicate = page.get('duplicate_of')
                require(type(duplicate) is int and 0 <= duplicate < page_count and duplicate != index,
                        f'PDF {index}: invalid duplicate destination')
    require(seen == set(range(page_count)), 'Unassigned PDF pages remain')
    page_by_index = {page['pdf_index']: page for page in pages}
    for page in pages:
        current, visited = page, set()
        while current['category'] == 'duplicate':
            require(current['pdf_index'] not in visited, 'Duplicate-page cycle')
            visited.add(current['pdf_index'])
            current = page_by_index[current['duplicate_of']]
    require(referenced == set(bundles), 'Course bundle has no page destination')
    return len(pages), len(bundles)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('course_map', type=Path)
    parser.add_argument('--source', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        pages, bundles = validate_course(args.course_map, args.source)
        print(f'DECLARED COURSE MAP PASS: {pages} PDF pages assigned; {bundles} current reviewed bundles.')
        print('LIMIT: source review must still verify classification, exclusions and missing media. This is not exam certification.')
        return 0
    except (PackError, OSError, RuntimeError) as error:
        print(f'FAIL: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
