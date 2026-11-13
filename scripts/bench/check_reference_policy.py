#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Compiler-free Go CPU capability, dual-parser and refusal controls."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import copy
import hashlib
import json
import types
import tempfile
import time
import os
import struct
from unittest.mock import patch
import reference_policy as policy
import metadata_scope


def require(value,message):
    if not value: raise AssertionError(message)


def synthetic_capabilities(erms=False,fsrm=False,active=None,module=policy):
    """Labeled fixture; real metadata discovery is tested separately."""
    native = {"internal":{n:False for n in module.GO_FIELDS},"version":"go1.27.3-X:nodwarf5",
        "goarch":"amd64","goos":"linux","cpuid":{"0":[7,0,0,0],"1":[0,0,0,1<<26],"7_0":[0,(1<<9) if erms else 0,0,(1<<4) if fsrm else 0],"80000000":[0x80000000,0,0,0]}}
    native["internal"].update(HasERMS=erms,HasFSRM=fsrm,HasOSXSAVE=True,HasRDTSCP=True,HasSHA=True,HasAES=True,HasAVX=True,HasAVX2=True)
    if active: native["internal"][active]=True
    options,reason=module._selection(native)
    base=copy.deepcopy(native) if not reason else None
    if base:
        for name in module.GO_OPTION_FIELDS.values(): base["internal"][name]=False
        base["internal"]["HasERMS"]=erms
        base["internal"]["HasAVX512"]=False
    driver={"path":"/synthetic/go","sha256":module.GO_DRIVER_SHA256}
    environment={"GOROOT":"/synthetic/goroot","GOVERSION":"go1.27.3-X:nodwarf5","GOEXPERIMENT":"nodwarf5","GOTOOLDIR":"/synthetic/tools","GOHOSTARCH":"amd64","GOHOSTOS":"linux"}
    def observation(command,stdout,controls=""):
        return {"command":command,"cwd":"/synthetic/probe","environment":{"GODEBUG":controls,"GOAMD64":"v1"},"status":0,"stdout":stdout,"stderr":"","supervision":{"program_status":0,"cleanup":{"ok":True},"receipt":"/synthetic/receipt"}}
    observations=[observation([driver["path"],"env"],json.dumps(environment)),observation([driver["path"],"build"],""),observation(["/synthetic/probe"],json.dumps(native))]
    if base: observations.append(observation(["/synthetic/probe"],json.dumps(base),",".join(options)))
    observations.append({"probe_binary":{"path":"/synthetic/probe","sha256":"0"*64}})
    proof={"format":module.GO_CAP_FORMAT,"policy_id":module.GO_POLICY,"compiler":{"driver":driver,"tools":{n:{"path":"/synthetic/tools/"+n,"sha256":v} for n,v in module.GO_TOOL_SHA256.items()}},
        "sources":{n:{"path":"/synthetic/goroot/src/"+n,"sha256":v} for n,v in module.GO_SOURCE_SHA256.items()},
        "sdk":{"goroot":"/synthetic/goroot","roots":["src","pkg/include","pkg/tool/linux_amd64"],"files":1,"bytes":1,"sha256":"1"*64},
        "go_environment":environment,"probe_sources":{n:hashlib.sha256((Path(module.__file__).parent/n).read_bytes()).hexdigest() for n in module.PROBE_INPUTS},
        "native_state":native,"base_state":base,"runtime_cpu_options":options,"base_supported":not reason,"baseline_reason":reason,"observations":observations}
    proof["identity_sha256"]=module._digest(module._identity(proof))
    return proof


def reseal(proof,module=policy):
    proof["identity_sha256"]=module._digest(module._identity(proof))
    return proof


def refuses(function,message):
    try: function()
    except ValueError: return
    raise AssertionError(message)


