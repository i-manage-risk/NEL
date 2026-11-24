#!/usr/bin/env python3
"""Retry stale page sources independently, publishing successful data each round."""
import argparse,json,os,signal,subprocess,sys,time
from datetime import datetime,date,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.run_after_close import scheduled_close,NY_TZ,next_session_date
from cot_release_dates import publication_date
ROOT=Path(__file__).resolve().parents[1]
STOCK_STAGES={'Liquid Leadership','NEL','KK','OSB','Top D','Superliquid','ETF studies'}

def read(path,root=ROOT):
 try:return json.loads((root/path).read_text())
 except (OSError,ValueError):return {}
def latest(rows):return max((r.get('date','') for r in rows),default='')
def cot_expected(now):
 for offset in range(22):
  day=now.date()-timedelta(days=offset)
  if day.weekday()==1 and publication_date(day.isoformat())[0]<=now.date().isoformat():return day.isoformat()
 return ''
def freshness(close,now,root=ROOT):
 target=close.isoformat();stamp=next_session_date(datetime.combine(close,datetime.min.time(),NY_TZ)).isoformat()
 state=read('outputs/.scan-state.json',root)
 stock_ok=state.get('close')==target and STOCK_STAGES.issubset(state.get('completed',[]))
 required=[f'outputs/{prefix}_{stamp}.{suffix}' for prefix,suffix in [('non_extended_leaders','csv'),('kk_liquid_leaders','csv'),('obc_candidates','csv'),('top_d','json'),('super_liquid_non_extended_leaders','csv')]]
 stock_ok=stock_ok and all((root/p).exists() for p in required)
 ll=read('outputs/liquid_leadership.json',root);ll_date=latest(ll.get('snapshots',[]))
 studies=[latest(read(f'outputs/etf/{kind}_snapshots.json',root).get('snapshots',[])) for kind in ['themes','sectors']]
 stock_ok=stock_ok and ll_date>=target and all(d>=target for d in studies)
 flow=read('outputs/flow_market.json',root)
 dates=[latest(flow.get('series',{}).get(s,{}).get('history',[])) for s in ['SPY','QQQ','IWM','DIA','RSP','QQQE','SPMO','TLT']]
 indexes=read('outputs/index_history.json',root);index_dates=[latest(indexes.get(s,{}).get('history',[])) for s in ['spx','nasdaq','russell','dow']]
 breadth=read('outputs/breadth_market_monitor.json',root);breadth_date=latest(breadth if isinstance(breadth,list) else [])
 cot=read('outputs/positioning.json',root);markets=cot.get('markets',[]);cot_date=min((latest(m.get('history',[])) for m in markets),default='');expected=cot_expected(now)
 calendar=read('outputs/workspace_calendar.json',root);calendar_date=max((s.get('closeDate','') for s in calendar.get('snapshots',[])),default='')
 debrief=read('outputs/debrief_data.json',root);debrief_rows=debrief.get('market',{}).get('series',{}).get('RSP',{}).get('history',[]);debrief_date=latest(debrief_rows)
 return {'debrief':{'current':debrief_date>=target,'asof':debrief_date,'target':target},'stocks':{'current':bool(stock_ok),'asof':state.get('close'),'target':target},'flow':{'current':all(d>=target for d in dates),'asof':min(dates),'target':target},'indexes':{'current':all(d>=target for d in index_dates),'asof':min(index_dates),'target':target},'breadth':{'current':breadth_date>=target,'asof':breadth_date,'target':target},'positioning':{'current':len(markets)==10 and cot_date>=expected,'asof':cot_date,'target':expected},'workspace':{'current':calendar_date>=target,'asof':calendar_date,'target':target}}

def command(args,timeout=600):
 print('Running:',*args,flush=True)
 process=subprocess.Popen(args,cwd=ROOT,start_new_session=True)
 try:return process.wait(timeout=timeout)==0
 except subprocess.TimeoutExpired:
  os.killpg(process.pid,signal.SIGTERM)
  try:process.wait(timeout=10)
  except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
  if any('run_after_close.py' in str(arg) for arg in args):
   try:(ROOT/'.daily_scan.lock').rmdir()
   except OSError:pass
  print('Timed out; other sources continue.',flush=True);return False

