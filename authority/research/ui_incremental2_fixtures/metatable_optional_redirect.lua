backing = {}
observed = setmetatable({}, {__newindex = function(_, key, value) backing[key] = value end})
observed.value = __tag(N, 'external')
return rawlen(observed), rawget(observed, 'value'), backing.value
