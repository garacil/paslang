#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Source-pinned Go CPU policy and read-only capability discovery.

The two Go CPU parsers have different vocabularies. Shared cpu.all=off is
safe only with measured REP preservation: restore ERMS iff truly present;
refuse true FSRM (vendored x/sys has no such option). Internal non-option
ISA fields are recorded and conservatively refused when true. OSXSAVE is
an OS state/detection control, not an accelerated workload selector.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import threading
import tempfile
import struct
from metadata_scope import invoke as scoped_invoke

GO_POLICY = "go1.27.3-amd64-v1-dual-parser-capabilities-v2"
GO_REVIEWED_VERSION = "go1.27.3"
GO_REVIEWED_VERSION_TOKENS = ("go1.27.3-X:nodwarf5",)
GO_DRIVER_SHA256 = "21401c8d2dae2e6db0d756f7b9ae5a885ac6c14882cbbe521c6f49b184da8402"
GO_TOOL_SHA256 = {
    "compile":"9e7c2f2d98036e47ecba57b7dc3556cd82bcf24e1f8c8bba5a9881b20951b6c5",
    "asm":"2d6ce7f1c728010cee15427f36f8b5d9bbac83bce91faa8997498c08e208099d",
    "link":"97df419b7cf8f4bb8e76c3623b8a1d371c6818533c4be04f0a3563ff6169843d",
}
GO_SOURCE_SHA256 = {'internal/cpu/cpu.go': '9af4310772f84d92f2a98e9f16e6553fdbefc4ce6286e0f508121e6c8819faf7', 'internal/cpu/cpu_x86.go': '395ce0d3004df63df376585519bc1b46303b206415c1915ab80b7bead155e26a', 'internal/cpu/cpu_x86.s': 'ee4dca9916b29475e600d85f71f0dfd134496d153c77d20a643b139cc6e18fed', 'vendor/golang.org/x/sys/cpu/cpu.go': 'b56854737e8d803d582232f9790f7dda2d8ff69e5982f6cdbdd2a150be540922', 'vendor/golang.org/x/sys/cpu/cpu_x86.go': '6a9cdf0eca762b62d0e49e1f3bc9b5c68f23fecbdb888d12ef27bc32bc3893b9', 'runtime/proc.go': '40d15ce858cf058cff92606001a29ee1689db88c121a2f0c283163a0d64a7375', 'runtime/cpuflags_amd64.go': 'b9aa3542d35b84d5279030a603acfade2563c67b970e99d5d89ebf64742383f6', 'runtime/asm_amd64.s': '71da1bf81ac9a5972ab4ddaccb0f2bab4c9272a888991a34721e520513f458bd', 'internal/buildcfg/exp.go': '5825d40b47471bca28a00c0c19215930efef22b758120b6d972da1a955f21fa0', 'internal/buildcfg/zbootstrap.go': '5fb530ddd25775785f71bcf4a566101f3b7506f78200a1d69a6a0dc898cd84b1'}
GO_OPTION_FIELDS = {
    "adx":"HasADX", "aes":"HasAES", "erms":"HasERMS", "fsrm":"HasFSRM",
    "pclmulqdq":"HasPCLMULQDQ", "rdtscp":"HasRDTSCP", "sha":"HasSHA",
    "vpclmulqdq":"HasAVX512VPCLMULQDQ", "popcnt":"HasPOPCNT",
    "sse3":"HasSSE3", "sse41":"HasSSE41", "sse42":"HasSSE42", "ssse3":"HasSSSE3",
    "avx":"HasAVX", "avx2":"HasAVX2", "bmi1":"HasBMI1", "bmi2":"HasBMI2",
    "fma":"HasFMA", "avx512f":"HasAVX512F", "avx512cd":"HasAVX512CD",
    "avx512bw":"HasAVX512BW", "avx512dq":"HasAVX512DQ", "avx512vl":"HasAVX512VL",
}
GO_BASE_DISABLED_FEATURES = tuple(k for k in GO_OPTION_FIELDS if k not in ("erms", "fsrm"))
GO_UNCONTROLLED_ISA = (
    "HasAVXVNNI", "HasAVX512GFNI", "HasAVX512VAES", "HasAVX512VNNI", "HasAVX512VBMI",
    "HasAVX512VBMI2", "HasAVX512BITALG", "HasAVX512VPOPCNTDQ", "HasGFNI", "HasVAES", "HasVPCLMULQDQ",
)
GO_FIELDS = tuple(GO_OPTION_FIELDS.values()) + GO_UNCONTROLLED_ISA + ("HasAVX512", "HasOSXSAVE")
GO_CAP_FORMAT = "paslang-go-cpu-capabilities-v1"
PROBE_INPUTS = ("go_cpu_probe.go","go_cpu_probe.s","reference_policy.py","metadata_scope.py","check_metadata_scope.py")


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _file(path):
    path = Path(path).resolve(strict=True)
    return {"path":str(path), "sha256":hashlib.sha256(path.read_bytes()).hexdigest()}


