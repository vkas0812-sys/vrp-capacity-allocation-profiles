"""Freeze locally available, hash-checked inputs and executable sources for a run."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
SRC=HERE.parent
sys.path.insert(0,str(SRC))
from external_ablation import PARENTS


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("run","initial","holdout"):parser.add_argument(name,type=Path)
    args=parser.parse_args();run=args.run.resolve()
    run.mkdir(parents=True,exist_ok=False)
    for d in ("inputs","bin","src/overnight"): (run/d).mkdir(parents=True)
    with (SRC/"holdout_parents.csv").open() as f:more=list(csv.DictReader(f))
    with (SRC/"results/external_ablation.csv").open() as f:initial_hash={r["parent"]:r["sha256"] for r in csv.DictReader(f)}
    parents=list(PARENTS)+[r["parent"] for r in more];hashes={}
    for i,name in enumerate(parents):
        origin=(args.initial if i<len(PARENTS) else args.holdout)/(name+".vrp")
        data=origin.read_bytes()
        if i<len(PARENTS):assert hashlib.sha256(data).hexdigest()==initial_hash[name]
        else:assert hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()==more[i-len(PARENTS)]["git_blob"]
        (run/"inputs"/origin.name).write_bytes(data)
        hashes[name]=hashlib.sha256(data).hexdigest()
    sources={}
    for path in [SRC/f for f in ("regret_bound.py","allocation_transfer.py","external_ablation.py","benchmark.py","six_vehicle_join.cpp")]+list(HERE.glob("*.py"))+[HERE/"profile_dag.cpp"]:
        target=run/"src"/path.relative_to(SRC);shutil.copyfile(path,target)
        sources[str(path.relative_to(SRC))]=hashlib.sha256(target.read_bytes()).hexdigest()
    for name,source in (("profile_dag","overnight/profile_dag.cpp"),("six_join","six_vehicle_join.cpp")):
        subprocess.run(["c++","-std=c++17","-O3",str(run/"src"/source),"-o",str(run/"bin"/name)],check=True)
    label="local.iccsa."+run.name.lower().replace("_","-")
    job=dict(Label=label,ProgramArguments=["/usr/bin/caffeinate","-i","-s",sys.executable,
              str(run/"src/overnight/campaign.py"),str(run),"--hours","8"],
             WorkingDirectory=str(run),RunAtLoad=True,KeepAlive=False,
             StandardOutPath=str(run/"supervisor.log"),StandardErrorPath=str(run/"supervisor.err"))
    (run/"job.plist").write_bytes(plistlib.dumps(job))
    (run/"manifest.json").write_text(json.dumps(dict(parents=parents,sha256=hashes,sources=sources,
        python=sys.version,compiler=subprocess.check_output(["c++","--version"],text=True).splitlines()[0],label=label),indent=2))
    print(run)


if __name__=="__main__":main()
