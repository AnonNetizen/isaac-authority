local a={x=1};local b={x=2};a.next=b;b.next=a
__tag(a,"personal");__tag(a,"world");__tag(a,"personal")
local old=b;a.next={x=3};__tag(a,"personal");__tag(a,"world")
old.x=__tag(9,"replacement");__tag(a,"personal")
return a.next.x,old.x,old.next.x
