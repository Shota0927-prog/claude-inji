import random
CAT=6
def hard_end(tick,wLim):
    n=len(tick); out=[0]*n; j=1
    for a in range(n):
        ta=tick[a]
        if j<a+1: j=a+1
        while j<n and not (tick[j]-ta>wLim): j+=1
        out[a]=j
    return out
def hard_end_ref(tick,wLim):
    n=len(tick); out=[]
    for a in range(n):
        lim=n
        for b in range(a+1,n):
            if tick[b]-tick[a]>wLim: lim=b; break
        out.append(lim)
    return out
def cnt_prefix(cat,he):
    n=len(cat)
    pf=[[0]*CAT for _ in range(n+1)]
    for i in range(n):
        pf[i+1]=pf[i][:]; pf[i+1][cat[i]]+=1
    return [sum(1 for c in range(CAT) if pf[he[a]][c]>pf[a][c]) for a in range(n)]
def cnt_slide(cat,he):
    n=len(cat); cc=[0]*CAT; right=0; out=[]
    for a in range(n):
        lim=he[a]
        while right<lim:
            cc[cat[right]]+=1; right+=1
        out.append(sum(1 for c in range(CAT) if cc[c]>0))
        cc[cat[a]]-=1
        assert min(cc)>=0, "negative count"
    return out
def cnt_ref(cat,he):
    return [len(set(cat[a:he[a]])) for a in range(len(cat))]
random.seed(7)
bad=0
for t in range(200000):
    n=random.choice([0,1,2,3,5,10,40])
    # non-decreasing ticks, with ties and negatives
    base=random.randint(-50,50); tick=[]
    v=base
    for _ in range(n):
        v+=random.choice([0,0,0,1,2,7]); tick.append(v)
    wLim=random.choice([0,1,2,3,10,100])
    cat=[random.randrange(random.choice([1,2,6])) for _ in range(n)]
    he=hard_end(tick,wLim); heR=hard_end_ref(tick,wLim)
    if he!=heR: bad+=1; print("HE mismatch",tick,wLim,he,heR); break
    if n==0: continue
    assert all(he[a]>=a+1 for a in range(n)), ("he<a+1",tick,wLim,he)
    a1=cnt_prefix(cat,he); a2=cnt_slide(cat,he); a3=cnt_ref(cat,he)
    if not (a1==a2==a3):
        bad+=1; print("CNT mismatch",tick,wLim,cat,he,a1,a2,a3); break
print("cases=200000 mismatches=%d" % bad)
