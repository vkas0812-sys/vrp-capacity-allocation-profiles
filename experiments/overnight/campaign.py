"""Bounded, single-worker macOS campaign. Run from the frozen run snapshot."""
import argparse
import csv
from datetime import datetime,timezone,timedelta
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
from statistics import median,mean
import subprocess
import sys
from time import monotonic,sleep,time
import traceback

import psutil


def atomic(path,data):
    tmp=path.with_suffix(path.suffix+".tmp");tmp.write_text(data);tmp.replace(path)


def stamp(t=None):
    return datetime.fromtimestamp(time() if t is None else t,timezone(timedelta(hours=7))).isoformat(timespec="seconds")


def plan(parents):
    jobs=[]
    def add(kind,n,k,B,site,seed,mode="hash",batch=1,stage="coverage",limit=90):
        j=dict(kind=kind,n=n,k=k,B=B,site=site,seed=seed,parent=parents[site%len(parents)],mode=mode,batch=batch,
               stage=stage,limit=limit)
        key="-".join(str(j[x]) for x in ("kind","n","k","B","site","seed","mode","batch"))
        j["id"]=key
        if key not in seen:
            jobs.append(j);seen.add(key)
    seen=set()
    # Quick pilots for every objective before any large case.
    for mode in ("hash","dense","rank"):add("index",12,4,4,0,0,mode)
    for mode in ("cold","hash"):add("batch",16,4,4,0,0,mode,5)
    for seed in range(12):add("policy",16,4,4,0,seed)
    add("certificate",24,6,4,0,0)
    for mode in ("three","baseline","two"):add("anchor",24,6,4,0,0,mode)
    for k,n in ((4,16),(6,18),(8,20)):
        for B in (2,4,6,8):add("budget",n,k,B,1,0,limit=35)
    # Multiple scenarios per depot, first half for fitting, second half held out.
    for seed in range(16):
        for site in range(4):add("policy",16,4,4,site,seed)
    for site in range(6):
        add("certificate",24,6,4,site,1)
        for b in (1,5,20,50):
            for mode in ("cold","hash"):add("batch",16,4,4,site,2,mode,b,limit=100)
    for n in (24,26,28):
        for mode in ("rank","hash","dense"):add("index",n,6,4,0,1,mode,limit=65)
    for site in range(3):
        for cut in (2,4,6,8):
            for k,n in ((4,20),(6,24),(8,24)):
                add("budget",n,k,cut,site,3,stage="scaling",limit=100)
    # Interleave six arms instead of completing a long arm before the others.
    for seed in range(10):
        for site in range(10):
            stage="replicate"
            for mode in ("baseline","two","three"):add("anchor",24,6,4,site,seed,mode,stage=stage,limit=100)
            for mode in ("hash","rank","dense"):add("index",(24,26,28)[(site+seed)%3],6,4,site,seed,mode,stage=stage,limit=180)
            add("certificate",24,6,4,site,seed,stage=stage)
            for mode in ("cold","hash"):add("batch",20,4,4,site,seed,mode,(5,20,50)[seed%3],stage=stage,limit=240)
            add("policy",20,4,4,site,seed,stage=stage,limit=75)
            add("budget",24,8,(2,4,6,8)[seed%4],site,seed,stage=stage,limit=240)
    return jobs


