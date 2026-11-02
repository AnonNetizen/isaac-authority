local t={amount=1};local function read() return t.amount end
__tag(read,"personal");__tag(read,"world");__tag(read,"personal")
t.amount=7;__tag(read,"personal");__tag(read,"world")
return read()