def go_level(cpu, native_level):
    if cpu == "base":
        return "v1"
    if cpu != "native" or native_level not in ("v1", "v2", "v3", "v4"):
        raise ValueError("native Go requires an explicitly reviewed GOAMD64 level")
    return native_level


def validate_go_version(version):
    if not isinstance(version, str) or not set(GO_REVIEWED_VERSION_TOKENS).intersection(version.split()):
        raise ValueError("Go CPU policy needs the exact reviewed go1.27.3-X:nodwarf5 toolchain")


def _clean(environment=None):
    env = dict(os.environ if environment is None else environment)
    env["GODEBUG"] = ",".join(p for p in env.get("GODEBUG", "").split(",") if p and not p.startswith("cpu."))
    return env


def go_build_environment(out, cpu, native_level, environment=None):
    env = _clean(environment)
    env.update(GOAMD64=go_level(cpu,native_level), GOARCH="amd64", GOOS="linux", GOFLAGS="",
               GOTOOLCHAIN="local", GOENV="off", GOEXPERIMENT="", GOWORK="off", GOCACHE=str(Path(out)/"gocache"))
    return env


def _sdk(goroot, inventory=None):
    """Content identity includes all std sources, assembly headers and Go tools."""
    root = Path(goroot).resolve(strict=True)
    rows = []
    for folder in ("src","pkg/include","pkg/tool/linux_amd64"):
        for path in sorted((root/folder).rglob("*")):
            if path.is_file():
                rows.append({"path":str(path.relative_to(root)),"bytes":path.stat().st_size,"sha256":_file(path)["sha256"]})
            elif path.is_symlink():
                raise ValueError("unresolved Go SDK symlink")
    result = {"goroot":str(root),"roots":["src","pkg/include","pkg/tool/linux_amd64"],
              "files":len(rows),"bytes":sum(row["bytes"] for row in rows),"sha256":_digest(rows)}
    if inventory is not None:
        Path(inventory).write_text(json.dumps(rows,indent=1)+"\n")
    return result


def _state(state):
    if not isinstance(state, dict) or set(state) != {"internal", "cpuid", "version", "goarch", "goos"}:
        raise ValueError("malformed Go effective CPU state")
    flags, leaves = state["internal"], state["cpuid"]
    if not isinstance(flags,dict) or set(flags) != set(GO_FIELDS) or any(type(v) is not bool for v in flags.values()):
        raise ValueError("malformed Go CPU boolean layout")
    if state["version"] != "go1.27.3-X:nodwarf5" or state["goarch"] != "amd64" or state["goos"] != "linux":
        raise ValueError("Go probe version/architecture mismatch")
    if not isinstance(leaves,dict) or not {"0","1","80000000"}.issubset(leaves):
        raise ValueError("missing raw CPUID evidence")
    if set(leaves)-{"0","1","7_0","7_1","80000000","80000001"} or any(
            not isinstance(v,list) or len(v)!=4 or any(type(n) is not int or not 0<=n<=0xffffffff for n in v) for v in leaves.values()):
        raise ValueError("malformed raw CPUID evidence")
    if ("7_0" in leaves) != (leaves["0"][0]>=7) or ("7_1" in leaves) != ("7_0" in leaves and leaves["7_0"][0]>=1):
        raise ValueError("inconsistent CPUID leaf coverage")
    if ("80000001" in leaves) != (leaves["80000000"][0]>=0x80000001) or not leaves["1"][3] & (1<<26):
        raise ValueError("missing mandatory SSE2/raw CPUID coverage")
    return flags


