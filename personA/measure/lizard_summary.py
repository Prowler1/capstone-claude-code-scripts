import csv,sys,statistics as st
rows=[]
for r in csv.reader(open(sys.argv[1],encoding='utf-8',errors='replace')):
    nloc,ccn,tok,par,length=map(int,r[:5]); f=r[6].replace(chr(92),'/'); rows.append((nloc,ccn,length,f,r[7],int(r[9]),int(r[10])))
def corpus(f):
    if f.startswith('mods/'): return 'mods/'+f.split('/')[1]
    if f.startswith('plugins/'): return 'plugins (py)'
    return 'scripts (ts)'
groups={}
for x in rows: groups.setdefault(corpus(x[3]),[]).append(x)
groups['ALL']=rows
print(f"{'corpus':22}{'fns':>5}{'meanCCN':>8}{'medCCN':>7}{'p90':>5}{'max':>5}{'CCN>10':>7}{'CCN>15':>7}{'len>60':>7}")
for k,v in groups.items():
    c=sorted(x[1] for x in v); n=len(c)
    print(f"{k:22}{n:5}{st.mean(c):8.2f}{st.median(c):7}{c[int(.9*n)]:5}{c[-1]:5}{sum(i>10 for i in c):7}{sum(i>15 for i in c):7}{sum(x[2]>60 for x in v):7}")
print("\nTop 15 by CCN:")
for x in sorted(rows,key=lambda x:-x[1])[:15]: print(f"CCN={x[1]:3} len={x[2]:4} nloc={x[0]:4} {x[3]}:{x[5]}-{x[6]} {x[4]}")
print("\nTop 8 by length:")
for x in sorted(rows,key=lambda x:-x[2])[:8]: print(f"len={x[2]:4} CCN={x[1]:3} {x[3]}:{x[5]}-{x[6]} {x[4]}")
print("\nregister.ts / auto-close entries:")
for x in rows:
    if x[3].endswith('diff/hooks/register.ts') and x[1]>=5 or 'auto-close' in x[3]: print(f"CCN={x[1]:3} len={x[2]:4} {x[3]}:{x[5]}-{x[6]} {x[4]}")
