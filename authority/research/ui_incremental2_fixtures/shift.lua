observed = {__tag(10, 'a'), __tag(20, 'b'), __tag(30, 'c')}
local insert, remove = table.insert, table.remove
insert(observed, 2, __tag(99, 'new'))
local removed = remove(observed, 3)
return observed[1], observed[2], observed[3], removed, #observed
