#!/usr/bin/env python3
"""Inspect little-endian GGUF v2/v3 metadata and bind it to verified weights.
Format: https://github.com/ggml-org/ggml/blob/master/docs/gguf.md
"""
import argparse, hashlib, json, struct
from pathlib import Path


def metadata(path):
    with Path(path).open('rb') as file:
        def unpack(fmt):
            return struct.unpack('<'+fmt,file.read(struct.calcsize('<'+fmt)))[0]
        def string(keep=True):
            size=unpack('Q')
            if size>256*1024*1024:raise ValueError('Unreasonable metadata string')
            if keep:return file.read(size).decode('utf-8')
            file.seek(size,1)
        def value(kind,keep=True):
            formats={0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}
            if kind in formats:return unpack(formats[kind])
            if kind==8:return string(keep)
            if kind==9:
                subtype,count=unpack('I'),unpack('Q')
                if count>10_000_000:raise ValueError('Unreasonable metadata array')
                for _ in range(count):value(subtype,False)
                return {'array_type':subtype,'count':count}
            raise ValueError('Unsupported GGUF metadata type '+str(kind))
        if file.read(4)!=b'GGUF':raise ValueError('Not little-endian GGUF')
        version=unpack('I')
        if version not in (2,3):raise ValueError('Unsupported GGUF version')
        tensors,count=unpack('Q'),unpack('Q')
        if count>100_000:raise ValueError('Unreasonable metadata count')
        result={}
        for _ in range(count):
            key=string();result[key]=value(unpack('I'))
        return result


def inspect(path,expected_sha256,model_path):
    path=Path(path)
    with path.open('rb') as file:actual=hashlib.file_digest(file,'sha256').hexdigest()
    if actual!=expected_sha256:raise ValueError('Artifact SHA256 mismatch')
    values=metadata(path)
    if values.get('split.count',1)>1:raise ValueError('Split GGUF is unsupported; all shards must be verified')
    return {'artifact_sha256':actual,'artifact_bytes':path.stat().st_size,
        'model_path':model_path,'metadata':values,
        'template_sha256':hashlib.sha256(values['tokenizer.chat_template'].encode()).hexdigest()}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--artifact',required=True,type=Path)
    p.add_argument('--sha256',required=True);p.add_argument('--model-path',required=True);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();result=inspect(a.artifact,a.sha256,a.model_path)
    with a.output.open('x') as out:out.write(json.dumps(result,indent=2)+'\n')
