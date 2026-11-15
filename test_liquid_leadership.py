import unittest
import pandas as pd
from liquid_leadership import select_leaders,PERIODS
class LiquidLeadershipTests(unittest.TestCase):
 def test_liquidity_before_exact_window_ranking(self):
  rows=[]
  for i in range(101):
   r={'name':f'S{i:03}','SMA30':100,'average_volume_30d_calc':2e6,'average_volume_10d_calc':2e6}
   r.update({c:i for c in PERIODS.values()});rows.append(r)
  rows.append({**rows[0],'name':'THIN','SMA30':1,**{c:10000 for c in PERIODS.values()}})
  rows.append({**rows[0],'name':'BOUNDARY','average_volume_10d_calc':1e6,**{c:10000 for c in PERIODS.values()}})
  rows[100]['Perf.10Y']=None
  universe,leaders,counts=select_leaders(pd.DataFrame(rows))
  self.assertEqual(len(universe),101)
  self.assertEqual(leaders['1m'],['S100','S099','S098'])
  self.assertEqual(leaders['10y'],['S099','S098'])
  self.assertEqual(counts['10y']['eligible'],100)
 def test_ties_are_deterministic_and_null_windows_stay_missing(self):
  r={'name':'B','SMA30':100,'average_volume_30d_calc':2e6,'average_volume_10d_calc':2e6,**{c:5 for c in PERIODS.values()}}
  a={**r,'name':'A'};r['Perf.All']=None;a['Perf.All']=None
  _,leaders,counts=select_leaders(pd.DataFrame([r,a]))
  self.assertEqual(leaders['1d'],['A']);self.assertEqual(leaders['all'],[])
if __name__=='__main__':unittest.main()