def run_job(run,j,deadline):
    env=dict(os.environ,PYTHONPATH=str(run/"src"),OPENBLAS_NUM_THREADS="1",OMP_NUM_THREADS="1",
             VECLIB_MAXIMUM_THREADS="1",MKL_NUM_THREADS="1",PYTHONUNBUFFERED="1")
    start=monotonic();peak=0;status=None
    cmd=[sys.executable,str(run/"src/overnight/cases.py"),str(run),json.dumps(j)]
    with (run/"worker.out").open("w") as out,(run/"worker.err").open("w") as err:
        proc=subprocess.Popen(cmd,stdout=out,stderr=err,env=env,start_new_session=True)
        try:
            while proc.poll() is None:
                try:
                    parent=psutil.Process(proc.pid)
                    processes=[parent]+parent.children(recursive=True)
                    rss=0
                    for p in processes:
                        try:rss+=p.memory_info().rss
                        except psutil.NoSuchProcess: pass
                    peak=max(peak,rss)
                except psutil.NoSuchProcess: pass
                if peak>2500*1024**2:status="rss_limit"
                elif time()>=deadline:status="campaign_deadline"
                elif monotonic()-start>=j["limit"]:status="timeout"
                elif (run/"STOP").exists():status="stopped"
                if status:break
                sleep(.2)
        finally:
            if proc.poll() is None:
                try:os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            proc.wait()
    record=dict(job=j,wall_s=round(monotonic()-start,4),peak_rss_sampled_mib=round(peak/1024**2,2),ended=stamp())
    if status:return dict(record,status=status)
    if proc.returncode:
        return dict(record,status="error",detail=(run/"worker.err").read_text()[-1600:])
    return dict(record,**json.loads((run/"worker.out").read_text()))


def identity(j):
    return tuple(j[x] for x in ("n","k","B","site","seed"))


def report(run,records,current,deadline):
    from collections import Counter,defaultdict
    lines=["# Thực nghiệm qua đêm","",f"Cập nhật {stamp()}. Hạn dừng {stamp(deadline)}.",
           f"Trạng thái: {current}. Đã ghi {len(records)} tác vụ.","",
           "| Nhánh | Hoàn tất | Hết giờ | Giới hạn tài nguyên | Lỗi / khác |",
           "|---|---:|---:|---:|---:|"]
    for kind in ("anchor","index","certificate","batch","budget","policy"):
        c=Counter(r["status"] for r in records if r["job"]["kind"]==kind)
        lines.append(f"| {kind} | {c['ok']} | {c['timeout']} | {c['rss_limit']+c['resource_limit']} | {sum(c.values())-sum(c[k] for k in ('ok','timeout','rss_limit','resource_limit'))} |")
    good=[r for r in records if r["status"]=="ok"]
    def pairs(kind,base,alt):
        groups=defaultdict(dict)
        for r in good:
            j=r["job"]
            if j["kind"]==kind:groups[identity(j)+(j["batch"],)][j["mode"]]=r
        return [(v[base],v[alt]) for v in groups.values() if base in v and alt in v]
    lines+=["","## So sánh ghép cặp","",
            "Hệ số là trung vị thời gian phương án đầu chia phương án sau, trên các ca cả hai hoàn tất. Tỷ lệ hoàn tất và giới hạn tài nguyên phải được đọc cùng thời gian. Peak RSS là tổng RSS lấy mẫu của worker và tiến trình con, có thể tính trùng trang dùng chung.",""]
    for kind,x,y in (("anchor","baseline","three"),("anchor","baseline","two"),("index","dense","rank"),
                     ("index","hash","rank"),("batch","cold","hash")):
        pp=pairs(kind,x,y)
        if pp:
            vals=[a["wall_s"]/b["wall_s"] for a,b in pp]
            mem=[a["peak_rss_sampled_mib"]/max(1,b["peak_rss_sampled_mib"]) for a,b in pp]
            lines.append(f"- {kind}, {x} / {y}: {len(pp)} cặp; thời gian {median(vals):.2f}×, RSS {median(mem):.2f}×.")
    cert=[r["result"] for r in good if r["job"]["kind"]=="certificate"]
    if cert:
        lines+=["",f"- Với nghiệm heuristic thực sự tìm được: {sum(r['certified_gain_pct']<=1 for r in cert)}/{len(cert)} ca chứng nhận tối ưu tiếp tiết kiệm tối đa 1%; ở mức 2% là {sum(r['certified_gain_pct']<=2 for r in cert)}/{len(cert)}."]
    lines+=["","## Giới hạn mở rộng",""]
    sizes=defaultdict(list)
    for r in records:
        j=r["job"]
        if j["kind"] in ("budget","index"):sizes[j["kind"],j["n"],j["k"],j["B"]].append(r)
    for (kind,n,k,b),rs in sorted(sizes.items()):
        ok=[r for r in rs if r["status"]=="ok"]
        lines.append(f"- {kind}, n={n}, k={k}, B={b}: {len(ok)}/{len(rs)} lượt hoàn tất.")
    lines+=["","## Quyết định cấu hình trước khi biết nhu cầu",""]
    groups=defaultdict(dict)
    for r in good:
        j=r["job"]
        if j["kind"]=="policy":groups[(j["site"],j["n"])][j["seed"]]=r["result"]["design_costs"]
    for (site,n),data in sorted(groups.items()):
        split=8 if n==16 else 5
        if not all(i in data for i in range(2*split)):continue
        def regret(d,c):return c[d]/min(c.values())-1
        train=[data[i] for i in range(split)]
        test=[data[i] for i in range(split,2*split)]
        designs=sorted(train[0]);fixed={"mean":min(designs,key=lambda d:mean(regret(d,c) for c in train)),
             "minimax":min(designs,key=lambda d:max(regret(d,c) for c in train))}
        lines.append(f"- Depot {site}, n={n}: "+", ".join(f"{p} chọn {d}, regret kiểm tra TB {100*mean(regret(d,c) for c in test):.2f}%, tệ nhất {100*max(regret(d,c) for c in test):.2f}%" for p,d in fixed.items())+".")
    atomic(run/"REPORT.md","\n".join(lines)+"\n")


