"""CEL/CDR must describe the same complete real call, including negative paths."""
import csv
import io
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def csv_text(rows):
    output = io.StringIO()
    csv.writer(output).writerows(rows)
    return output.getvalue()


def trace_rows(tenant=None):
    origin = 'PJSIP/t9-incoming-00000001'
    rows = [
        ['CHAN_START','from-tdm-gateway','5511900003333',origin,'','','','123.1','123.1',''],
    ]
    if tenant:
        destination = f'PJSIP/{tenant}-1001-00000002'
        rows += [
            ['APP_START','ura-principal','s',origin,'Answer','','','123.1','123.1',''],
            ['ANSWER','ura-principal','s',origin,'Answer','','','123.1','123.1',''],
            ['APP_START',tenant+'-internal','1001',origin,'Dial','PJSIP/'+tenant+'-1001,20',tenant,'123.1','123.1',''],
            ['CHAN_START',tenant+'-internal','1001',destination,'','','','123.2','123.1',''],
            ['ANSWER',tenant+'-internal','1001',destination,'','','','123.2','123.1',''],
            ['BRIDGE_ENTER',tenant+'-internal','1001',origin,'Dial','',tenant,'123.1','123.1',''],
            ['BRIDGE_ENTER',tenant+'-internal','1001',destination,'','','','123.2','123.1',''],
            ['HANGUP',tenant+'-internal','1001',destination,'','','','123.2','123.1','{"hangupcause":16}'],
            ['CHAN_END',tenant+'-internal','1001',destination,'','','','123.2','123.1',''],
        ]
    if not tenant:
        rows.append(['APP_START','from-tdm-gateway','did-desconhecido',origin,
                     'Hangup','21','','123.1','123.1',''])
    rows += [
        ['HANGUP',tenant+'-internal' if tenant else 'from-tdm-gateway',
         '1001' if tenant else 'did-desconhecido',origin,'Hangup','',tenant or '',
         '123.1','123.1','{"hangupcause":16}' if tenant else '{"hangupcause":21}'],
        ['CHAN_END',tenant+'-internal' if tenant else 'from-tdm-gateway',
         '1001' if tenant else 'did-desconhecido',origin,'','','','123.1','123.1',''],
        ['LINKEDID_END',tenant+'-internal' if tenant else 'from-tdm-gateway',
         '1001' if tenant else 'did-desconhecido',origin,'','','','123.1','123.1',''],
    ]
    return rows


def cdr_row(tenant=None):
    return [tenant or '', '199999', '1001' if tenant else 'did-desconhecido',
            tenant+'-internal' if tenant else 'from-tdm-gateway',
            'PJSIP/t9-incoming-00000001',f'PJSIP/{tenant}-1001-00000002' if tenant else '',
            'ANSWERED' if tenant else 'FAILED','2' if tenant else '0','123.1']


@pytest.mark.parametrize('tenant', ['t1','t2','t3',None])
def test_complete_trace_and_cdr_are_correlated(tenant):
    from lab.did_evidence import evaluate_trace, evaluate_cdr
    trace = evaluate_trace(csv_text(trace_rows(tenant)),tenant)
    assert trace['well_formed'] and trace['correlated'] and trace['complete']
    assert trace['isolated'] is True
    if tenant:
        assert trace['routed'] is True
        assert trace['entered_ura'] is True
    else:
        assert all(trace[key] for key in ('never_answered','no_delivery','no_side_effects','cause_21'))
        assert trace['entered_ura'] is False
    assert all(evaluate_cdr(csv_text([cdr_row(tenant)]),trace,tenant).values())


@pytest.mark.parametrize('change', [
    lambda rows:rows.pop(),
    lambda rows:rows[0].__setitem__(8,'999.9'),
    lambda rows:rows[3].__setitem__(3,'PJSIP/t2-1001-00000009'),
    lambda rows:rows[3].__setitem__(5,'PJSIP/t2-1001,20'),
    lambda rows:rows[2].__setitem__(1,'t2-internal'),
    lambda rows:rows.append(trace_rows('t2')[0]),
])
def test_partial_or_cross_tenant_trace_cannot_prove_routing(change):
    from lab.did_evidence import evaluate_trace
    rows = trace_rows('t1')
    change(rows)
    result = evaluate_trace(csv_text(rows),'t1')
    assert not all(result[key] for key in ('well_formed','correlated','complete','routed','isolated'))


@pytest.mark.parametrize('event', ['ANSWER','BRIDGE_ENTER','APP_START'])
def test_rejected_path_cannot_contain_answer_bridge_or_recording(event):
    from lab.did_evidence import evaluate_trace
    rows = trace_rows()
    rows.insert(1,[event,'from-tdm-gateway','5511900003333',rows[0][3],
                   'MixMonitor' if event=='APP_START' else '', '', '', '123.1','123.1',''])
    result = evaluate_trace(csv_text(rows))
    assert not all(result[key] for key in ('never_answered','no_delivery','no_side_effects'))


@pytest.mark.parametrize('extra', ['','{}','{"hangupcause":16}',
                                  '{"hangupcause":0,"hangupcause":21}',
                                  '{"hangupcause":true}'])
