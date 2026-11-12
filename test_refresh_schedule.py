import unittest
from datetime import datetime, date
from scripts.run_after_close import scheduled_close, next_session_date, NY_TZ
class RefreshScheduleTests(unittest.TestCase):
    def at(self,s):return datetime.fromisoformat(s).replace(tzinfo=NY_TZ)
    def test_close_and_overnight_are_same_session(self):
        self.assertEqual(scheduled_close(self.at('2026-11-11T16:25')),date(2026,11,11))
        self.assertEqual(scheduled_close(self.at('2026-11-12T02:00')),date(2026,11,11))
        self.assertEqual(scheduled_close(self.at('2026-11-12T08:15')),date(2026,11,11))
    def test_intraday_is_blocked(self):
        for time in ['09:00','09:30','12:00','16:00','16:24']:
            self.assertIsNone(scheduled_close(self.at('2026-11-12T'+time)))
    def test_weekend_holiday_and_dst(self):
        self.assertEqual(scheduled_close(self.at('2026-11-16T08:00')),date(2026,11,13))
        self.assertEqual(scheduled_close(self.at('2026-11-27T08:00')),date(2026,11,25))
        self.assertEqual(scheduled_close(self.at('2026-07-09T16:25')),date(2026,7,9))
        self.assertEqual(next_session_date(self.at('2026-11-13T16:25')),date(2026,11,16))
if __name__=='__main__':unittest.main()

class RefreshResumeTests(unittest.TestCase):
    def test_failed_stage_does_not_block_other_sources_and_retry_resumes(self):
        import io, json, tempfile
        from contextlib import redirect_stdout
        from pathlib import Path
        from unittest.mock import patch
        from scripts import run_after_close as runner
        attempts={}; fail=True
        class Process:
            def __init__(self,command,**kwargs):
                self.script=command[2];attempts[self.script]=attempts.get(self.script,0)+1
                self.stdout=iter(['test stage output\n'])
            def wait(self):return 1 if self.script=='obc_scan.py' and fail else 0
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with patch.multiple(runner,PROJECT_DIR=root,LOG_DIR=root/'logs',MARKER=root/'outputs'/'.last_scheduled_run.txt',LOCK_DIR=root/'.lock'),patch.object(runner,'scheduled_close',return_value=date(2026,11,11)),patch.object(runner.subprocess,'Popen',Process),patch.object(runner.time,'sleep'),redirect_stdout(io.StringIO()):
                self.assertEqual(runner.main(),1)
                state=json.loads((root/'outputs'/'.scan-state.json').read_text())
                self.assertEqual(state['failed'],['OSB'])
                self.assertIn('ETF studies',state['completed'])
                self.assertEqual(attempts['obc_scan.py'],2)
                self.assertFalse(runner.MARKER.exists())
                fail=False
                self.assertEqual(runner.main(),0)
                self.assertEqual(attempts['obc_scan.py'],3)
                self.assertEqual(attempts['focus_list.py'],1)
                self.assertEqual(runner.MARKER.read_text().strip(),'2026-11-11')
