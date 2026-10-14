#!/usr/bin/env python3
"""Evaluate one-step GOLD-HISTORY tool decisions for the real ToolTalk dataset.
Not the ToolTalk official evaluator; does not execute APIs or assess DB state.
"""
import argparse
import json
import os
from collections import defaultdict
from pathlib import Path
from time import monotonic

from eval_personal100 import parse_json

SYSTEM='''Predict the next assistant tool calls based on the conversation prefix.
Return JSON ONLY: {"actions": [{"tool":"ExactAPIFunctionName", "arguments":{...}}]}.
Only output executable API calls the assistant should make at this turn, in order.
Return an empty actions list if the assistant should ask a question or just respond.
Do not output future-turn calls. Omit internal authentication/session token arguments
(the runtime injects them). Preserve concrete values in the user context.
API names correspond to account, alarms, calendar, email, messages, reminders,
and weather services: AddAlarm, AddReminder, ChangePassword, CompleteReminder,
CreateEvent, CurrentWeather, DeleteAccount, DeleteAlarm, DeleteEvent,
DeleteReminder, FindAlarms, ForecastWeather, GetAccountInformation,
GetReminders, HistoricWeather, LogoutUser, ModifyEvent, QueryCalendar,
QueryUser, RegisterUser, ResetPassword, SearchInbox, SearchMessages,
SendEmail, SendMessage, and other ToolTalk API names listed by the repository.
'''


def score(gold,pred):
    actions=pred.get('actions',[]) if isinstance(pred,dict) else []
    if not isinstance(actions,list):actions=[]
    names=[a.get('tool') if isinstance(a,dict) else None for a in actions]
    expected=[a['tool'] for a in gold]
    route_ok=names==expected
    args_ok=route_ok
    if args_ok:
        for guess,answer in zip(actions,gold):
            got=guess.get('arguments') if isinstance(guess.get('arguments'),dict) else {}
            if any(got.get(k)!=v for k,v in answer['arguments'].items()):args_ok=False
    return {'tool_sequence_exact':route_ok,'gold_argument_subset_exact':args_ok}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--data',type=Path,default=Path('tooltalk100.jsonl'))
    p.add_argument('--output',type=Path,default=Path('results_tooltalk100.jsonl'))
    p.add_argument('--model',default='gpt-6-luna')
    p.add_argument('--effort',default='medium',choices=['none','low','medium','high','xhigh','max'])
    p.add_argument('--limit',type=int,default=100)
    p.add_argument('--retry-errors',action='store_true',help='Retry rows previously saved with an error')
    args=p.parse_args()
    if not args.data.is_file():p.error('Run prepare_tooltalk100.py first (requires network access).')
    if not os.environ.get('OPENAI_API_KEY'):p.error('OPENAI_API_KEY is unset')
    try:from openai import OpenAI
    except ImportError:p.error('Install OpenAI Python SDK: pip install openai')
    client=OpenAI()
    rows=[json.loads(x) for x in args.data.read_text(encoding='utf-8').splitlines() if x.strip()][:args.limit]
    done={}
    if args.output.exists():
        # Keep the latest successful attempt for each ID. API/format failures
        # should not erase a valid earlier prediction during retries.
        for line in args.output.read_text(encoding='utf-8').splitlines():
            if line.strip():
                item=json.loads(line)
                if item.get('error') is None or item['id'] not in done:
                    done[item['id']]=item
    if args.retry_errors:
        done={key:value for key,value in done.items() if value.get('error') is None}
    for row in rows:
        if row['id'] in done:continue
        data={'metadata':row['metadata'],'history':row['history']}
        t0=monotonic()
        try:
            response=client.responses.create(model=args.model,reasoning={'effort':args.effort},
                input=[{'role':'developer','content':SYSTEM},
                       {'role':'user','content':json.dumps(data,ensure_ascii=False)}],
                text={'format':{'type':'json_object'}})
            pred=parse_json(response.output_text)
            metrics=score(row['gold_actions'],pred)
            error=None
        except Exception as e:
            pred=None;metrics=None;error=str(e)
        result={'id':row['id'],'difficulty':row['difficulty'],
                'metrics':metrics,'gold':row['gold_actions'],
                'prediction':pred,'error':error,'latency_s':round(monotonic()-t0,3)}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('a',encoding='utf-8') as fp:fp.write(json.dumps(result,ensure_ascii=False)+'\n')
        done[row['id']]=result
        print(row['id'], metrics or error)
    scored=[r for r in done.values() if r['metrics'] is not None]
    groups=defaultdict(list)
    for r in scored:groups['ALL'].append(r);groups[r['difficulty']].append(r)
    for g,r in sorted(groups.items()):
        n=len(r)
        print(g,n,{m:round(sum(int(x['metrics'][m]) for x in r)/n,4)
                   for m in ('tool_sequence_exact','gold_argument_subset_exact')})
    print('WARNING: all these scores are ONE-STEP prediction with gold previous context; NOT live app success.')

if __name__=='__main__':main()