def policy_controls(module=policy):
    for erms in (False,True):
        p=synthetic_capabilities(erms=erms,module=module)
        module.validate_go_capabilities(p)
        env=module.go_runtime_environment("base",None,{"GODEBUG":"cpu.all=on,cpu.fsrm=on,gctrace=0","GOAMD64":"v4"},p)
        expected="gctrace=0,cpu.all=off"+(",cpu.erms=on" if erms else "")
        require(env["GODEBUG"]==expected and env["GOAMD64"]=="v1","detected-only ERMS/alloff selection differs")
        for fsrm in (False,True):
            q=synthetic_capabilities(erms=erms,fsrm=fsrm,module=module)
            require(q["base_supported"]== (not fsrm),"true FSRM passed baseline selection")
            if fsrm: refuses(lambda:module.go_runtime_environment("base",capabilities=q),"true FSRM accepted")
    for field in module.GO_UNCONTROLLED_ISA:
        p=synthetic_capabilities(active=field,module=module)
        require(not p["base_supported"] and field in p["baseline_reason"],"uncontrolled optional ISA silently accepted")
        refuses(lambda:module.go_runtime_environment("base",capabilities=p),"unsafe optional ISA accepted")
    source={"GODEBUG":"cpu.all=off,cpu.erms=on,cpu.fsrm=on,cpu.aes=off,gctrace=0","GOAMD64":"v4"}
    native=module.go_runtime_environment("native","v3",source)
    require(native["GODEBUG"]=="gctrace=0" and native["GOAMD64"]=="v3","ordinary native CPU controls leaked")
    for cpu,level,target in (("base",None,"v1"),("native","v3","v3")):
        env=module.go_build_environment("/synthetic/build",cpu,level,source)
        require(env["GODEBUG"]=="gctrace=0" and env["GOAMD64"]==target,"compiler host masked or target changed")
    require(source["GOAMD64"]=="v4" and "cpu.fsrm=on" in source["GODEBUG"],"caller environment mutated")
    refuses(lambda:module.go_runtime_environment("base"),"missing capabilities accepted")
    p=synthetic_capabilities(module=module)
    mutations=[lambda q:q.update(identity_sha256="f"*64),
        lambda q:q["compiler"]["driver"].update(sha256="f"*64),
        lambda q:q["sources"]["internal/cpu/cpu.go"].update(sha256="f"*64),
        lambda q:q["go_environment"].update(GOEXPERIMENT="simd"),
        lambda q:q["probe_sources"].update({"go_cpu_probe.go":"f"*64}),
        lambda q:q.update(runtime_cpu_options=[]),
        lambda q:q.update(runtime_cpu_options=["cpu.all=off","cpu.erms=on"]),
        lambda q:(q["base_state"]["internal"].update(HasRDTSCP=True),q["observations"][3].update(stdout=json.dumps(q["base_state"]))),
        lambda q:q["native_state"]["internal"].update(HasERMS=True),
        lambda q:q["base_state"]["internal"].update(HasAVX2=0),
        lambda q:q.update(observations=[]),
        lambda q:q["observations"][2].update(stderr='GODEBUG sys/cpu: unknown cpu feature "rdtscp"\n'),
        lambda q:q["observations"][2].update(status=7),
        lambda q:q["observations"][2].update(stdout="{}"),
        lambda q:q["observations"][0]["environment"].update(GODEBUG="cpu.all=off"),
        lambda q:q["observations"][3]["environment"].update(GODEBUG=""),
        lambda q:q.update(compiler="bad"),lambda q:q.update(sdk={}),lambda q:q.update(sources=None)]
    for index,mutate in enumerate(mutations):
        q=copy.deepcopy(p);mutate(q)
        if index!=0: reseal(q,module)
        refuses(lambda:module.validate_go_capabilities(q),"malformed/unsafe proof accepted #"+str(index))
    apic=copy.deepcopy(p)
    apic["native_state"]["cpuid"]["1"][1] |= 3<<24
    apic["base_state"]["cpuid"]["1"][1] |= 9<<24
    apic["observations"][2]["stdout"]=json.dumps(apic["native_state"])
    apic["observations"][3]["stdout"]=json.dumps(apic["base_state"])
    reseal(apic,module)
    require(apic["identity_sha256"]==p["identity_sha256"],"topology APIC ID polluted stable capability identity")
    module.validate_go_capabilities(apic)
    changed=copy.deepcopy(apic);changed["base_state"]["cpuid"]["1"][2] ^= 1
    reseal(changed,module)
    refuses(lambda:module.validate_go_capabilities(changed),"feature-bit change mistaken for topology")
    module.validate_go_version("go version go1.27.3-X:nodwarf5 linux/amd64")
    for text in ("go1.27.3","go1.27.2","go1.27.3-X:simd"):
        refuses(lambda:module.validate_go_version(text),"unreviewed version accepted")
    with patch.object(module,"_file",side_effect=ValueError("changed actual tool")):
        refuses(lambda:module.validate_go_capabilities(p,"/changed/go"),"actual compiler recheck omitted")


def parser_controls():
    # Two independent parser models, from the source-reviewed vocabularies.
    # cpu.all=off skips Required entries; a named unknown selector is an error.
    internal=set(policy.GO_OPTION_FIELDS)
    xsys={"adx","aes","avx","avx2","avx512","avx512f","avx512cd","avx512er","avx512pf","avx512vl","avx512bw","avx512dq","avx512ifma","avx512vbmi","avx512vnniw","avx5124fmaps","avx512vpopcntdq","avx512vpclmulqdq","avx512vnni","avx512gfni","avx512vaes","avx512vbmi2","avx512bitalg","avx512bf16","amxtile","amxint8","amxbf16","bmi1","bmi2","cx16","erms","fma","osxsave","pclmulqdq","popcnt","rdrand","rdseed","sse3","sse41","sse42","ssse3","avxifma","avxvnni","avxvnniint8","sse2"}
    for erms in (False,True):
        controls=synthetic_capabilities(erms=erms)["runtime_cpu_options"]
        for vocab,required in ((internal,set()),(xsys,{"sse2"})):
            state={n:True for n in vocab};state["erms"]=erms
            for control in controls:
                key,value=control[4:].split("=")
                require(key=="all" or key in vocab,"unsupported shared selector")
                if key=="all":
                    state={n:n in required for n in vocab}
                else:
                    require(value!="on" or erms and key=="erms","absent capability forced on")
                    state[key]=value=="on"
            require({n for n,v in state.items() if v}==required|({"erms"} if erms else set()),"dual-parser effective mask differs")
    require({"rdtscp","sha","vpclmulqdq","fsrm"}.isdisjoint(xsys),"unknown-selector control missing")


