import unittest
import numpy as np
import pandas as pd
from top_d import character_metrics, rank_records


def bars(values, index):
    values=np.asarray(values,dtype=float)
    return pd.DataFrame({'Open':values,'High':values*1.01,'Low':values*.99,'Close':values,'Volume':1e6},index=index)

class TopDTests(unittest.TestCase):
    def setUp(self):
        self.index=pd.bdate_range('2024-01-01',periods=400)
        self.close=self.index[-1].date().isoformat()
        self.rsp=bars(100*np.exp(np.arange(400)*.001),self.index)
    def test_smooth_trend_and_scale_invariance(self):
        h=bars(100*np.exp(np.arange(400)*.015),self.index)
        a=character_metrics(h,self.rsp,self.close)
        b=character_metrics(h*2,self.rsp,self.close)
        self.assertAlmostEqual(a['smoothness'],100)
        self.assertEqual(a['character'],'Smooth trender')
        self.assertEqual(a['respect10'],100)
        self.assertEqual(a['breaks10'],0)
        self.assertAlmostEqual(a['best20d'],100*(np.exp(.3)-1))
        self.assertAlmostEqual(a['best20d'],b['best20d'])
        self.assertEqual(a['upBeatRate'],100)
        self.assertGreater(a['upReturn'],0)
    def test_whipsaw_is_less_efficient(self):
        trend=100*np.exp(np.arange(400)*.015)
        smooth=character_metrics(bars(trend,self.index),self.rsp,self.close)
        noisy=character_metrics(bars(trend*np.exp(.10*np.sin(np.arange(400)*2)),self.index),self.rsp,self.close)
        self.assertLess(noisy['smoothness'],smooth['smoothness'])
        self.assertGreater(noisy['breaks10'],smooth['breaks10'])
    def test_future_bars_do_not_change_metrics(self):
        h=bars(100*np.exp(np.arange(400)*.015),self.index)
        expected=character_metrics(h,self.rsp,self.close)
        future=pd.bdate_range(self.index[-1]+pd.Timedelta(days=1),periods=30)
        actual=character_metrics(pd.concat([h,bars([1]*30,future)]),pd.concat([self.rsp,bars([10000]*30,future)]),self.close)
        self.assertEqual(actual,expected)
    def test_stale_or_short_history_is_not_silently_used(self):
        with self.assertRaises(ValueError):character_metrics(self.rsp.iloc[:-1],self.rsp,self.close)
        with self.assertRaises(ValueError):character_metrics(self.rsp.iloc[-40:],self.rsp,self.close)
    def test_rank_is_deterministic_and_missing_evidence_not_zero(self):
        rows=[dict(symbol='B',best20d=40,smoothness=20,upReturn=1,upBeatRate=50,respect=60),dict(symbol='A',best20d=80,smoothness=80,upReturn=4,upBeatRate=80,respect=90),dict(symbol='NEW',best20d=90,smoothness=90,upReturn=None,upBeatRate=None,respect=90)]
        ranked=rank_records(rows)
        self.assertEqual(ranked[0]['symbol'],'A')
        self.assertEqual(ranked[-1]['symbol'],'NEW')
        self.assertIsNone(ranked[-1]['score'])
if __name__=='__main__':unittest.main()
