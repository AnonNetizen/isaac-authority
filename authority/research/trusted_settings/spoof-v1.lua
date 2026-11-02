-- Same apparent framework filename/function name, different source/prototype.
function SpoofPostRender()
    local optionDisplay = AuditSetting.Display
    local result = optionDisplay(false, false, Vector(3, 4))
    Isaac.RenderText(tostring(result), 0, 0)
end
