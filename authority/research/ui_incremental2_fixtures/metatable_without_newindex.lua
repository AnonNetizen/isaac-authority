observed = setmetatable({}, {__index = function() return 'fallback' end})
observed.value = __tag(N, 'external')
return rawget(observed, 'value'), rawlen(observed), rawget(observed, 'missing')