def execute(run,hours):
    lock=(run/"worker.lock").open("w")
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    manifest=json.loads((run/"manifest.json").read_text())
    clock=run/"clock.json"
    if not clock.exists():atomic(clock,json.dumps(dict(start=stamp(),deadline=time()+hours*3600)))
    deadline=json.loads(clock.read_text())["deadline"]
    entries=plan(manifest["parents"])
    atomic(run/"plan.json",json.dumps(entries,indent=1))
    (run/"jobs").mkdir(exist_ok=True)
    archive=sorted((run/"jobs").glob("*.json"))
    records=[json.loads(p.read_text()) for p in archive]
    done={r["job"]["id"] for r in records if r["status"] not in ("stopped","campaign_deadline")}
    seen={};batch_hash={};heuristic={}
    def validate(r):
        if r["status"]!="ok":return
        j=r["job"];v=r["result"];key=identity(j)
        if j["kind"]=="certificate":
            heuristic[key]=v
            if key in seen:
                best=min(cost for _,cost in seen[key].values())
                assert v["cut_bound"]<=best<=v["incumbent"]
            return
        prof=v["profile"]
        if key in seen:assert prof==seen[key],f"inconsistent profile {key}"
        if key in heuristic:
            best=min(cost for _,cost in prof.values())
            assert heuristic[key]["cut_bound"]<=best<=heuristic[key]["incumbent"]
        if j["kind"]=="batch":
            batchkey=key+(j["batch"],)
            assert batch_hash.setdefault(batchkey,v["hashes"])==v["hashes"]
        seen[key]=prof
    for r in records:validate(r)
    def status(state,job=None):
        atomic(run/"status.json",json.dumps(dict(state=state,updated=stamp(),deadline=stamp(deadline),
               completed=len(records),planned=len(entries),pid=os.getpid(),job=job),indent=2))
    reason="queue_complete"
    for j in entries:
        if time()>=deadline:reason="deadline";break
        if (run/"STOP").exists():reason="stopped";break
        if j["id"] in done:continue
        status("running",j)
        try:r=run_job(run,j,deadline)
        except Exception:r=dict(job=j,status="error",detail=traceback.format_exc()[-2200:],ended=stamp())
        try:validate(r)
        except AssertionError:
            r["status"]="validation_error";r["detail"]=traceback.format_exc()[-1500:]
        atomic(run/"jobs"/(j["id"]+".json"),json.dumps(r))
        records=[old for old in records if old["job"]["id"]!=j["id"]]+[r]
        report(run,records,"running",deadline)
        if r["status"]=="validation_error":reason="validation_error";break
    status(reason)
    report(run,records,reason,deadline)
    return 2 if reason=="validation_error" else 0


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run",type=Path)
    parser.add_argument("--hours",type=float,default=8.)
    args=parser.parse_args()
    sys.exit(execute(args.run.resolve(),args.hours))