def _selection(native):
    flags = _state(native)
    leaf = native["cpuid"].get("7_0", [0,0,0,0])
    if flags["HasERMS"] != bool(leaf[1] & (1<<9)) or flags["HasFSRM"] != bool(leaf[3] & (1<<4)):
        raise ValueError("native REP state disagrees with raw CPUID")
    if flags["HasFSRM"]:
        return [], "true FSRM cannot be preserved by both reviewed Go CPU parsers"
    active = [n for n in GO_UNCONTROLLED_ISA if flags[n]]
    if active:
        return [], "uncontrolled optional ISA fields: " + ",".join(active)
    return ["cpu.all=off"] + (["cpu.erms=on"] if flags["HasERMS"] else []), ""


def _normalized_state(state):
    if state is None: return None
    leaves = {key:list(value) for key,value in state["cpuid"].items()}
    # AMD64 APM vol.3 E.3: CPUID(1).EBX[31:24] is the per-logical-CPU
    # LocalApicId. Retain raw bytes in observations, compare only capabilities.
    leaves["1"][1] &= 0x00ffffff
    return dict(state,cpuid=leaves)


def _identity(proof):
    result = {key:proof[key] for key in ("format","policy_id","compiler","sources","sdk","go_environment",
        "probe_sources","native_state","base_state","runtime_cpu_options","base_supported","baseline_reason")}
    for key in ("native_state","base_state"): result[key] = _normalized_state(proof[key])
    return result


