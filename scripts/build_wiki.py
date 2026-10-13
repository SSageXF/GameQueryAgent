"""Build a complete, auditable Wiki snapshot and semantic chunks, offline."""
import gzip
import hashlib
import html
import json
import re
import argparse
from collections import Counter
from pathlib import Path
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'artifacts/wiki'
OUT=ROOT/'data/wiki'
LABELS={'original':'卡面原文','awakening':'觉醒','officialSkill':'技能与强化','growth':'属性成长','formal':'站方解释','pending':'待确认','rawBaseStats':'原始属性（原始单位）','attackStyle':'攻击方式','attackDistance':'攻击距离','quality':'阶级','faction':'阵营','relatedCards':'关联卡牌','derivedCards':'衍生卡牌','acquisition':'获取途径','resource':'资源','trigger':'触发','receivers':'承接','failures':'失效条件','shopCost':'商店费用','shopAvailable':'商店可获取','auctionRound':'拍卖回合','talentGroup':'天赋组','talentStage':'天赋阶段','baseStats':'基础属性','skills':'技能','skillSections':'棋手技能','skillNotes':'技能说明','baseProperties':'基础面板','levelSnapshots':'等级面板','enhancements':'强化节点','shortDefinition':'定义','boundary':'边界','stages':'阶段','description':'说明','text':'正文','content':'正文','core_idea':'核心思路','risk_note':'风险','statSteps':'属性节点','upgradeNodes':'升级节点','related':'关联','versionStatus':'版本状态'}
VISUAL={'image','thumbnail','portrait','avatar','awakeImage','icon','illustration','cardImage','poster','src','assets','delivery','width','height'}
META={'id','rawId','name','type','explorerType','version','versionStatus','sourceUpdate','sources','imageStatus'}

OFFLINE=None
def read(name):
    if OFFLINE is not None:
        if name=='embedded.json':return OFFLINE['embedded']
        if name=='sources.json':return {'collected_at':OFFLINE['collected_at'],'sources':OFFLINE['sources']}
        key=name.removesuffix('.json')
        return OFFLINE['catalogs'].get(key,OFFLINE['documents'].get(key))
    return json.loads((CACHE/name).read_text(encoding='utf-8'))

def clean(s):
    s=html.unescape(re.sub(r'</?[A-Za-z][^>]*>','',str(s))).replace('\\n','\n')
    return s.strip()

def flatten(value, prefix=''):
    if isinstance(value,dict):
        return '\n'.join(flatten(v, prefix+LABELS.get(k,k)+'：') for k,v in value.items() if k not in VISUAL and v is not None)
    if isinstance(value,list): return '\n'.join(flatten(v,prefix+f'{i+1}.') for i,v in enumerate(value))
    return prefix+clean(value)

def chunks(text, limit=1300):
    # No truncation: preserve every sentence/field, splitting long paragraphs if necessary.
    pieces=[]; cur=''
    for line in text.splitlines():
        for pos in range(0,max(len(line),1),limit):
            part=line[pos:pos+limit]
            if cur and len(cur)+len(part)+1>limit: pieces.append(cur);cur=''
            cur += ('\n' if cur else '')+part
    if cur: pieces.append(cur)
    return pieces

