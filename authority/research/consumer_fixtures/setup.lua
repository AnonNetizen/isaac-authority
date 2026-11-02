settings = __config()
local reward = settings.amount
local other = settings.x
reader = function() return reward end
reader_alias = function() return reward end
writer = function(v) reward = v end
other_writer = function(v) other = v end
cached = 'amount=' .. reward
return settings.amount, settings.x, reader(), cached, reader_alias()
