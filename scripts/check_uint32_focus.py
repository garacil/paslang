#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Check CRC width, UInt32 bounds, typed memory XOR and width/tune selection.

Usage: check_uint32_focus.py COMPILER BUILDDIR [QEMU] [options].
Every selected case runs on both targets with inline0/40 and normal/stress GC.
Actual inline0 ELF selection is checked independently of exact output/status.
"""
import argparse,hashlib,json,os,re,shutil,sys,tempfile
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent.parent
import check_uint32_tune_codegen as tune
sys.path.insert(0,str(ROOT/'scripts/bench'))
import metadata_scope as scope
CASES=('crc32width','uint32bounds','uint32memxor','uint32tune')
FAULTS=((255,0,127,35),(511,0,255,39),(256,0,255,43),(256,0,255,47),(-1,0,255,51),(-1,0,255,55),(0,1,255,59))
MARKERS=('FAIL-MASK128','FAIL-MASK511','FAIL-UNMASKED','FAIL-FULLWIDTH','FAIL-SIGNED','FAIL-SIGNEDMASK','FAIL-BYTEWRAP')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def item(path):
 p=Path(path);st=p.stat()
 return {'sha256':sha(p),'bytes':st.st_size,'mode':st.st_mode&0o777,'resolved':str(p.resolve())}
def snapshot(paths):return {str(p):item(p) for p in sorted(set(map(Path,paths)))}
def after(keys):return {name:item(name) if Path(name).is_file() else None for name in keys}
def exact_fault(k):
 index,low,high,line=FAULTS[k-1]
 return ('paslang: index '+str(index)+' out of range ['+str(low)+'..'+str(high)+'] at line '+str(line)+'\n').encode()
def artifacts(program):
 paths=[program,*[program.with_suffix(x) for x in ('.s','.o','.link','.ld')]]
 if not all(p.is_file() for p in paths):raise RuntimeError('compiler artifact missing: '+str(program))
 return snapshot(paths)
def linked_inputs(program,sdk,stem):
 lines=program.with_suffix('.link').read_text().splitlines()
 if len(lines)<6 or lines[0]!='-o' or lines[2:4]!=['--gc-sections','-T']:raise RuntimeError('malformed link receipt: '+str(program))
 result={}
 for entry in lines[6:]:
  obj=Path(entry);obj=(obj if obj.is_absolute() else ROOT/obj).resolve()
  if not obj.is_relative_to(sdk):raise RuntimeError('linked object escaped selected SDK: '+str(obj))
  pi=sdk/(obj.stem.lower()+'.pi')
  if not pi.is_file():raise RuntimeError('linked unit lacks selected SDK interface: '+str(obj))
  result.update(snapshot((obj,pi)))
 required={'crc32width':('sysutils','pashash'),'uint32bounds':('sysutils',),'uint32memxor':('sysutils','paslib'),'uint32tune':()}[stem]
 for name in required:
  if not any(Path(path).suffix=='.o' and Path(path).stem.lower()==name for path in result):raise RuntimeError('required linked unit absent: '+name)
 return result

def bounds_codegen(text,arch):
 bodies=tune.functions(text);observations={};issues=[]
 safe=('safe256','saferaw','safewrap')
 checked=('mask128','mask511','unmasked','fullwidthmask','signedindex','signedmask','bytewrap')
 for name in safe+checked:
  matches=[body for symbol,body in bodies.items() if re.fullmatch(r'p_f\.0_[0-9]+_'+name,symbol)]
  if len(matches)!=1:issues.append(name+': missing or duplicate body');continue
  body=matches[0];calls=[row for row in body['instructions'] if re.search(r'<rt_boundsfail(?:[+>])',row['args'])]
  observations[name]={'entry':body['entry'],'bounds_failure_branches':calls}
  if bool(calls)!=(name in checked):issues.append(name+': bounds check selection differs')
 return {'ok':not issues,'issues':issues,'functions':observations}

def memory_codegen(text,arch):
 bodies=tune.functions(text);observations={};issues=[]
 for name in ('first7','second7','third7','addressalias7','byte7','word7','wide7','narrowwide7'):
  matches=[body for symbol,body in bodies.items() if re.fullmatch(r'p_f\.0_[0-9]+_'+name,symbol)]
  if len(matches)!=1:issues.append(name+': missing or duplicate body')
  else:observations[name]=matches[0]
 if len(observations)!=8:return {'ok':False,'issues':issues,'functions':observations}
 def ins(name):return observations[name]['instructions']
 def parts(row):return [p.strip() for p in row['args'].split('#',1)[0].rsplit(',',1)]
 def reg32(r):return re.fullmatch(tune.REG32,r) is not None
 def register(r):return reg32(r) or re.fullmatch(tune.REG64,r) is not None
 def physical(r):
  if not register(r):return None
  r=r[1:]
  if r.startswith('e'):return 'r'+r[1:]
  return r[:-1] if r.endswith('d') else r
 def references(memory,r):return physical(r) in [physical(x) for x in re.findall(r'%[a-z0-9]+',memory)]
 if arch=='amd64':
  fast=[];sequences={}
  for name in ('first7','second7','third7'):
   body=ins(name)
   for i in range(len(body)-2):
    copy,shift,xor=body[i:i+3];a,b,c=parts(copy),parts(shift),parts(xor)
    if len(a)!=2 or len(b)!=2 or len(c)!=2:continue
    if (copy['op'] in ('mov','movl') and all(reg32(x) for x in a) and
        shift['op'] in ('shr','shrl') and tune.immediate(b[0])==7 and b[1]==a[1] and
        xor['op'] in ('xor','xorl') and '(' in c[0] and c[1]==a[1] and
        not references(c[0],c[1])):
     fast.append(name);sequences[name]=body[i:i+3];break
  fallback=ins('addressalias7');load_first=None
  # The alias path deliberately keeps UInt32Operand's ordinary shift route.
  # Its RHS may use SHR r64 or SHR r32: source storage is held UInt32, and
  # either yields the same low32 for count7. The LHS still reads exactly4.
  for i in range(len(fallback)-3):
   load,copy,shift,xor=fallback[i:i+4];a,b,c,d=parts(load),parts(copy),parts(shift),parts(xor)
   if any(len(x)!=2 for x in (a,b,c,d)):continue
   if (load['op'] in ('mov','movl') and '(' in a[0] and reg32(a[1]) and references(a[0],a[1]) and
       copy['op'] in ('mov','movl','movq') and all(register(x) for x in b) and
       shift['op'] in ('shr','shrl','shrq') and tune.immediate(c[0])==7 and register(c[1]) and physical(b[1])==physical(c[1]) and
       xor['op'] in ('xor','xorl') and all(reg32(x) for x in d) and
       physical(d[0])==physical(c[1]) and physical(d[1])==physical(a[1]) and
       physical(b[0])!=physical(a[1]) and physical(c[1])!=physical(a[1])):
    load_first={'sequence':fallback[i:i+4],'shift_width':32 if reg32(c[1]) else 64};break
  if not fast:issues.append('no actual typed4 MOVL/SHRL7/memory-XOR32 fast form')
  if load_first is None:issues.append('no dataflow-bound typed4 load-first ordinary SHR7/register-XOR32 fallback')
  shape={'memory_xor_fast_functions':fast,'fast_sequences':sequences,'computed_address_load_first':load_first}
 else:
  shifted=[]
  for name in ('first7','second7','third7'):
   if any(row['op']=='eor' and re.fullmatch(r'w[0-9]+,\s*w[0-9]+,\s*w[0-9]+,\s*lsr\s*#(?:7|0x7)',row['args'].split('//',1)[0].strip()) for row in ins(name)):shifted.append(name)
  if len(shifted)!=3:issues.append('typed4 ARM shifted-W XOR selection differs')
  shape={'shifted_w_xor_functions':shifted}
 return {'ok':not issues,'issues':issues,'functions':observations,'shape':shape}


def main():
 parser=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
 parser.add_argument('compiler');parser.add_argument('builddir');parser.add_argument('qemu',nargs='?')
 parser.add_argument('--units-amd64');parser.add_argument('--units-arm64')
 parser.add_argument('--out',help='fresh retained output directory')
 parser.add_argument('--target',choices=('all','amd64','arm64'),default='all')
 parser.add_argument('--case',action='append',choices=CASES,help='bounded selection; default all four cases')
 parser.add_argument('--role',choices=('baseline','candidate','mutant'),default='candidate')
 parser.add_argument('--expected-version',help='optional exact release token')
 parser.add_argument('--objdump-amd64',default='objdump');parser.add_argument('--objdump-arm64',default='aarch64-linux-gnu-objdump')
 options=parser.parse_args()
 def executable(value):
  path=Path(shutil.which(str(value)) or value).resolve()
  if not path.is_file():raise RuntimeError('executable absent: '+str(value))
  return path
 builddir=Path(options.builddir).resolve();compiler=executable(options.compiler)
 sdks={'amd64':Path(options.units_amd64 or builddir).resolve(),'arm64':Path(options.units_arm64 or builddir/'a64').resolve()}
 if options.out:
  out=Path(options.out).resolve()
  if out.exists():parser.error('fresh output directory required; retain previous failures')
  out.mkdir(parents=True)
 else:
  builddir.mkdir(parents=True,exist_ok=True);out=Path(tempfile.mkdtemp(prefix='check-uint32-focus-',dir=builddir))
 cases=list(dict.fromkeys(options.case or CASES))
 profiles=[(arch,cpu,inline) for arch,cpus in (('amd64',('base','native')),('arm64',('base','max'))) if options.target in ('all',arch) for cpu in cpus for inline in (0,40)]
 qemu=executable(options.qemu or builddir/'qemu-aarch64') if options.target!='amd64' else None
 dumps={arch:executable(options.objdump_amd64 if arch=='amd64' else options.objdump_arm64) for arch in sdks if options.target in ('all',arch)}
 env={k:v for k,v in os.environ.items() if k not in scope.CONTROL_KEYS and not k.startswith('PASLANG_')}
 env.setdefault('PATH',os.defpath);env.update(LC_ALL='C',PYTHONDONTWRITEBYTECODE='1')
 inputs=[Path(__file__),ROOT/'scripts/check_uint32_tune_codegen.py',ROOT/'scripts/bench/metadata_scope.py',compiler,*dumps.values(),*([qemu] if qemu else [])]
 for stem in cases:inputs.extend((ROOT/'testdata'/(stem+'.paslang'),ROOT/'testdata'/(stem+'.out')))
 inputs.extend((ROOT/'src').rglob('*.paslang'))
 for arch,sdk in sdks.items():
  if options.target in ('all',arch):inputs.extend(p for p in sdk.rglob('*') if p.is_file() and p.suffix in ('.pi','.o') and not p.is_relative_to(out))
 expected_builds=len(profiles)*len(cases);expected_runs=len(profiles)*(2*len(cases)+(7 if 'uint32bounds' in cases else 0))
 record={'kind':'uint32-focus-v1','role':options.role,'ok':False,'complete':False,'performance_verdict':None,'compiler':str(compiler),'cases':cases,'profiles':profiles,
  'expected_builds':expected_builds,'expected_executions':expected_runs,'inputs_before':{},'commands':[],'builds':[],'executions':[],'codegen':[],'errors':[]}
 def save():
  signals=scope.received_signals()
  if signals:
   message='cancellation received: '+str(signals)
   if message not in record['errors']:record['errors'].append(message)
   record['ok']=False
  record['received_signals']=signals;scope.save(out/'results.json',record)
 def fail(message):record['errors'].append(message);save()
 def command(argv,label,timeout=180,environment=None):
  scope.check_stop();argv=list(map(str,argv));folder=out/(label+'.scope');environment=env if environment is None else environment
  row={'label':label,'command':argv,'cwd':str(ROOT),'scope':str(folder),'status':'pending'};record['commands'].append(row);save()
  result=scope.invoke(argv,folder,ROOT,environment,timeout,grace=2,cleanup_timeout=5)
  row.update(status=result['status'],receipt_sha256=sha(folder/'result.json'),cleanup=result['cleanup'],signals=result['received_signals']);save()
  if not result['cleanup'].get('ok') or result.get('received_signals') or result.get('signals') or result.get('reason') is not None:raise RuntimeError('owned cleanup/cancellation/deadline failure: '+label)
  scope.validate_receipt(folder,argv,ROOT,environment);row['validated']=True;save();scope.check_stop()
  return result,(folder/'stdout').read_bytes(),(folder/'stderr').read_bytes()
 try:
  record['inputs_before']=snapshot(inputs);save()
  if 'crc32width' in cases and (ROOT/'testdata/crc32width.out').read_bytes()!=b'crc32-width 9256 0\n':raise RuntimeError('CRC oracle changed')
  if 'uint32tune' in cases and tune.expected_output()!=(ROOT/'testdata/uint32tune.out').read_bytes():raise RuntimeError('independent width/tune oracle differs')
  if 'uint32bounds' in cases:
   source=(ROOT/'testdata/uint32bounds.paslang').read_text().splitlines()
   for marker,(_,_,_,line) in zip(MARKERS,FAULTS):
    if [n for n,text in enumerate(source,1) if '{ '+marker+' }' in text]!=[line]:raise RuntimeError('fault source marker moved: '+marker)
  version,stdout,stderr=command([compiler,'-v'],'compiler-version',60)
  record['observed_version']=stdout.decode('utf-8','replace')
  if version['status']!=0 or stderr or not stdout.startswith(b'paslangc ') or (options.expected_version and options.expected_version not in stdout.decode().split()):raise RuntimeError('compiler version or diagnostics differ')
  for arch,cpu,inline in profiles:
   sdk=sdks[arch]
   for stem in cases:
    tag='-'.join(map(str,(stem,arch,cpu,inline)));program=out/tag
    result,stdout,stderr=command([compiler,'-target',arch,'-cpu',cpu,'-inline',str(inline),'-Fu',sdk,'-o',program,ROOT/'testdata'/(stem+'.paslang')],tag+'-build')
    build={'tag':tag,'profile':[arch,cpu,inline],'case':stem,'sdk':str(sdk),'clean_diagnostics':result['status']==0 and stdout==b'' and stderr==b''};record['builds'].append(build);save()
    if not build['clean_diagnostics']:fail(tag+': compile status or diagnostics differ');continue
    build['artifacts']=artifacts(program);build['linked_inputs']=linked_inputs(program,sdk,stem);save()
    result,text,stderr=command([dumps[arch],'-dw','-l','--no-show-raw-insn',program],tag+'-elf',60)
    if result['status']!=0 or stderr:fail(tag+': ELF inspection differs')
    if inline==0 and stem!='crc32width' and result['status']==0 and not stderr:
     gate={'uint32bounds':bounds_codegen,'uint32memxor':memory_codegen,'uint32tune':tune.check}[stem](text.decode('utf-8','strict'),arch)
     record['codegen'].append({'tag':tag,'case':stem,'arch':arch,'cpu':cpu,'observation':gate})
     if options.role!='baseline' and not gate['ok']:fail(tag+': actual ELF selection requirement differs')
     save()
    prefix=[] if arch=='amd64' else [qemu,'-cpu','cortex-a53' if cpu=='base' else 'max']
    modes=[('normal',(),env),('stress',(),dict(env,PASLANG_GCSTRESS='1',PASLANG_GCVERIFY='1',PASLANG_GCPOISON='1'))]
    if stem=='uint32bounds':modes.extend(('fatal'+str(k),(str(k),),env) for k in range(1,8))
    for mode,args,environment in modes:
     result,stdout,stderr=command([*prefix,program,*args],tag+'-'+mode,600 if arch=='arm64' else 180,environment)
     want=(ROOT/'testdata'/(stem+'.out')).read_bytes() if not args else b'';error=exact_fault(int(args[0])) if args else b'';status=1 if args else 0
     matches=result['status']==status and stdout==want and stderr==error
     record['executions'].append({'tag':tag,'mode':mode,'status':result['status'],'expected_status':status,'exact_oracle_match':matches,
      'expected_stdout_sha256':hashlib.sha256(want).hexdigest(),'expected_stderr_sha256':hashlib.sha256(error).hexdigest()})
     if not matches:fail(tag+'/'+mode+': exact output/status differs')
     save()
    print(tag,'retained',flush=True)
 except BaseException as error:fail(type(error).__name__+': '+str(error))
 finally:
  record['inputs_after']=after(record['inputs_before']);record['inputs_unchanged']=record['inputs_before']==record['inputs_after']
  linked={path:value for b in record['builds'] for path,value in b.get('linked_inputs',{}).items()};built={path:value for b in record['builds'] for path,value in b.get('artifacts',{}).items()}
  record['linked_after']=after(linked);record['linked_unchanged']=linked==record['linked_after'];record['artifacts_after']=after(built);record['artifacts_unchanged']=built==record['artifacts_after']
  record['compiled_all']=len(record['builds'])==expected_builds and all(b['clean_diagnostics'] for b in record['builds'])
  record['executed_all']=len(record['executions'])==expected_runs and all(r['exact_oracle_match'] for r in record['executions'])
  record['codegen_complete']=len(record['codegen'])==sum(inline==0 for _,_,inline in profiles)*sum(stem!='crc32width' for stem in cases)
  record['complete']=True;record['ok']=not record['errors'] and record['inputs_unchanged'] and record['linked_unchanged'] and record['artifacts_unchanged'] and record['compiled_all'] and record['executed_all'] and record['codegen_complete'];save()
 print('UInt32 focus '+('ok' if record['ok'] else 'FAILED')+': '+str(out/'results.json'),flush=True)
 return 0 if record['ok'] else 1
if __name__=='__main__':
 with scope.signal_scope():
  status=main();scope.check_stop();raise SystemExit(status)
