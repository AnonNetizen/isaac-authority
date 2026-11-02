local leaf={value=1};local a={left=leaf,right=leaf,position=2};local b={parent=a};a.next=b
__tag(a,"personal");a.position=3;__tag(a,"personal")
leaf.value=7;__tag(a,"personal");a.position=4;__tag(a,"personal")
return a.left.value,a.right.value,a.next.parent.position