def _validate_go_capabilities(capabilities, go_executable=None):
    """Pure validation by default; explicit tool argument rechecks real inputs.

    Actual discovery runs afresh per harness invocation, outside timed regions.
    This record is evidence from that discovery, not a user-issued certificate.
    """
    p = capabilities
    required = set(("format","policy_id","compiler","sources","sdk","go_environment","probe_sources",
                    "native_state","base_state","runtime_cpu_options","base_supported","baseline_reason","identity_sha256","observations"))
    if not isinstance(p,dict) or set(p)!=required or p["format"]!=GO_CAP_FORMAT or p["policy_id"]!=GO_POLICY:
        raise ValueError("missing/malformed source-bound Go capabilities")
    if p["identity_sha256"] != _digest(_identity(p)):
        raise ValueError("Go capability identity digest mismatch")
    compiler, sources, environment = p["compiler"], p["sources"], p["go_environment"]
    if (not isinstance(compiler,dict) or set(compiler)!={"driver","tools"} or
        compiler["driver"].get("sha256")!=GO_DRIVER_SHA256 or set(compiler["tools"])!=set(GO_TOOL_SHA256) or
        any(compiler["tools"][k].get("sha256")!=v for k,v in GO_TOOL_SHA256.items())):
        raise ValueError("Go compiler identity is not reviewed")
    if not isinstance(sources,dict) or set(sources)!=set(GO_SOURCE_SHA256) or any(sources[k].get("sha256")!=v for k,v in GO_SOURCE_SHA256.items()):
        raise ValueError("Go CPU/default-experiment sources are not reviewed")
    if not isinstance(environment,dict) or environment.get("GOVERSION")!="go1.27.3-X:nodwarf5" or environment.get("GOEXPERIMENT")!="nodwarf5" or environment.get("GOHOSTARCH")!="amd64" or environment.get("GOHOSTOS")!="linux":
        raise ValueError("unreviewed Go defaults/experiments")
    actual_probe = {name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in PROBE_INPUTS}
    if p["probe_sources"] != actual_probe:
        raise ValueError("Go capability probe source mismatch")
    sdk = p["sdk"]
    if (not isinstance(sdk,dict) or set(sdk)!={"goroot","roots","files","bytes","sha256"}
        or sdk["goroot"]!=environment["GOROOT"] or sdk["roots"]!=["src","pkg/include","pkg/tool/linux_amd64"]
        or type(sdk["files"]) is not int or sdk["files"]<1 or type(sdk["bytes"]) is not int or sdk["bytes"]<1
        or not isinstance(sdk["sha256"],str) or len(sdk["sha256"])!=64):
        raise ValueError("malformed Go SDK source/tool fingerprint")

    options, reason = _selection(p["native_state"])
    if p["runtime_cpu_options"]!=options or type(p["base_supported"]) is not bool or p["baseline_reason"]!=reason or p["base_supported"]!=(not reason):
        raise ValueError("Go baseline capability selection is inconsistent")
    if not reason:
        base = _state(p["base_state"])
        native = p["native_state"]["internal"]
        if _normalized_state(p["base_state"])["cpuid"]!=_normalized_state(p["native_state"])["cpuid"]:
            raise ValueError("Go native/base CPUID evidence differs")
        expected = dict(native)
        for field in GO_OPTION_FIELDS.values(): expected[field] = False
        expected["HasERMS"] = native["HasERMS"]
        expected["HasAVX512"] = False
        if base!=expected:
            raise ValueError("Go effective base state did not preserve REP or disable ISA options")
    elif p["base_state"] is not None:
        raise ValueError("unsupported Go baseline must not contain a certified effective state")
    observations = p["observations"]
    if not isinstance(observations,list) or len(observations) != (5 if not reason else 4):
        raise ValueError("missing Go probe observations")
    for row in observations[:-1]:
        if (not isinstance(row,dict) or set(row)!={"command","cwd","environment","status","stdout","stderr","supervision"}
            or type(row["status"]) is not int or row["status"]!=0 or row["stderr"]!=""
            or not isinstance(row["stdout"],str) or not isinstance(row["command"],list)
            or not all(isinstance(arg,str) for arg in row["command"])
            or not isinstance(row["supervision"],dict) or row["supervision"].get("program_status")!=0
            or row["supervision"].get("cleanup",{}).get("ok") is not True):
            raise ValueError("Go probe observation failed or emitted unexpected stderr")
    if json.loads(observations[0]["stdout"])!=environment or json.loads(observations[2]["stdout"])!=p["native_state"]:
        raise ValueError("Go probe state/metadata differs from observed stdout")
    if observations[0]["command"][0]!=compiler["driver"]["path"] or observations[1]["command"][:2]!=[compiler["driver"]["path"],"build"]:
        raise ValueError("Go capability observation used a different compiler")
    artifact = observations[-1]
    if not isinstance(artifact,dict) or set(artifact)!={"probe_binary"} or set(artifact["probe_binary"])!={"path","sha256"}:
        raise ValueError("Go probe artifact identity missing")
    for index in (2,3) if not reason else (2,):
        if observations[index]["command"]!=[artifact["probe_binary"]["path"]]:
            raise ValueError("Go native/base observations used a different probe artifact")
    for row in observations[:3]:
        if any(part.startswith("cpu.") for part in row["environment"].get("GODEBUG","").split(",")):
            raise ValueError("Go metadata compiler/native host was CPU masked")
    if not reason:
        if json.loads(observations[3]["stdout"])!=p["base_state"]:
            raise ValueError("Go base state differs from observed stdout")
        controls = [part for part in observations[3]["environment"].get("GODEBUG","").split(",") if part.startswith("cpu.")]
        if controls!=options:
            raise ValueError("Go effective-state observation used a different baseline mask")
    if go_executable is not None:
        if _file(go_executable)!=compiler["driver"]:
            raise ValueError("Go compiler changed after capability discovery")
        for item in [*compiler["tools"].values(), *sources.values()]:
            if _file(item["path"])!=item:
                raise ValueError("Go tool/source changed after capability discovery")
        if _sdk(environment["GOROOT"])!=sdk:
            raise ValueError("Go SDK source/header/tool inputs changed after capability discovery")
    return p


