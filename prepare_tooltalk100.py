#!/usr/bin/env python3
"""Fetch 100 held-out tool-decision points from Microsoft's open ToolTalk conversations.
Source: https://github.com/microsoft/ToolTalk (MIT license).
Each evaluation is teacher-forced one decision point, NOT a live execution benchmark.
"""
import argparse
import json
import random
import urllib.request
from pathlib import Path

REPO="https://api.github.com/repos/microsoft/ToolTalk/contents/data/"
RAW="https://raw.githubusercontent.com/microsoft/ToolTalk/main/data/"


def get_json(url):
    req=urllib.request.Request(url,headers={'User-Agent':'muse-action-eval-research/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as response:
        return json.loads(response.read().decode('utf-8'))


def extract(doc, difficulty):
    turns=doc['conversation']
    out=[]
    for i,t in enumerate(turns[:-1]):
        if t.get('role')!='user':continue
        # ToolTalk's gold answer is the assistant turn after each user turn.
        after=next((x for x in turns[i+1:] if x.get('role')=='assistant'),None)
        if after is None:continue
        prior=[]
        for h in turns[:i+1]:
            if h.get('role') in ('user','assistant'):
                prior.append({'role':h['role'],'content':h.get('text','')})
            for api in h.get('apis') or []:
                prior.append({'role':'tool','content':f"{api['request']['api_name']} returned "+json.dumps(api.get('response'),ensure_ascii=False)})
        actions=[]
        for api in after.get('apis') or []:
            request=api.get('request') or {}
            args=request.get('parameters') or {}
            actions.append({'tool':request.get('api_name'),
                            'arguments':{k:v for k,v in args.items() if k not in ('session_token','password')}})
        out.append({'source':'microsoft/ToolTalk','difficulty':difficulty,
                    'conversation':doc['name'],'turn_index':t.get('index',i),
                    'metadata':{'location':doc.get('metadata',{}).get('location'),
                                'timestamp':doc.get('metadata',{}).get('timestamp'),
                                'username':doc.get('metadata',{}).get('username')},
                    'history':prior,'gold_actions':actions})
    return out


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,default=Path('tooltalk100.jsonl'))
    p.add_argument('--cache',type=Path,default=Path('.tooltalk_cache'))
    args=p.parse_args()
    args.cache.mkdir(parents=True,exist_ok=True)
    sampled={}
    for folder in ('easy','tooltalk'):
        cache_list=args.cache/f'{folder}_listing.json'
        if cache_list.exists():listing=json.loads(cache_list.read_text())
        else:
            listing=get_json(REPO+folder)
            cache_list.write_text(json.dumps(listing),encoding='utf-8')
        cases=[]
        for entry in listing:
            if not entry['name'].endswith('.json'):continue
            local=args.cache/(folder+'__'+entry['name'])
            if local.exists():doc=json.loads(local.read_text(encoding='utf-8'))
            else:
                doc=get_json(RAW+folder+'/'+entry['name'])
                local.write_text(json.dumps(doc,ensure_ascii=False),encoding='utf-8')
            cases.extend(extract(doc,folder))
        if len(cases)<50:raise RuntimeError(f'Only {len(cases)} {folder} tool decision points')
        rng=random.Random(20261014 if folder=='easy' else 20261015)
        sampled[folder]=rng.sample(cases,50)
    rows=sampled['easy']+sampled['tooltalk']
    random.Random(20261016).shuffle(rows)
    for i,row in enumerate(rows,1):row['id']=f'T{i:03d}'
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('w',encoding='utf-8') as fp:
        for row in rows:fp.write(json.dumps(row,ensure_ascii=False)+'\n')
    print(f"Saved {len(rows)} real-source turn-level cases to {args.output}")
    print('By difficulty:',{k:len(v) for k,v in sampled.items()})
    print('Actions (gold nonempty):',sum(bool(x['gold_actions']) for x in rows))

if __name__=='__main__':main()
