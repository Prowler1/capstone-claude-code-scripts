import csv,sys,statistics as st,collections
def load(p):
    rows=[r for r in csv.DictReader(open(p,encoding='utf-8'))]
    for r in rows: r['ccn']=int(r['ccn']); r['lines']=int(r['lines'])
    return rows
rows=load(sys.argv[1])
def corpus(f):
    i=f.find('mods/'); 
    return 'mods/'+f[i:].split('/')[1] if i>=0 else 'scripts'
g=collections.defaultdict(list)
for r in rows: g[corpus(r['file'])].append(r)
print(f"{'corpus':16}{'fns':>5}{'mean':>6}{'med':>4}{'p90':>4}{'max':>4}{'>10':>4}{'>15':>4}")
for k in sorted(g):
    c=sorted(r['ccn'] for r in g[k]); n=len(c)
    print(f"{k:16}{n:5}{st.mean(c):6.2f}{st.median(c):4}{c[int(.9*n)]:4}{c[-1]:4}{sum(x>10 for x in c):4}{sum(x>15 for x in c):4}")
print("\nTop TS functions by CCN:")
for r in sorted(rows,key=lambda r:-r['ccn'])[:10]: print(f"  {r['ccn']:3} {r['lines']:4}L {r['file'][r['file'].find('mods/') if 'mods/' in r['file'] else r['file'].find('scripts/'):]}:{r['start']}-{r['end']} {r['function']}")
def filesum(rows,suffix):
    # file-level CCN: decision points across all functions in the file (outer fns counted once each)
    return sum(r['ccn'] for r in rows if r['file'].endswith(suffix)), sum(1 for r in rows if r['file'].endswith(suffix))
tot=collections.Counter(); reg=collections.Counter()
for r in rows:
    k=corpus(r['file'])
    if k.startswith('mods'):
        tot[k]+=r['ccn']-1  # decision points only, so closures don't inflate by count
        if r['file'].endswith('hooks/register.ts'): reg[k]+=r['ccn']-1
print("\nregister.ts share of each mod's decision points:")
for k in sorted(tot): print(f"  {k:16} {reg[k]:4}/{tot[k]:4} = {100*reg[k]/tot[k]:.1f}%")
if len(sys.argv)>2:
    after=load(sys.argv[2])
    for label,rs in (('before',[r for r in rows if 'mods/diff' in r['file']]),('after',after)):
        reg=[r for r in rs if r['file'].endswith('hooks/register.ts')]
        bl=[r for r in rs if 'body-loader' in r['file']]
        print(f"\n{label}: register.ts fns={len(reg)} decision_points={sum(r['ccn']-1 for r in reg)} max={max(r['ccn'] for r in reg)} | body-loader decision_points={sum(r['ccn']-1 for r in bl)} | diff total={sum(r['ccn']-1 for r in rs)}")
        print("   top in register:",[(r['function'],r['start'],r['ccn']) for r in sorted(reg,key=lambda r:-r['ccn'])[:6]])
