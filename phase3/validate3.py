"""Actual security probes, archive data audit, and corrected task regressions."""
import json
from pathlib import Path
import subprocess
import tarfile
from time import perf_counter
import bootstrap3
from bootstrap3 import ROOT, PHASE2, PROJECT
from common import read, write, file_hash, stamp, digest
from backend3 import MinimizedRunner
from container_runner import ContainerRunner, PROBES, cli, docker_path
from validate import expected_outcome
from catalogue import reviewed_candidate
from interface import parse_candidate
from replay import accepted_full, accepted_fingerprint

def archive_audit(images, directory):
    docker=docker_path();archive=directory/'images.tar'
    cli(docker,['image','save','--output',str(archive),*images.values()],timeout=120)
    records=[]
    with tarfile.open(archive) as outer:
        manifests=json.load(outer.extractfile('manifest.json'))
        for manifest in manifests:
            cfg=json.load(outer.extractfile(manifest['Config']))
            config_digest='sha256:'+file_hash_bytes(outer.extractfile(manifest['Config']).read())
            # The containerd store's immutable ImageId is a manifest digest;
            # Docker save Config is a different object. Match complete diff IDs.
            builds=read(ROOT/'build_receipt.json')['images']
            scope=next(s for s,b in builds.items() if b['rootfs_layers']==cfg['rootfs']['diff_ids'])
            image=images[scope]
            app={};layer_records=[]
            for layer in manifest['Layers']:
                names=[]
                with tarfile.open(fileobj=outer.extractfile(layer),mode='r|*') as inner:
                    for member in inner:
                        name=member.name.removeprefix('./').lstrip('/')
                        if name.startswith('app/') and member.isfile():
                            raw=inner.extractfile(member).read()
                            app[name]=raw;names.append(name)
                layer_records.append({'layer':layer,'app_files':names})
            expected={p.name for p in (ROOT/'build_contexts'/scope).iterdir()}-{'Dockerfile'}
            if set(app)!={'app/'+n for n in expected}:raise AssertionError('Unexpected app file/layer')
            for name,raw in app.items():
                if file_hash_bytes(raw)!=file_hash(ROOT/'build_contexts'/scope/Path(name).name):
                    raise AssertionError('Layer contents differ from minimized context')
            data=json.loads(app['app/research_data.json']);bank=json.loads(app['app/states.json'])
            frozen=read(PHASE2/'data/research_data.json');original=read(PHASE2/'data/states.json')
            if scope=='development':
                if data!={'development':frozen['development']} or bank!={'fingerprint':original['fingerprint']}:
                    raise AssertionError('Development exposure differs')
            elif data!={'audit':{}} or bank!={'audit':original['audit']}:
                raise AssertionError('Reserved audit exposure differs')
            records.append({'scope':scope,'image':image,'config_digest':config_digest,'status':'PASS','all_app_files':sorted(app),
                'layers':layer_records,'final_heldout_included':False,'legacy_data_layers_included':False,
                'reserved_audit_in_development':False})
    # The archive is retained outside Git for reproducible layer-level inspection.
    write(directory/'image_layer_audit.json',records)
    return records

def file_hash_bytes(raw):
    import hashlib
    return hashlib.sha256(raw).hexdigest()