def validate_go_capabilities(capabilities, go_executable=None):
    try:
        return _validate_go_capabilities(capabilities,go_executable)
    except (KeyError,TypeError,AttributeError) as error:
        raise ValueError("malformed Go capability metadata") from error


def go_runtime_environment(cpu, native_level=None, environment=None, capabilities=None):
    if cpu not in ("native","base"):
        raise ValueError("Go CPU mode must be native or base")
    env = _clean(environment)
    if cpu=="base" or native_level is not None: env["GOAMD64"] = go_level(cpu,native_level)
    if cpu=="base":
        proof = validate_go_capabilities(capabilities)
        if not proof["base_supported"]: raise ValueError("Go baseline refused: "+proof["baseline_reason"])
        env["GODEBUG"] = ",".join(filter(None,[env["GODEBUG"],*proof["runtime_cpu_options"]]))
    return env


def _capture(command, env, cwd, observations, timeout=120):
    row = {"command":list(map(str,command)), "cwd":str(cwd), "environment":{k:env[k] for k in ("GODEBUG","GOAMD64","GOARCH","GOOS","GOENV","GOEXPERIMENT","GOTOOLCHAIN","GOFLAGS","GOWORK","GOCACHE") if k in env}}
    observations.append(row)
    receipt = Path(cwd)/("capture-"+str(len(observations)).zfill(3))
    result = scoped_invoke(command,receipt,cwd,env,timeout,grace=0.2,cleanup_timeout=3)
    row.update(status=result["status"],stdout=(receipt/"stdout").read_bytes().decode("utf-8","surrogateescape"),
               stderr=(receipt/"stderr").read_bytes().decode("utf-8","surrogateescape"),supervision={
                   "receipt":str(receipt),"cleanup":result.get("cleanup"),"program_status":result.get("program_status")})
    if row["status"]!=0 or row["stderr"] or not result.get("cleanup",{}).get("ok"):
        raise ValueError("Go capability command failed/cleanup incomplete or emitted unexpected stderr; see observations")
    return row["stdout"]


def prepare_go_capabilities(go_executable, outdir, environment=None):
    """Discover actual native/base CPU state once, before any workload timing."""
    if threading.current_thread() is not threading.main_thread() or len(list(Path("/proc/self/task").iterdir()))!=1:
        raise ValueError("Go capability discovery requires a single-threaded main-thread caller")
    parent = Path(outdir).resolve()
    parent.mkdir(parents=True,exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix="discovery-",dir=parent))
    observations = []
    try:
        env = go_build_environment(parent,"base",None,environment)
        driver = _file(go_executable)
        if driver["sha256"]!=GO_DRIVER_SHA256: raise ValueError("Go driver is not the exact reviewed compiler")
        goenv = json.loads(_capture([driver["path"],"env","-json","GOROOT","GOVERSION","GOEXPERIMENT","GOTOOLDIR","GOHOSTARCH","GOHOSTOS"],env,out,observations))
        validate_go_version(goenv.get("GOVERSION"))
        tools = {name:_file(Path(goenv["GOTOOLDIR"])/name) for name in GO_TOOL_SHA256}
        sources = {name:_file(Path(goenv["GOROOT"])/"src"/name) for name in GO_SOURCE_SHA256}
        if any(tools[k]["sha256"]!=v for k,v in GO_TOOL_SHA256.items()) or any(sources[k]["sha256"]!=v for k,v in GO_SOURCE_SHA256.items()):
            raise ValueError("Go compiler/source bytes are not reviewed")
        sdk = _sdk(goenv["GOROOT"],out/"sdk-inventory.json")
        probe_sources = {name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in PROBE_INPUTS}
        for name in ("go_cpu_probe.go","go_cpu_probe.s"):
            shutil.copyfile(Path(__file__).parent/name,out/name)
            if hashlib.sha256((out/name).read_bytes()).hexdigest()!=probe_sources[name]:
                raise ValueError("Go probe source changed while copying build inputs")
        (out/"go.mod").write_text("module paslang-cpu-metadata\n\ngo 1.27.3\n")
        binary = out/"go-cpu-probe"
        _capture([driver["path"],"build","-o",binary,"."],env,out,observations)
        artifact = _file(binary)
        native = json.loads(_capture([str(binary)],env,out,observations))
        options, reason = _selection(native)
        base = None
        if not reason:
            baseenv = dict(env,GODEBUG=",".join(filter(None,[env["GODEBUG"],*options])))
            base = json.loads(_capture([str(binary)],baseenv,out,observations))
        proof = {"format":GO_CAP_FORMAT,"policy_id":GO_POLICY,"compiler":{"driver":driver,"tools":tools},
            "sources":sources,"sdk":sdk,"go_environment":goenv,"probe_sources":probe_sources,
            "native_state":native,"base_state":base,"runtime_cpu_options":options,"base_supported":not reason,"baseline_reason":reason,"observations":observations}
        proof["identity_sha256"] = _digest(_identity(proof))
        # Bind raw receipt to the exact separately built metadata artifact.
        observations.append({"probe_binary":artifact})
        validate_go_capabilities(proof,go_executable)
        (out/"capabilities.json").write_text(json.dumps(proof,indent=1)+"\n")
        return proof
    finally:
        (out/"observations.json").write_text(json.dumps(observations,indent=1)+"\n")


