if not settings_object then
    local fields=__config()
    fields.read=function(self)return self.amount end
    settings_object=__authority_ui_userdata('Vector',fields)
end
collectgarbage('collect')
local cached=settings_object.read
return cached(settings_object),settings_object.x,settings_object.language,'amount='..settings_object.amount