def build():
    OUT.mkdir(parents=True,exist_ok=True)
    modules=read('embedded.json')
    sources=read('sources.json')
    date=sources['collected_at'][:10]
    def module(prefix): return next(m for m in modules if m['file'].startswith(prefix))
    def dataset(prefix,i=0): return module(prefix)['datasets'][i]['value']
    catalogs={k:read(k+'.json') for k in ('hero','equipment','effect','talent')}
    snapshot={'schema':'wiki-full/v1','collected_at':sources['collected_at'],'sources':sources['sources'],
              'catalogs':catalogs,'embedded':modules,
              'documents':{k:read(k+'.json') for k in ('search-index','achievement-text','diamond-frenzy','lineup-featured-presets','lineup-card-index','dps-bootstrap','equipment-manifest')}}
    (OUT/'snapshot.json.gz').write_bytes(gzip.compress(json.dumps(snapshot,ensure_ascii=False).encode(),mtime=0))
    (OUT/'equipment-manifest.json').write_text(json.dumps({**snapshot['documents']['equipment-manifest'],'collected_at':date},ensure_ascii=False,indent=2),encoding='utf-8')
    records=[]; objects=[]; coverage=[]
    old={r['id']:r for r in json.loads((ROOT/'data/wzwxq.json').read_text(encoding='utf-8'))}
    def add(key,title,value,route,section,entity='',claim='wiki_reference',mode='万象大赛',status='current',version='',aliases=(),field='',explicit_id=None):
        body=flatten(value)
        if not body.strip():return []
        ids=[]
        for i,part in enumerate(chunks(body)):
            kid=explicit_id or 'WIKI-'+hashlib.sha256((key+'|'+field).encode()).hexdigest()[:20]
            if i: kid+=f'-{i+1}'
            row={'id':kid,'title':title,'body':part,'aliases':list(dict.fromkeys(a for a in [entity,title,*aliases] if a)),'entity':entity,
                 'topic':section,'section':section,'object_id':key,'field':field,'source_title':'万象棋知识站',
                 'source_url':'https://wzwxq.com'+route,'collected_at':date,'verified_at':date,'mode':mode,
                 'version_scope':f'Wiki采集于{date}；来源标注：{version or "见原页面"}；状态：{status}，不是实时游戏保证',
                 'claim_type':claim,'verification':'wiki_snapshot','eligible':claim!='pending',
                 'publication_status':status,'authority':'project_designated_wiki'}
            previous=old.get(kid)
            if previous and previous.get('verification')=='official_data_matched' and re.sub(r'\s+','',part)==re.sub(r'\s+','',previous['body']):
                row.update(claim_type='official_original',verification='official_data_matched',official_url=previous['official_url'])
            records.append(row);ids.append(kid)
        return ids
    def register(key,name,section,route,ids):
        objects.append({'id':key,'name':name,'section':section,'route':route,'record_ids':ids})
    for kind,d in catalogs.items():
        for item in d['items']:
            row={**d.get('itemDefaults',{}),**item}; key=row['id'];name=row['name'];route='/explore/'+key
            status='off_shelf' if row.get('temporarilyOffShelf') else row.get('versionStatus','supplementary')
            ids=[]
            for field,value in row.items():
                if field in META|VISUAL or value in (None,'',[],{}):continue
                claim='pending' if field=='pending' else 'site_interpretation' if field in {'formal','resource','trigger','receivers','failures','related','confidence'} else 'wiki_original' if field in {'original','awakening','officialSkill'} else 'wiki_reference'
                legacy='WX-'+key+'-'+{'officialSkill':'skill'}.get(field,field) if field in {'original','awakening','officialSkill','pending','formal'} else None
                if field=='formal':legacy='WX-'+key+'-interpretation'
                ids+=add(key,name+'·'+LABELS.get(field,field),value,route,kind,name,claim,status=status,version=row.get('version',''),field=field,explicit_id=legacy)
            register(key,name,kind,route,ids)
        coverage.append({'section':kind,'source_objects':len(d['items']),'imported_objects':len(d['items']),'status':'complete'})
    # The acquisition panel overlays costs/limits from a separate public module.
    effect_names={x['id']:x['name'] for x in catalogs['effect']['items']}
    for key,values in dataset('draw-effect-defaults').items():
        name=effect_names.get(key,key)
        add(key,name+'·商店费用与获取限制',values,'/explore/'+key,'effect',name,'site_interpretation',field='acquisition_limits',aliases=['购买','费用','获取'])
    # Reproduce the site's override: current official skill sections replace older player text.
    current={p['name']:p for p in dataset('chessplayerFacts',1)}
    players=dataset('chessplayerFacts',2)
    for p in players:
        player=dict(p)
        if p['name'] in current:
            player.update(skillSections=current[p['name']]['skillSections'],skillNotes=[],skillEvidence='站点2026-09-29棋手图鉴覆盖旧技能')
            player['currentCards']=current[p['name']].get('cards',[])
        ids=[];route='/players/'+quote(p['name'])
        for field,v in player.items():
            if field in VISUAL|{'id','name'} or v in (None,'',[],{}):continue
            claim='wiki_original' if field in {'skillSections','currentCards'} else 'site_interpretation'
            ids+=add(p['id'],p['name']+'·'+LABELS.get(field,field),v,route,'players',p['name'],claim,field=field,aliases=['棋手'+p['name']])
        register(p['id'],p['name'],'players',route,ids)
    biographies=next(d['value'] for d in module('ChessplayerArchive')['datasets'] if isinstance(d['value'],list) and d['value'] and isinstance(d['value'][0],dict) and 'stories' in d['value'][0])
    for bio in biographies:
        name=bio['name'];route='/players/'+quote(name)
        add('bio-'+name,name+'·人物档案',bio['facts'],route,'players',name,'wiki_original',field='biography',aliases=['年龄','身高','生日','喜好','职业'])
        for field in ('stories','questions'):
            for i,item in enumerate(bio[field]):
                add('bio-'+name+'-'+field+'-'+str(i),name+'·'+item.get('title', '好感问答'),item,route,'players',name,'wiki_original',field=field,aliases=['故事' if field=='stories' else '好感问答'])
    for i in (0,1):
        for name,value in dataset('ChessplayerArchive',i).items():
            add('player-cards-'+name+'-'+str(i),name+'·关联牌与强化',value,'/players/'+quote(name),'players',name,'wiki_reference',field='relatedCards')
    mechanics=dataset('wiki-knowledge')
    for m in mechanics:
        route='/mechanics/'+m['id'];key='mechanic-'+m['id']
        claim='pending' if m.get('evidence',{}).get('status')=='unverified' else 'site_interpretation'
        ids=add(key,m['name'],m,route,'mechanics',m['name'],claim,aliases=m.get('aliases',[]))
        register(key,m['name'],'mechanics',route,ids)
    summon=next(d['value'] for d in module('summon-cards')['datasets'] if isinstance(d['value'],list) and d['value'] and isinstance(d['value'][0],dict) and str(d['value'][0].get('id','')).startswith('summon-'))
    for s in summon:
        route='/explore/'+s['id'];ids=add(s['id'],s['name'],s,route,'summons',s['name'],'site_interpretation',status='supplementary')
        register(s['id'],s['name'],'summons',route,ids)
    guides=dataset('BeginnerGuide',0)+[dataset('BeginnerGuide',1),{'name':'活动玩法','items':dataset('BeginnerGuide',2)}]
    for group in guides:
        for item in group['items']:
            key='guide-'+item['id'];mode='其他玩法' if group['name']=='活动玩法' else '万象大赛'
            ids=add(key,item['title'],item,'/guide','guide',claim='wiki_original',mode=mode,aliases=[group['name']])
            register(key,item['title'],'guide','/guide',ids)
    for cat in snapshot['documents']['achievement-text']['categories']:
        mode='钻石狂潮' if '钻石' in cat['name'] else '其他玩法' if '娱乐' in cat['name'] else '万象大赛'
        for a in cat['achievements']:
            key='achievement-'+str(a['stages'][0]['id']);ids=add(key,a['name']+'·成就',a,'/achievements','achievements',a['name'],'wiki_original',mode,version='客户端配置1.3.0.4；站点标注2026-09-30',aliases=['成就',cat['name']])
            register(key,a['name'],'achievements','/achievements',ids)
    for item in snapshot['documents']['lineup-featured-presets']['records']:
        route='/lineups/detail/'+quote(item['id'],safe='');ids=add(item['id'],item['title'],item,route,'lineups',claim='site_interpretation',version=item.get('updated_at',''),aliases=['阵容',item.get('chessplayer','')])
        register(item['id'],item['title'],'lineups',route,ids)
    for group,items in [('official_updates',dataset('UpdatesCenter',0)),('site_updates',dataset('UpdatesCenter',1))]:
        for i,item in enumerate(items):
            key=group+'-'+str(item.get('id',i));route='/updates/official/'+item['id'] if group=='official_updates' else '/updates'
            ids=add(key,item['title'],item,route,group,claim='wiki_original' if group=='official_updates' else 'site_interpretation',mode='通用',status='historical',version=item.get('date',''),aliases=['公告','更新',item.get('date','')])
            register(key,item['title'],group,route,ids)
    diamond=snapshot['documents']['diamond-frenzy']
    for field in ('rules','events','packs','cards','officialNews','officialUpdate'):
        value=diamond[field];items=value if isinstance(value,list) else [value]
        for i,item in enumerate(items):
            key='diamond-'+field+'-'+str(item.get('id',i));name=item.get('name') or item.get('title') or '钻石狂潮'+field
            route='/modes/diamond-frenzy';ids=add(key,name,item,route,'diamond',name,'wiki_original','钻石狂潮',version=diamond['asOf'],aliases=['钻石狂潮',field])
            register(key,name,'diamond',route,ids)
    # Visible documentation for interactive columns; model data is not a real-match promise.
    tool_modules={'DrawSimulator':'/analysis/draw','DpsCalculator':'/analysis/dps','EquipmentValue':'/analysis/equipment-value','LineupProduct-':'/analysis/lineup','SiteToolGuide':'/guide/research'}
    for prefix,route in tool_modules.items():
        m=module(prefix)
        texts=[t['value'] for t in m['texts'] if len(t['value'])>=8]
        static=[flatten(d['value']) for d in m['datasets'] if len(flatten(d['value']))>=25]
        if prefix=='SiteToolGuide':
            for i,t in enumerate(m['texts'][:2]):
                path='/guide/hero-atlas' if i==0 else '/guide/research'
                add('tutorial-'+str(i),'Wiki工具使用指南',re.sub(r'<[^>]+>','\n',t['value']),path,'tools',claim='site_interpretation',mode='通用')
        ids=add('tool-'+prefix,prefix+'工具说明与边界','\n'.join(texts+static),route,'tools',claim='site_interpretation',mode='通用',aliases=['工具','模拟器','数值研究','计算器'])
        register('tool-'+prefix,prefix,'tools',route,ids)
    for key,route in [('dps-bootstrap','/analysis/dps'),('equipment-manifest','/analysis/equipment-value')]:
        doc=snapshot['documents'][key]
        for field,value in doc.items():
            if field in ('heroes','equipment'):
                for item in value:
                    name=item.get('name',item.get('id','工具数据'))
                    add(key+'-'+str(item.get('id',name)),name+'·'+('装备价值模型' if key=='equipment-manifest' else '固定木桩模型'),item,route,'tool_models',name,'site_model',field=field,aliases=['木桩' if key=='dps-bootstrap' else '装备价值'])
            else:add(key,key+'·'+field,value,route,'tool_models',claim='site_model',mode='通用',field=field)
    # Preserve relationship/atlas navigation and labels from the actual home module.
    nav=module('site-D')
    relations=next(d['value'] for d in nav['datasets'] if isinstance(d['value'],list) and d['value'] and isinstance(d['value'][0],dict) and 'baseId' in d['value'][0])
    for relation in relations:
        key='relation-'+relation['id'];title=relation['quantity']+'·装备关系演示'
        ids=add(key,title,relation,'/relations','relations',claim='site_interpretation',aliases=['装备合成','装备关系'])
        register(key,title,'relations','/relations',ids)
    navigation=[d['value'] for d in nav['datasets'] if '/relations' in json.dumps(d['value']) or '/atlas' in json.dumps(d['value']) or '/strategy' in json.dumps(d['value'])]
    add('navigation','Wiki栏目导航与关系入口',navigation,'/atlas','navigation',claim='site_interpretation',mode='通用')
    for section, count in Counter(o['section'] for o in objects).items():
        if section not in catalogs:coverage.append({'section':section,'source_objects':count,'imported_objects':count,'status':'complete'})
    ids=[r['id'] for r in records]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate chunk ID')
    index=snapshot['documents']['search-index']['items']
    # Search index includes 326 diamond card records under a different ID namespace.
    known={o['id'] for o in objects}; missing=[x for x in index if x['id'] not in known and x['kind'] not in ('mode','mechanic','player')]
    for kind, section in [('player','players'),('mechanic','mechanics'),('mode','diamond')]:
        names={o['name'] for o in objects if o['section']==section}
        missing.extend(x for x in index if x['kind']==kind and x['name'] not in names)
    report={'schema':'wiki-coverage/v1','collected_at':sources['collected_at'],'sections':coverage,'record_count':len(records),'objects':objects,
            'search_index_count':len(index),'search_index_missing':[{k:x[k] for k in ('id','name','kind')} for x in missing],
            'claim_counts':dict(Counter(r['claim_type'] for r in records)),
            'boundaries':['私人草稿和未知分享码不属于公开栏目内容','不复制运行网站程序，不宣称能执行Wiki模拟工具','图片URL及原始字段保留于快照；纯视觉文件不作为检索文本','历史公告保留原日期；不将旧公告自动覆盖当前卡面','公开共享阵容API当前返回HTML；采用页面自带公开精选阵容完整27条快照'],
            'snapshot_sha256':hashlib.sha256((OUT/'snapshot.json.gz').read_bytes()).hexdigest()}
    report['routes']={'/':'栏目入口','/atlas':'图鉴索引','/strategy':'攻略入口','/more':'栏目入口','/explore':'四类完整图鉴及召唤物',
                      '/players':'棋手技能、关联卡、档案、故事及好感问答','/mechanics':'机制词典','/guide':'新手与玩法说明',
                      '/guide/hero-atlas':'工具教程','/guide/research':'工具教程','/relations':'三条装备关系演示',
                      '/achievements':'全部六类成就及阶段','/updates':'官方归档与站点更新','/lineups':'公开精选阵容27套',
                      '/modes/diamond-frenzy':'规则、事件、卡包、卡牌及公告','/analysis':'固定木桩栏目别名',
                      '/analysis/dps':'模型说明和bootstrap','/analysis/draw':'模拟器说明和获取限制',
                      '/analysis/equipment-value':'模型说明、manifest及85份全等级分片','/analysis/lineup':'棋盘说明及公开阵容'}
    (OUT/'records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('record_count','search_index_count','search_index_missing','claim_counts')},ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--from-snapshot',action='store_true');args=parser.parse_args()
    if args.from_snapshot:OFFLINE=json.loads(gzip.decompress((OUT/'snapshot.json.gz').read_bytes()))
    build()
