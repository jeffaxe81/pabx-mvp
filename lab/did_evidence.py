"""Bounded private CEL/CDR correlation; callers publish only boolean findings."""
import csv
import io
import json
import re

from .call_checks import cdr_rows

FIELDS = ('event','context','extension','channel','application','data','account',
          'uniqueid','linkedid','extra')
FORBIDDEN = {'answer','dial','queue','voicemail','mixmonitor','monitor','background','read','playback'}
ORIGIN = r'PJSIP/t9-incoming-[0-9a-f]+'
ID = r'[0-9]+\.[0-9]+'


def prepare_cel(conf):
    """CEL is enabled only in the disposable private DID configuration."""
    columns = ('eventtype','CHANNEL(context)','CHANNEL(exten)','CHANNEL(channame)',
               'CHANNEL(appname)','CHANNEL(appdata)','CHANNEL(accountcode)',
               'CHANNEL(uniqueid)','CHANNEL(linkedid)','eventextra')
    for name,body in (
        ('cel.conf','[general]\nenable=yes\napps=all\nevents=ALL\n'),
        ('cel_custom.conf','[mappings]\nLab.csv => '+','.join(
            '${CSV_QUOTE(${'+field+'})}' for field in columns)+'\n')):
        target = conf/name
        target.write_text(body)
        target.chmod(0o600)


def new_trace(before,after):
    if not after.startswith(before) or (before and not before.endswith('\n')):
        raise ValueError('rastro CEL mudou durante o laboratório')
    return after[len(before):]


def parse_cel(raw):
    if not isinstance(raw,str) or len(raw)>1024*1024:
        return None
    try:
        rows = list(csv.reader(io.StringIO(raw),strict=True))
    except csv.Error:
        return None
    if any(len(row)!=len(FIELDS) for row in rows):
        return None
    return [dict(zip(FIELDS,row)) for row in rows]


def _cause(extra):
    def unique(pairs):
        result = {}
        for key,value in pairs:
            if key in result: raise ValueError('duplicate CEL field')
            result[key] = value
        return result
    try:
        data = json.loads(extra,object_pairs_hook=unique)
        value = data.get('hangupcause') if isinstance(data,dict) else None
        return value if type(value) is int else None
    except (ValueError,TypeError):
        return None


def evaluate_trace(raw,tenant=None):
    if tenant not in (None,'t1','t2','t3'):
        raise ValueError('empresa de laboratório inválida')
    rows = parse_cel(raw)
    result = {key:False for key in ('well_formed','correlated','complete','routed','isolated',
                                   'never_answered','no_delivery','no_side_effects','cause_21','entered_ura',
                                   'ingress_context','one_dial','dial_destination','bridge_both')}
    if not rows:
        return result
    result['well_formed'] = True
    starts = [row for row in rows if row['event']=='CHAN_START']
    origins = [row for row in starts if re.fullmatch(ORIGIN,row['channel'])]
    if len(origins)!=1:
        return result
    origin = origins[0]
    result.update(_source_id=origin['uniqueid'],_source_channel=origin['channel'],
                  _original_did=origin['extension'])
    identities = {row['uniqueid'] for row in rows}
    channels = {row['uniqueid']:row['channel'] for row in starts}
    result['correlated'] = (all(re.fullmatch(ID,value) for value in identities)
                            and all(row['linkedid']==origin['uniqueid'] for row in rows)
                            and identities=={row['uniqueid'] for row in starts}
                            and len(starts)==len(identities)
                            and all(channels.get(row['uniqueid'])==row['channel'] for row in rows))
    result['complete'] = (result['correlated'] and sum(row['event']=='LINKEDID_END' for row in rows)==1 and all(
        any(row['event']==event and row['uniqueid']==identity for row in rows)
        for identity in identities for event in ('HANGUP','CHAN_END')))
    applications = [row for row in rows if row['event']=='APP_START']
    result['entered_ura'] = any(row['context']=='ura-principal' for row in rows)
    if tenant:
        destinations = [row for row in starts if re.fullmatch(r'PJSIP/'+tenant+r'-1001-[0-9a-f]+',row['channel'])]
        if len(destinations)==1:
            result.update(_destination_id=destinations[0]['uniqueid'],
                          _destination_channel=destinations[0]['channel'])
        allowed = {'from-tdm-gateway','ura-principal',tenant+'-internal'}
        result['isolated'] = (len(starts)==2 and len(destinations)==1
                              and all(row['context'] in allowed for row in rows)
                              and all(row['account'] in ('',tenant) for row in rows))
        dial = [row for row in applications if row['application'].lower()=='dial']
        bridge_ids = {row['uniqueid'] for row in rows if row['event']=='BRIDGE_ENTER'}
        result.update(ingress_context=origin['context']=='from-tdm-gateway',one_dial=len(dial)==1,
                      dial_destination=len(dial)==1 and dial[0]['data'].split(',')[0]=='PJSIP/'+tenant+'-1001',
                      bridge_both=bridge_ids==identities)
        result['routed'] = all(result[key] for key in ('ingress_context','one_dial','dial_destination',
                                                      'isolated','bridge_both','complete'))
    else:
        result['isolated'] = all(row['context']=='from-tdm-gateway' and not row['account'] for row in rows)
        result['never_answered'] = (not any(row['event']=='ANSWER' for row in rows)
                                    and not any(row['application'].lower()=='answer' for row in applications))
        result['no_delivery'] = (len(starts)==1 and not any(row['event']=='BRIDGE_ENTER' for row in rows)
                                 and not any(row['application'].lower() in ('dial','queue') for row in applications))
        result['no_side_effects'] = (result['isolated']
                                     and not any(row['application'].lower() in FORBIDDEN for row in applications))
        hangups = [row for row in rows if row['event']=='HANGUP' and row['uniqueid']==origin['uniqueid']]
        result['cause_21'] = len(hangups)==1 and _cause(hangups[0]['extra'])==21
    return result


def evaluate_cdr(raw,trace,tenant=None):
    rows = cdr_rows(raw)
    names = ('one_record','tenant','source','destination','context','origin_channel',
             'destination_channel','disposition','duration','correlated')
    result = {name:False for name in names}
    if rows is None or not trace.get('_source_id'):
        return result
    matching = [row for row in rows if row[8]==trace['_source_id']]
    if len(matching)!=1:
        return result
    row = matching[0]
    result.update(one_record=True,tenant=row[0]==(tenant or ''),source=row[1]=='199999',
                  context=row[3]==(tenant+'-internal' if tenant else 'from-tdm-gateway'),
                  origin_channel=row[4]==trace['_source_channel'],
                  correlated=trace.get('complete') is True)
    if tenant:
        result.update(destination=row[2]=='1001',
                      destination_channel=row[5]==trace.get('_destination_channel'),
                      disposition=row[6]=='ANSWERED',duration=row[7].isdigit() and int(row[7])>=1)
    else:
        result.update(destination=row[2] in ('did-desconhecido',trace['_original_did']),
                      destination_channel=row[5]=='',disposition=row[6] in ('FAILED','NO ANSWER'),
                      duration=row[7]=='0')
    return result
