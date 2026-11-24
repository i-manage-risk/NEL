import json,tempfile,unittest
from pathlib import Path
from datetime import datetime,date
from scripts.refresh_pages import freshness,run_round,cot_expected,NY_TZ,STOCK_STAGES
class PageRefreshTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.close=date(2026,11,20);self.now=datetime(2026,11,20,18,tzinfo=NY_TZ)
  self.write('outputs/.scan-state.json',{'close':'2026-11-20','completed':list(STOCK_STAGES)})
  for prefix,suffix in [('non_extended_leaders','csv'),('kk_liquid_leaders','csv'),('obc_candidates','csv'),('top_d','json'),('super_liquid_non_extended_leaders','csv')]:
   p=self.root/f'outputs/{prefix}_2026-11-23.{suffix}';p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}')
  self.write('outputs/liquid_leadership.json',{'snapshots':[{'date':'2026-11-20'}]})
  for k in ['themes','sectors']:self.write(f'outputs/etf/{k}_snapshots.json',{'snapshots':[{'date':'2026-11-20'}]})
  self.write('outputs/flow_market.json',{'series':{s:{'history':[{'date':'2026-11-20'}]} for s in ['SPY','QQQ','IWM','DIA','RSP','QQQE','SPMO','TLT']}})
  self.write('outputs/index_history.json',{s:{'history':[{'date':'2026-11-20'}]} for s in ['spx','nasdaq','russell','dow']})
  self.write('outputs/breadth_market_monitor.json',[{'date':'2026-11-20'}])
  self.write('outputs/debrief_data.json',{'market':{'series':{'RSP':{'history':[{'date':'2026-11-20'}]}}}})
  self.write('outputs/positioning.json',{'markets':[{'history':[{'date':'2026-11-17'}]} for _ in range(10)]})
  self.write('outputs/workspace_calendar.json',{'snapshots':[{'closeDate':'2026-11-20'}]})
 def tearDown(self):self.tmp.cleanup()
 def write(self,p,d):
  p=self.root/p;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d))
 def test_current_pages_skip_all_sources(self):
  calls=[];states,errors=run_round(self.close,self.now,self.root,lambda args,**kw:calls.append(args) or True)
  self.assertTrue(all(s['current'] for s in states.values()));self.assertEqual(calls,[]);self.assertEqual(errors,[])
 def test_stale_sources_retry_independently_and_failed_one_does_not_block(self):
  self.write('outputs/breadth_market_monitor.json',[{'date':'2026-11-19'}]);self.write('outputs/positioning.json',{'markets':[]});calls=[]
  def run(args,**kw):calls.append(args[-1]);return args[-1]!='breadth_dashboard.py'
  states,errors=run_round(self.close,self.now,self.root,run)
  self.assertEqual(calls,['breadth_dashboard.py','positioning.py','scripts/build_debrief_data.py']);self.assertEqual(errors,['breadth']);self.assertFalse(states['breadth']['current'])
 def test_missing_stock_file_is_not_reported_current(self):
  (self.root/'outputs/kk_liquid_leaders_2026-11-23.csv').unlink();self.assertFalse(freshness(self.close,self.now,self.root)['stocks']['current'])
 def test_holiday_release_is_due_monday_not_friday(self):
  self.assertEqual(cot_expected(datetime(2026,11,13,18,tzinfo=NY_TZ)),'2026-11-03')
  self.assertEqual(cot_expected(datetime(2026,11,16,18,tzinfo=NY_TZ)),'2026-11-10')
if __name__=='__main__':unittest.main()
