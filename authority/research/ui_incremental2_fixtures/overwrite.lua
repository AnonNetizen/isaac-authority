observed = {value = __tag(0, 'old'), unrelated = __tag(7, 'other')}
local put = rawset
for i = 1, N do put(observed, 'value', __tag(i, 'new')) end
return observed.value, observed.unrelated, rawget(observed, 'value'), rawlen(observed)
