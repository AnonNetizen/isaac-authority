observed = {leaf = {amount = 7}, tick = 0}
__tag(observed, 'reward')
for i = 1, N do
    observed.tick = i
    __tag(observed, 'reward')
end
return observed.leaf.amount, observed.tick