def go_policy_description():
    return {"id":GO_POLICY,"reviewed_go_version":GO_REVIEWED_VERSION,"reviewed_version_tokens":list(GO_REVIEWED_VERSION_TOKENS),
        "architecture":"amd64","base_build_level":"v1","base_disabled_options":list(GO_BASE_DISABLED_FEATURES),
        "experiments":"exact installed nodwarf5 defaults; no experimental SIMD; user GOENV/GOEXPERIMENT disabled",
        "rep_preferences":"ERMS restored only when independently detected; FSRM must already be false; never force absent features",
        "native":"ordinary CPU detection, compiler hosts unmasked; target GOAMD64 remains explicit",
        "scope":"pinned dual-parser/effective-state policy; uncontrolled true optional ISA fields refuse baseline; no universal arbitrary-library claim"}


def go_binary_metadata(path):
    """Inspect actual ELF program headers; no executable or loader is run.

    Layout/tags follow the reviewed Go debug/elf/{elf.go,file.go} reference.
    Static baseline evidence deliberately excludes PT_DYNAMIC providers too.
    """
    path=Path(path).resolve(strict=True);data=path.read_bytes()
    if len(data)<64 or data[:7]!=b"\x7fELF\x02\x01\x01":
        raise ValueError("Go artifact must be a complete ELF64 little-endian executable")
    header=struct.unpack_from("<16sHHIQQQIHHHHHH",data)
    kind,machine,version,phoff,ehsize,phentsize,phnum=header[1],header[2],header[3],header[5],header[8],header[9],header[10]
    if kind not in (2,3) or machine!=62 or version!=1 or ehsize!=64 or phentsize!=56 or not 0<phnum<0xffff or phoff<64 or phoff+phnum*phentsize>len(data):
        raise ValueError("unsupported/malformed Go ELF header/program table")
    programs=[];interpreter=None;dynamic=None
    for index in range(phnum):
        entry=struct.unpack_from("<IIQQQQQQ",data,phoff+index*phentsize)
        tag,flags,offset,vaddr,paddr,size,memsize,align=entry
        if offset+size>len(data) or tag==1 and size>memsize:
            raise ValueError("Go ELF segment is outside its artifact")
        programs.append(entry)
        if tag==3:
            if interpreter is not None or size<2:
                raise ValueError("duplicate/malformed Go ELF interpreter")
            text=data[offset:offset+size]
            if not text.endswith(b"\0") or b"\0" in text[:-1]:
                raise ValueError("malformed Go ELF interpreter string")
            interpreter=text[:-1].decode("utf-8","surrogateescape")
        if tag==2:
            if dynamic is not None or size%16:
                raise ValueError("duplicate/malformed Go ELF dynamic segment")
            dynamic=[]
            for at in range(offset,offset+size,16):
                dt,value=struct.unpack_from("<qQ",data,at)
                if dt==0:break
                dynamic.append((dt,value))
            else:raise ValueError("unterminated Go ELF dynamic segment")
    if not any(tag==1 and flags&1 and va<=header[4]<va+size for tag,flags,off,va,pa,size,mem,align in programs):
        raise ValueError("Go ELF entry point is not in an executable load segment")
    needed=[]
    if dynamic:
        offsets=[v for tag,v in dynamic if tag==1]
        if offsets:
            addresses=[v for tag,v in dynamic if tag==5];sizes=[v for tag,v in dynamic if tag==10]
            if len(addresses)!=1 or len(sizes)!=1:
                raise ValueError("Go ELF dependencies lack one bounded dynamic string table")
            address,size=addresses[0],sizes[0]
            matches=[(off+address-va,size) for tag,fl,off,va,pa,sz,mem,al in programs if tag==1 and va<=address and address+size<=va+sz]
            if len(matches)!=1:raise ValueError("unmapped/ambiguous Go ELF dynamic strings")
            off,size=matches[0];strings=data[off:off+size]
            for start in offsets:
                if start>=len(strings):raise ValueError("Go ELF dependency string outside table")
                end=strings.find(b"\0",start)
                if end<0 or end==start:raise ValueError("unterminated/empty Go ELF dependency string")
                needed.append(strings[start:end].decode("utf-8","surrogateescape"))
    metadata={"format":"paslang-go-linked-program-v1","binary":{"path":str(path),"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()},
        "elf":{"class":64,"machine":machine,"type":kind},"needed":needed,"interpreter":interpreter,"has_dynamic_segment":dynamic is not None}
    metadata["identity_sha256"]=_digest(metadata)
    return metadata


def require_go_artifact_capabilities(cpu,metadata):
    """CPU proof does not certify an external C provider's runtime ISA."""
    try:
        if cpu not in ("native","base") or not isinstance(metadata,dict) or set(metadata)!={"format","binary","elf","needed","interpreter","has_dynamic_segment","identity_sha256"}:
            raise ValueError("missing/malformed Go artifact metadata")
        fields={key:value for key,value in metadata.items() if key!="identity_sha256"}
        if metadata["format"]!="paslang-go-linked-program-v1" or metadata["identity_sha256"]!=_digest(fields):
            raise ValueError("Go artifact identity mismatch")
        binary,elf=metadata["binary"],metadata["elf"]
        if (not isinstance(binary,dict) or set(binary)!={"path","bytes","sha256"} or not isinstance(binary["path"],str)
            or type(binary["bytes"]) is not int or binary["bytes"]<64 or not isinstance(binary["sha256"],str) or len(binary["sha256"])!=64 or any(c not in "0123456789abcdef" for c in binary["sha256"])
            or elf not in ({"class":64,"machine":62,"type":2},{"class":64,"machine":62,"type":3})
            or not isinstance(metadata["needed"],list) or not all(isinstance(n,str) and n for n in metadata["needed"])
            or metadata["interpreter"] is not None and (not isinstance(metadata["interpreter"],str) or not metadata["interpreter"])
            or type(metadata["has_dynamic_segment"]) is not bool):
            raise ValueError("malformed Go artifact provider metadata")
        if cpu=="base" and (metadata["has_dynamic_segment"] or metadata["interpreter"] or metadata["needed"]):
            raise ValueError("Go baseline provider ISA unproved: external/dynamic ELF provider; native remains available")
        return {"cpu":cpu,"artifact_identity_sha256":metadata["identity_sha256"],"binary_sha256":binary["sha256"],
                "provider_policy":"ordinary native linkage" if cpu=="native" else "no dynamic/interpreter/provider segment"}
    except (KeyError,TypeError,AttributeError) as error:
        raise ValueError("malformed Go artifact metadata") from error
