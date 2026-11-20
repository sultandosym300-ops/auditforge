import unittest

from auditforge.env import Session


class CursorCoverageTests(unittest.TestCase):
    def test_pages_cover_every_ledger_row_once_in_storage_order(self):
        session = Session()
        session.reset(308014, {}, 'evaluation')
        seen = []
        cursor = None
        for _ in range(100):
            observation, _, _, truncated, _ = session.step(
                dict(tool='list_records', table='ledger', limit=17, cursor=cursor)
            )
            self.assertFalse(truncated)
            page = observation['result']
            seen.extend(row['row_id'] for row in page['records'])
            cursor = page['next_cursor']
            if cursor is None:
                break
        self.assertIsNone(cursor)
        self.assertEqual(seen, [row['row_id'] for row in session.public['ledger']])
