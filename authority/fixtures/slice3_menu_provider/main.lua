-- Framework contract model only. This is not the real MCM implementation.
local entries = {}
ModConfigMenu = {OptionType={NUMBER=1},MenuData=entries}
function ModConfigMenu.AddSetting(category,subcategory,setting)
    if type(subcategory)=='table' and setting==nil then setting=subcategory;subcategory='Uncategorized' end
    assert(type(category)=='string' and type(subcategory)=='string' and type(setting)=='table')
    entries[#entries+1]={category=category,subcategory=subcategory,setting=setting}
    return setting
end
function ModConfigMenu.Change(index,value)
    local item=entries[index].setting
    local previous=type(item.CurrentSetting)=='function' and item.CurrentSetting() or item.CurrentSetting
    item.OnChange(value)
    return previous
end
function ModConfigMenu.Render(index,x)
    local item=entries[index].setting
    local current=type(item.CurrentSetting)=='function' and item.CurrentSetting() or item.CurrentSetting
    local text=type(item.Display)=='function' and item.Display() or item.Display
    Isaac.RenderText(text,x,10,1,1,1,1)
    return current,text
end
