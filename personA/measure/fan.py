import json,sys,collections,statistics as st
for mod in sys.argv[2:]:
    g=json.load(open(f"{sys.argv[1]}/m2-{mod}.json"))
    g={k:[d for d in v if d!=k] for k,v in g.items()}
    fin=collections.Counter(d for v in g.values() for d in v)
    fout={k:len(v) for k,v in g.items()}
    n=len(g); E=sum(fout.values())
    pkg=lambda p: p.split('/')[0] if '/' in p else p.replace('.ts','')
    P=collections.defaultdict(set)
    for k,v in g.items():
        for d in v:
            if pkg(k)!=pkg(d): P[pkg(k)].add(pkg(d))
    pin=collections.Counter(d for v in P.values() for d in v)
    pkgs=sorted({pkg(k) for k in g})
    # non-self cycles via SCC
    idx={};low={};stack=[];on=set();sccs=[];c=[0]
    sys.setrecursionlimit(10000)
    def sc(v):
        idx[v]=low[v]=c[0];c[0]+=1;stack.append(v);on.add(v)
        for w in g.get(v,[]):
            if w not in idx: sc(w);low[v]=min(low[v],low[w])
            elif w in on: low[v]=min(low[v],idx[w])
        if low[v]==idx[v]:
            s=[]
            while True:
                w=stack.pop();on.discard(w);s.append(w)
                if w==v:break
            if len(s)>1:sccs.append(s)
    for v in g:
        if v not in idx: sc(v)
    print(f"== {mod}: files={n} edges={E} mean_fanout={E/n:.2f} median_fanout={st.median(fout.values())} multi-file cycles={len(sccs)} packages={len(pkgs)}")
    print("  top fan-out files:",sorted(fout.items(),key=lambda x:-x[1])[:5])
    print("  top fan-in files:",fin.most_common(5))
    print("  pkg fan-out:",sorted(((p,len(P[p])) for p in pkgs),key=lambda x:-x[1])[:6])
    print("  pkg fan-in:",pin.most_common(6))
    print("  pkgs with fan-out 0:",sum(1 for p in pkgs if len(P[p])==0),"/",len(pkgs))
    if sccs: print("  cycles:",[sorted(s)[:4] for s in sccs][:5])