def main():
    directory=ROOT/'validations'/stamp();directory.mkdir(parents=True)
    images={s:r['ImageId'] for s,r in read(ROOT/'build_receipt.json')['images'].items()}
    start=perf_counter();checks=[];tasks=[]
    write(directory/'manifest.json',{'images':images,'policy':read(PROJECT/'phase1b/phase1c/policy.json'),
         'source_sha256':{str(p.relative_to(ROOT)):file_hash(p) for p in ROOT.glob('*.py')},
         'generated_sources_executed':0,'llm_requests':0})
    try:
        archive_audit(images,directory)
        for scope,image in images.items():
            runner=ContainerRunner(image)
            expected_scores=([-213.08333333333334,-212.41666666666666,-500.0]
                             if scope=='development' else [-1.0,-1.0,-2.0])
            for probe in PROBES:
                record=runner.run_probe(probe,3 if probe in ('infinite_loop','process_tree') else None)
                if probe.startswith('baseline_'):
                    position=['baseline_first_fit','baseline_best_fit','baseline_seed'].index(probe)
                    ok=(record['status']=='completed' and record['cleanup_verified'] and
                        (record.get('worker_result') or {}).get('result',{}).get('score')==expected_scores[position])
                else: ok=expected_outcome(record)
                write(directory/f'{scope}_{probe}.json',record)
                checks.append({'scope':scope,'probe':probe,'status':'PASS' if ok else 'FAIL'})
                if not ok:raise AssertionError(f'{scope} {probe} failed')
            print(scope+' 14 isolation checks passed',flush=True)
        runner=MinimizedRunner();bank=read(PHASE2/'data/states.json')
        expected={'first_fit':{'OR3':-213.08333333333334,'Weibull 5k':-2077.6666666666665},
                  'best_fit':{'OR3':-212.41666666666666,'Weibull 5k':-2072.6666666666665},
                  'seed':{'OR3':-500.0,'Weibull 5k':-5000.0}}
        for fixture,scores in expected.items():
            c=reviewed_candidate(fixture,'priority');p=parse_candidate(c.text,'priority')
            record=runner.run_task(c,p,'full');tasks.append(record)
            assert accepted_full(record,runner.data['development']) and record['result']['scores_per_group']==scores
        c=reviewed_candidate('best_fit','priority');p=parse_candidate(c.text,'priority')
        for size in (16,64,128):
            probe=runner.run_task(c,p,'fingerprint',size=size);tasks.append(probe)
            fused=runner.run_task(c,p,'fused',size=size);tasks.append(fused)
            assert accepted_fingerprint(probe,size,[s['state_id'] for s in bank['fingerprint'][:size]])
            assert accepted_full(fused,runner.data['development'])
            assert fused['result']['decisions']==probe['result']['decisions']
            skip=runner.run_task(c,p,'fused',size=size,representatives=[{'candidate_id':3,'decisions':probe['result']['decisions']}]);tasks.append(skip)
            assert not skip['result']['full_evaluation_performed'] and skip['result']['matched_representative_id']==3
        for fixture in ('invalid_shape','invalid_nan','runtime_error'):
            c=reviewed_candidate(fixture,'priority');p=parse_candidate(c.text,'priority')
            for action in ('full','fingerprint','fused'):
                record=runner.run_task(c,p,action);tasks.append(record);assert record['status']!='ok' and record['cleanup_verified']
        c=reviewed_candidate('validation_dtype','priority');p=parse_candidate(c.text,'priority')
        for action,size in [('full',16),('fingerprint',16),('fingerprint',64),('fingerprint',128)]:
            record=runner.run_task(c,p,action,size=size);tasks.append(record);assert record['status']=='ok'
        audit=MinimizedRunner('audit');c=reviewed_candidate('best_fit','priority');p=parse_candidate(c.text,'priority')
        record=audit.run_task(c,p,'fingerprint',dataset='audit',size=256,state_set='audit');tasks.append(record)
        assert accepted_fingerprint(record,256,[s['state_id'] for s in bank['audit']])
        # Scope refusals occur before creating a Docker worker.
        for run,kwargs in [(runner,dict(action='fingerprint',state_set='audit',size=256)),
                           (audit,dict(action='full',dataset='audit')),
                           (runner,dict(action='full',dataset='legacy_validation'))]:
            try:run.run_task(c,p,**kwargs)
            except PermissionError:pass
            else:raise AssertionError('Out-of-scope data/task accepted')
        from candidates import Candidate
        model=Candidate(c.text,'ollama',response_metadata={'expected_name':'priority'})
        try:runner.run_task(model,p,'full')
        except PermissionError:pass
        else:raise AssertionError('Unapproved model execution accepted')
        write(directory/'task_records.json',tasks)
        result={'status':'PASS','directory':str(directory),'images':images,'isolation_checks':len(checks),
                'task_checks':len(tasks),'scope_refusals':4,'policy_sha256':file_hash(PROJECT/'phase1b/phase1c/policy.json'),
                'all_cleanup_verified':all(r['cleanup_verified'] for r in tasks),
                'checks':checks,'wall_seconds':perf_counter()-start,'generated_sources_executed':0,
                'layer_audit_sha256':file_hash(directory/'image_layer_audit.json')}
        write(directory/'summary.json',result);write(ROOT/'validation.json',result)
        print(json.dumps({k:v for k,v in result.items() if k!='checks'},indent=2))
    except Exception as exc:
        write(directory/'summary.json',{'status':'FAIL','error':str(exc),'checks':checks,'completed_tasks':len(tasks)})
        raise

if __name__=='__main__':main()
