observed = {}
local insert = table.insert
for i = 1, N do insert(observed, __tag(i, 'reward')) end
return #observed, observed[1], observed[N], observed[1] + observed[N]