def publish():
 # Existing repository-write / Pages permissions; no new credential scopes.
 subprocess.run(['git','config','user.name','github-actions[bot]'],cwd=ROOT,check=True,timeout=120)
 subprocess.run(['git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com'],cwd=ROOT,check=True,timeout=120)
 paths=['outputs','industry_flow_dashboard.html','index.html','super-liquid.html','themes.html','sectors.html','breadth.html','data/etf_holdings_cache.json']
 subprocess.run(['git','add',*paths],cwd=ROOT,check=True,timeout=120)
 if subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode==0:return
 subprocess.run(['git','commit','-m','Refresh completed page sources'],cwd=ROOT,check=True,timeout=120)
 for attempt in range(3):
  try:subprocess.run(['git','pull','--rebase','origin','main'],cwd=ROOT,check=True,timeout=120)
  except subprocess.CalledProcessError:
   subprocess.run(['git','rebase','--abort'],cwd=ROOT,timeout=30)
   raise RuntimeError('Concurrent data changed. Preserving remote history; next five-minute run starts from latest main.')
  if subprocess.run(['git','push','origin','main'],cwd=ROOT,timeout=120).returncode==0:break
 else:raise RuntimeError('Unable to publish refreshed data')
 command(['gh','api','--method','POST',f'repos/{os.environ["GITHUB_REPOSITORY"]}/pages/builds'],60)

def repair_stock_checkpoint(close,root=ROOT):
 path=root/'outputs/.scan-state.json';state=read('outputs/.scan-state.json',root)
 if state.get('close')!=str(close):return
 stamp=next_session_date(datetime.combine(close,datetime.min.time(),NY_TZ)).isoformat()
 outputs={'NEL':f'non_extended_leaders_{stamp}.csv','KK':f'kk_liquid_leaders_{stamp}.csv','OSB':f'obc_candidates_{stamp}.csv','Top D':f'top_d_{stamp}.json','Superliquid':f'super_liquid_non_extended_leaders_{stamp}.csv'}
 valid={key for key,file in outputs.items() if (root/'outputs'/file).exists()}
 if latest(read('outputs/liquid_leadership.json',root).get('snapshots',[]))>=str(close):valid.add('Liquid Leadership')
 if all(latest(read(f'outputs/etf/{kind}_snapshots.json',root).get('snapshots',[]))>=str(close) for kind in ['themes','sectors']):valid.add('ETF studies')
 state['completed']=[name for name in state.get('completed',[]) if name in valid]
 path.write_text(json.dumps(state))

def run_round(close,now,root=ROOT,run=command):
 before=freshness(close,now,root);errors=[]
 if not before['stocks']['current']:repair_stock_checkpoint(close,root)
 scripts={'stocks':'scripts/run_after_close.py','breadth':'breadth_dashboard.py','indexes':'index_history.py','flow':'flow_market_data.py','positioning':'positioning.py'}
 for key,script in scripts.items():
  if not before[key]['current'] and not run([sys.executable,'-u',script],timeout=900 if key=='stocks' else 300):errors.append(key)
 after=freshness(close,now,root)
 if not before['stocks']['current'] or not after['workspace']['current']:
  if not run([sys.executable,'workspace_data.py']):errors.append('workspace')
 if any(not before[key]['current'] for key in ('debrief','flow','breadth','positioning','workspace')):
  if not run([sys.executable,'scripts/build_debrief_data.py']):errors.append('debrief')
 return freshness(close,now,root),errors

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--watch-minutes',type=int,default=0);parser.add_argument('--publish',action='store_true');parser.add_argument('--check',action='store_true');args=parser.parse_args()
 now=datetime.now(NY_TZ);close=scheduled_close(now)
 if close is None:print('Pre-close/intraday: no closing scan performed.');return 0
 if args.check:
  states=freshness(close,now);print(json.dumps(states));return int(not all(s['current'] for s in states.values()))
 deadline=time.monotonic()+args.watch_minutes*60
 while True:
  started=time.monotonic();states,errors=run_round(close,datetime.now(NY_TZ))
  status={'checkedAt':datetime.now(timezone.utc).isoformat(),'close':str(close),'sources':states,'errors':errors,'complete':not errors and all(s['current'] for s in states.values())}
  print(json.dumps(status,indent=2),flush=True)
  (ROOT/'outputs/refresh_status.json').write_text(json.dumps(status,separators=(',',':')))
  summary=os.environ.get('GITHUB_STEP_SUMMARY')
  if summary:
   with open(summary,'a') as out:
    out.write('\n| Source | Available | Required | Current |\n|---|---|---|---|\n'+''.join(f"| {key} | {value['asof']} | {value['target']} | {value['current']} |\n" for key,value in states.items()))
  if args.publish:
   publish()
   status['complete']=not errors and all(s['current'] for s in freshness(close,datetime.now(NY_TZ)).values())
  if status['complete']:return 0
  if time.monotonic()+300>=deadline:return 1
  # Don't run closing stock scans after the pre-market safety window opens.
  if scheduled_close(datetime.now(NY_TZ))!=close:return 1
  time.sleep(max(1,300-(time.monotonic()-started)))

if __name__=='__main__':sys.exit(main())
