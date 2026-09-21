#!/usr/bin/env python3
"""Fixed development keyword baseline. Reads feedback only, never references.

Authored after reviewing the development rubric. It is not a trained classifier
or a blinded contestant, and cannot reliably resolve quotation or negation scope.
"""
import argparse
import json
import re
import time
from pathlib import Path
from development_benchmark import ROOT, digest, read_rows

VERSION = 'rules-v1'
INSUFFICIENT = 'insufficient_information'
KEYS = ('sentiment','follow_up_needed','serious_concern_reported','testimonial_potential')


def hit(pattern, text):
    return re.search(pattern, text, re.I) is not None


def classify(feedback):
    text = feedback.lower().replace('’', "'")
    if not hit(r'interview|recruit|hiring|panel|candidate|application|assessment|offer|reject|booking|feedback|process|selection', text):
        return dict.fromkeys(KEYS, INSUFFICIENT)
    positive = hit(r'friendly|helpful|useful|clear|fair|respectful|welcoming|thoughtful|excellent|appreciat|comfortable|impressed|good experience', text)
    negative = hit(r'but|however|rude|unfair|upset|uncomfort|disappoint|humiliat|ignored|refus|threat|discriminat|harass|exclud|no one|nobody|no reply|not replied|not received|unanswered|still waiting|missed|wasn.t there|felt off|not sorted', text)
    negated_concern = hit(r'no (?:discrimination|harassment)|did not (?:discriminate|harass)|didn.t (?:discriminate|harass)|policy (?:against|on)', text)
    identity = hit(r'age|older|young|religio|muslim|christian|race|racial|black|white|asian|pregnan|sex|women|woman|men|man|gender|trans|gay|lesbian|disabil|accent|nationality', text)
    mistreatment = hit(r'too old|too young|not (?:hire|suit)|don.t (?:hire|want)|do not (?:hire|want)|because|belong|stereotype|can.t|cannot|unsuitable|excluded', text)
    explicit_concern = hit(r'threat|sexual (?:comment|harass)|unwanted|retaliat|private.*(?:sent|shared|expos)|(?:sent|shared).*another candidate|(?:refus|ignor).*(?:accessib|adjustment|accommodation|caption)|(?:ask|demand).*(?:pregnan|medication|diagnos|family plans)', text)
    vague_concern = hit(r'discriminat|humiliat|culture fit|accessibility issue', text)
    concern = 'yes' if not negated_concern and (explicit_concern or (identity and mistreatment)) else (INSUFFICIENT if vague_concern and not negated_concern else 'no')
    sentiment = 'mixed' if positive and negative else ('positive' if positive else ('negative' if negative else 'neutral'))
    no_contact = hit(r'do not contact|don.t contact|no (?:reply|response|contact) (?:needed|required)|nothing (?:else|further).*need', text)
    resolved = hit(r'resolved|fully (?:fixed|refunded)|now (?:fixed|sorted)|reimbursed|received the refund', text)
    unresolved = hit(r'still waiting|not received|no reply|not replied|unanswered|nobody.*replied|overdue|emailed twice|please (?:call|contact|explain)|would like to discuss|whether.*reassess|not sorted|rearrang', text)
    followup = 'no' if no_contact or (resolved and not unresolved) else ('yes' if unresolved else 'no')
    specific = hit(r'questions|feedback|schedule|timeline|format|example|exercise|explain|update|adjustment|caption|travel', text) and len(text.split()) >= 15
    testimonial = 'yes' if sentiment == 'positive' and concern == 'no' and specific else 'no'
    return dict(zip(KEYS,(sentiment,followup,concern,testimonial)))


def run(output):
    source_hash = digest(Path(__file__).read_text())
    rows = read_rows(ROOT/'data/pilot/inputs.jsonl')
    with open(output,'x') as out:
        for row in rows:
            start = time.perf_counter()
            result = classify(row['feedback'])
            elapsed = time.perf_counter()-start
            out.write(json.dumps({'id':row['id'],'status':'ok','prediction':result,
                'requested_model':VERSION,'returned_model':VERSION,'surface':'Python fixed keyword rules',
                'input_sha256':digest(row['feedback']),'rules_sha256':source_hash,
                'elapsed_seconds':elapsed,'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                'hosted_charge_usd':0})+'\n')

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    run(p.parse_args().output)
