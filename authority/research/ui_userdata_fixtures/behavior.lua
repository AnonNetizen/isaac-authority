local kinds={'Vector','Color','KColor','Font','FontRenderSettings','Sprite','BitSet128'}
local sum=0
for i,kind in ipairs(kinds) do
    local fields={amount=__tag(i,'personal_config:amount'),x=137}
    fields.read=function(self)return self.amount end
    local object=__authority_ui_userdata(kind,fields)
    local alias=object
    local cached=object.read
    alias.amount=alias.amount+1
    sum=sum+cached(object)
end
collectgarbage('collect')
return sum,137