def test_rejection_requires_unambiguous_real_hangup_cause(extra):
    from lab.did_evidence import evaluate_trace
    rows = trace_rows()
    next(row for row in rows if row[0]=='HANGUP')[-1] = extra
    assert evaluate_trace(csv_text(rows))['cause_21'] is False


def test_empty_truncated_or_oversize_trace_never_proves_rejection():
    from lab.did_evidence import evaluate_trace, parse_cel
    for raw in ('','garbage','"unterminated', 'x'*(1024*1024+1)):
        trace = evaluate_trace(raw)
        assert not trace['complete']
        assert not trace['cause_21']
    assert parse_cel('garbage') is None


@pytest.mark.parametrize('column,value', [(0,'t2'),(1,'999999'),(2,'1002'),(3,'t2-internal'),
                                        (4,'PJSIP/t1-1001-00000001'),(5,'PJSIP/t2-1001-00000002'),
                                        (6,'NO ANSWER'),(7,'0'),(8,'123.9')])
def test_cdr_cannot_borrow_evidence_from_another_call(column,value):
    from lab.did_evidence import evaluate_trace, evaluate_cdr
    trace = evaluate_trace(csv_text(trace_rows('t1')),'t1')
    row = cdr_row('t1')
    row[column] = value
    assert not all(evaluate_cdr(csv_text([row]),trace,'t1').values())
    assert not all(evaluate_cdr(csv_text([cdr_row('t1')]*2),trace,'t1').values())


def test_negative_cdr_requires_no_tenant_no_destination_channel_and_zero_billsec():
    from lab.did_evidence import evaluate_trace, evaluate_cdr
    trace = evaluate_trace(csv_text(trace_rows()))
    for column,value in ((0,'t1'),(5,'PJSIP/t1-1001-00000002'),(6,'ANSWERED'),(7,'1')):
        row = cdr_row()
        row[column] = value
        assert not all(evaluate_cdr(csv_text([row]),trace).values())


def test_route_diagnostics_identify_missing_bridge_and_wrong_application_without_values():
    from lab.did_evidence import evaluate_trace
    good = evaluate_trace(csv_text(trace_rows('t1')),'t1')
    assert all(good[key] for key in ('ingress_context','one_dial','dial_destination','bridge_both'))
    rows = trace_rows('t1')
    rows = [row for row in rows if row[0]!='BRIDGE_ENTER']
    missing = evaluate_trace(csv_text(rows),'t1')
    assert missing['bridge_both'] is False and missing['one_dial'] is True
    rows = trace_rows('t1')
    rows[3][5] = 'PJSIP/PRIVATE_VALUE,20'
    wrong = evaluate_trace(csv_text(rows),'t1')
    assert wrong['dial_destination'] is False
    assert 'PRIVATE_VALUE' not in str({key:value for key,value in wrong.items() if type(value) is bool})


@pytest.mark.parametrize('application', ['Record','AGI','EAGI','System','TrySystem','VoiceMailMain'])
def test_negative_path_rejects_recording_and_other_unexpected_applications(application):
    from lab.did_evidence import evaluate_trace
    rows = trace_rows()
    event = list(rows[1]); event[4] = application
    rows.insert(1,event)
    assert evaluate_trace(csv_text(rows))['no_side_effects'] is False


def test_missing_application_events_cannot_prove_a_clean_negative_path():
    from lab.did_evidence import evaluate_trace
    rows = [row for row in trace_rows() if row[0]!='APP_START']
    assert evaluate_trace(csv_text(rows))['no_side_effects'] is False


@pytest.mark.parametrize('event,application', [('APP_END','Dial'),('APP_END','Record'),
                                             ('APP_END','VoiceMail'),('APP_END','Answer'),
                                             ('BRIDGE_EXIT','')])
def test_explicit_forbidden_end_event_blocks_rejection_even_if_start_is_missing(event,application):
    from lab.did_evidence import evaluate_trace, evaluate_cdr
    rows = trace_rows()
    extra = list(rows[1]); extra[0] = event; extra[4] = application
    rows.insert(1,extra)
    result = evaluate_trace(csv_text(rows))
    valid = all(result[key] for key in ('well_formed','correlated','complete','isolated',
                                        'never_answered','no_delivery','no_side_effects','cause_21'))
    assert not (valid and all(evaluate_cdr(csv_text([cdr_row()]),result).values()))


@pytest.mark.parametrize('mutation', ['reversed','duplicate_start','duplicate_hangup','duplicate_end','early_link_end'])
def test_lifecycle_must_be_unique_and_ordered(mutation):
    from lab.did_evidence import evaluate_trace
    rows = trace_rows()
    if mutation=='reversed': rows.reverse()
    elif mutation=='early_link_end': rows.insert(1,rows.pop())
    else:
        name = {'duplicate_start':'CHAN_START','duplicate_hangup':'HANGUP','duplicate_end':'CHAN_END'}[mutation]
        rows.insert(1,list(next(row for row in rows if row[0]==name)))
    assert evaluate_trace(csv_text(rows))['complete'] is False


def test_positive_dial_application_end_does_not_count_as_another_dial():
    from lab.did_evidence import evaluate_trace
    rows = trace_rows('t1')
    end = list(rows[3]); end[0] = 'APP_END'
    rows.insert(-3,end)
    result = evaluate_trace(csv_text(rows),'t1')
    assert result['one_dial'] is True and result['routed'] is True