def artifact_controls(module=policy):
    with tempfile.TemporaryDirectory(prefix='paslang-go-elf-') as temporary:
        path=Path(temporary)/'artifact'
        def image(dynamic=False,interp=False):
            data=bytearray(1024)
            ident=b'\x7fELF\x02\x01\x01'+bytes(9)
            count=1+int(dynamic)+int(interp)
            struct.pack_into('<16sHHIQQQIHHHHHH',data,0,ident,2,62,1,0x400200,64,0,0,64,56,count,0,0,0)
            struct.pack_into('<IIQQQQQQ',data,64,1,5,0,0x400000,0,len(data),len(data),4096)
            index=1
            if interp:
                text=b'/lib64/ld-linux-x86-64.so.2\x00';data[300:300+len(text)]=text
                struct.pack_into('<IIQQQQQQ',data,64+56*index,3,4,300,0x400000+300,0,len(text),len(text),1);index+=1
            if dynamic:
                struct.pack_into('<IIQQQQQQ',data,64+56*index,2,6,400,0x400000+400,0,64,64,8)
                for n,pair in enumerate(((1,0),(5,0x400000+600),(10,10),(0,0))):struct.pack_into('<qQ',data,400+n*16,*pair)
                data[600:610]=b'libc.so.6\x00'
            return data
        for dynamic,interp in ((False,False),(False,True),(True,False),(True,True)):
            data=image(dynamic,interp);path.write_bytes(data)
            metadata=module.go_binary_metadata(path)
            require(metadata['needed']==(['libc.so.6'] if dynamic else []) and bool(metadata['interpreter'])==interp and metadata['has_dynamic_segment']==dynamic,'ELF provider evidence differs')
            module.require_go_artifact_capabilities('native',metadata)
            if dynamic or interp:refuses(lambda:module.require_go_artifact_capabilities('base',metadata),'external Go provider passed baseline')
            else:module.require_go_artifact_capabilities('base',metadata)
        data=image();data[4]=1;path.write_bytes(data)
        refuses(lambda:module.go_binary_metadata(path),'ELF32 passed amd64 artifact proof')
        data=image();struct.pack_into('<Q',data,32,1000);path.write_bytes(data)
        refuses(lambda:module.go_binary_metadata(path),'out-of-file program table accepted')
        data=image(True,True);struct.pack_into('<Q',data,400+16+8,0xffffffffffffffff);path.write_bytes(data)
        refuses(lambda:module.go_binary_metadata(path),'unmapped dynamic strings accepted')
        path.write_bytes(image());metadata=module.go_binary_metadata(path);metadata['interpreter']='forged'
        refuses(lambda:module.require_go_artifact_capabilities('native',metadata),'forged Go artifact provider evidence accepted')


def mutant_controls():
    source=Path(policy.__file__).read_text()
    changes=[("fsrm",'if flags["HasFSRM"]:', 'if False:'),
        ("uncontrolled",'if active:', 'if False:'),
        ("forced-erms",'if flags["HasERMS"] else []','if True else []'),
        ("host-mask",'if p and not p.startswith("cpu.")','if p'),
        ("effective-state",'if base!=expected:', 'if False:'),
        ("stderr",'or row["stderr"]!=""','or False'),
        ("source-pin",'sources[k].get("sha256")!=v','False')]
    names=[]
    for name,old,new in changes:
        require(old in source,"mutant anchor absent: "+name)
        module=types.ModuleType("policy_mutant_"+name);module.__file__=policy.__file__
        exec(compile(source.replace(old,new,1),"<"+name+">","exec"),module.__dict__)
        try: policy_controls(module)
        except (AssertionError,ValueError): names.append(name)
        else: raise AssertionError("policy mutant survived: "+name)
    old='if cpu=="base" and (metadata["has_dynamic_segment"] or metadata["interpreter"] or metadata["needed"]):'
    require(old in source,'provider mutant anchor missing')
    module=types.ModuleType('provider_mutant');module.__file__=policy.__file__
    exec(compile(source.replace(old,'if False:',1),'<provider-mutant>','exec'),module.__dict__)
    try:artifact_controls(module)
    except AssertionError:names.append('external-provider')
    else:raise AssertionError('Go provider refusal mutant survived')
    return names


def main():
    policy_controls();parser_controls();artifact_controls();names=mutant_controls()
    print(json.dumps({"ok":True,"groups":["detected-REP","all-uncontrolled-ISA","host-target-separation","strict-proof-identity","effective-state","raw-CPUID","dual-parser-RequiredSSE2","diagnostics","actual-input-recheck","topology-vs-features","actual-ELF-provider-refusal"],"caught_mutants":names}))
    return 0


if __name__=="__main__":raise SystemExit(main())
