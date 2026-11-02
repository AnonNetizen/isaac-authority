observed = {untouched = __tag(8, 'other')}
local alias = rawset(observed, 'value', __tag(9, 'new'))
return type(alias), alias.untouched, alias.value
