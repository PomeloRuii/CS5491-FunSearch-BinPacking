"""Single-attempt pinned Qwen generation; every attempt needs a budget reservation."""
import base64
import hashlib
import json
from pathlib import Path
import socket
from time import perf_counter
from urllib import request, error
import bootstrap3
from bootstrap3 import ROOT,PROJECT
from common import read,write,append,digest,file_hash,stamp
from approval import GenerationBudget
from ollama_adapter import OllamaConfig, OllamaAdapter, NoRedirect, MAX_RESPONSE_BYTES
from candidates import Candidate
from interface import messages_for,expected_name,PROMPT_ID
from static_policy import validate

class EventLog:
    def __init__(self,path):self.path=Path(path)
    def emit(self,event,**value):append(self.path,{'event':event,**value})

def fixed_config():
    value=read(ROOT/'config.json')
    return OllamaConfig(**{k:v for k,v in value.items() if k in OllamaConfig.__dataclass_fields__})

class QwenPilotAdapter:
    def __init__(self,budget,output,purpose='pool'):
        self.budget=budget;self.output=Path(output);self.output.mkdir(parents=True,exist_ok=True)
        self.config=fixed_config();self.logger=EventLog(self.output/'events.jsonl')
        self.metadata_adapter=OllamaAdapter(self.config,self.logger)
        self.metadata=None
        self.purpose=purpose
        if budget.manifest['generation_config_sha256']!=file_hash(ROOT/'config.json'):
            raise PermissionError('Approved generation settings differ')
        if budget.manifest['prompt_source_sha256']!=file_hash(PROJECT/'phase1b/phase1d/interface.py'):
            raise PermissionError('Approved prompt implementation differs')

    def draw(self,prompt,candidate_id,database_checkpoint_sha256):
        # Check budget identity before even querying metadata.
        if self.metadata is None:
            self.metadata=self.metadata_adapter.model_metadata();write(self.output/'model_metadata.json',self.metadata)
        cfg=self.config;messages=messages_for(prompt)
        payload={'model':cfg.model,'messages':messages,'n':1,'stream':False,
            'temperature':cfg.temperature,'top_p':cfg.top_p,'max_tokens':cfg.max_tokens,
            'seed':cfg.seed,'reasoning_effort':cfg.reasoning_effort}
        slot,reservation=self.budget.reserve(candidate_id,payload,self.purpose)
        directory=self.output/f'candidate_{candidate_id:03d}'
        directory.mkdir(exist_ok=False)
        write(directory/'request.json',{'payload':payload,'prompt_id':PROMPT_ID,
            'prompt_sha256':digest(messages),'reservation':reservation,'island_id':int(prompt.island_id),
            'version_generated':prompt.version_generated,'database_checkpoint_sha256':database_checkpoint_sha256,
            'database_prompt':{'code':prompt.code,'island_id':int(prompt.island_id),'version_generated':prompt.version_generated},
            'generation_settings':__import__('dataclasses').asdict(cfg),'model_metadata':self.metadata})
        start=perf_counter();outcome={'candidate_id':candidate_id,'origin':'ollama','model':cfg.model,
            'digest':cfg.expected_digest,'quantization':cfg.expected_quantization,'api_attempts':1,
            'island_id':int(prompt.island_id),'version_generated':prompt.version_generated,
            'expected_name':expected_name(prompt),'prompt_sha256':digest(messages),
            'database_checkpoint_sha256':database_checkpoint_sha256,'observed_fitness':None,
            'executed':False,'source_sha256':None,'status':'request_failed'}
        try:
            data=json.dumps(payload,ensure_ascii=False,allow_nan=False).encode()
            req=request.Request(cfg.base_url+'/chat/completions',data=data,headers={'Content-Type':'application/json'})
            opener=request.build_opener(request.ProxyHandler({}),NoRedirect())
            # One network attempt. An HTTP failure body is retained too.
            write(slot/'transport_attempt_started.json',{'candidate_id':candidate_id,'timestamp':stamp(),
                'delivery_status':'unknown_until_response','payload_sha256':digest(payload)})
            try:
                with opener.open(req,timeout=cfg.request_timeout_seconds) as response:
                    raw=response.read(MAX_RESPONSE_BYTES+1);outcome['http_status']=response.status
            except error.HTTPError as exc:
                raw=exc.read(MAX_RESPONSE_BYTES+1)
                (directory/'raw_http_response.bin').write_bytes(raw)
                outcome['http_status']=exc.code
                raise
            (directory/'raw_http_response.bin').write_bytes(raw)
            outcome['raw_response_sha256']=hashlib.sha256(raw).hexdigest()
            if len(raw)>MAX_RESPONSE_BYTES:raise ValueError('API response exceeds 1 MiB cap')
            result=json.loads(raw);write(directory/'response.json',result)
            if not isinstance(result,dict) or result.get('model')!=cfg.model:raise ValueError('Response identity differs')
            choices=result.get('choices')
            if not isinstance(choices,list) or len(choices)!=1:raise ValueError('Expected exactly one candidate')
            choice=choices[0];message=choice.get('message')
            if not isinstance(message,dict) or message.get('tool_calls') or message.get('function_call'):
                raise ValueError('Unexpected assistant response structure')
            source=message.get('content')
            if not isinstance(source,str):raise ValueError('Missing text source')
            # Preserve exact response UTF-8 bytes on Windows too; no newline translation.
            (directory/'source.py.txt').write_bytes(source.encode('utf-8'))
            outcome.update(source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                source_file=str((directory/'source.py.txt').relative_to(self.output)),
                finish_reason=choice.get('finish_reason'),usage=result.get('usage'),response_id=result.get('id'),
                response_model=result.get('model'),source=source)
            try:
                parsed,static=validate(source,outcome['expected_name'],choice.get('finish_reason'))
                outcome.update(status='static_valid_pending_execution_approval',static=static,
                    parsed_body_sha256=hashlib.sha256(parsed.body.encode()).hexdigest())
            except (SyntaxError,ValueError) as exc:
                outcome.update(status='static_rejected',failure_reason=str(exc),static={'status':'FAIL'})
        except (OSError,ValueError,KeyError,TypeError,IndexError,AttributeError) as exc:
            outcome.update(failure_type=type(exc).__name__,failure_reason=str(exc),delivery_status='unknown_on_transport_failure')
        finally:
            outcome['generation_seconds']=perf_counter()-start
            write(directory/'candidate.json',outcome);write(slot/'outcome.json',outcome)
            append(self.output/'artifact_ledger.jsonl',outcome)
        return outcome

def load_candidate(pool_file,row):
    pool_file=Path(pool_file);directory=pool_file.parent
    target=(directory/row['source_file']).resolve()
    if not target.is_relative_to(directory.resolve()):raise PermissionError('Artifact path escape refused')
    source=target.read_bytes().decode('utf-8')
    if hashlib.sha256(source.encode()).hexdigest()!=row['source_sha256']:raise PermissionError('Saved source changed')
    return Candidate(source,'ollama',row['finish_reason'],row['generation_seconds'],row.get('usage'),
        {**row,'artifact_candidate_id':row['candidate_id'],'artifact_manifest_sha256':file_hash(pool_file)})

