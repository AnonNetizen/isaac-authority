backing = {}
observed = setmetatable({}, {__newindex = backing})
observed.value = __tag(N, 'external')
return rawlen(observed), rawget(observed, 'value'), backing.value
