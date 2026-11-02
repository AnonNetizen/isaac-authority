local get = rawget
local total = 0
for i = 1, N do total = total + get(observed, 'value') end
return total, observed.unused
