observed = {keep = __tag(7, 'personal_option:keep'), other = 1}
local value = __tag(11, 'world:old')
local unrelated = 22
reader = function() return value end
reader_alias = function() return value end
writer = function(v) value = v end
other_writer = function(v) unrelated = v end
other_reader = function() return unrelated end
return observed.keep, reader(), reader_alias()
