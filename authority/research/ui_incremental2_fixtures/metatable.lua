backing = {}
observed = setmetatable({}, {__newindex = function(_, key, value) backing[key] = value end})
observed.value = __tag(13, 'redirected')
return rawget(observed, 'value'), backing.value
