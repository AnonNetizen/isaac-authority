observed = {10, 20, 30, 40, 50, 60, 70, __tag(80, 'retained')}
for i = 2, 7 do observed[i] = nil end
return observed[1], observed[8]
