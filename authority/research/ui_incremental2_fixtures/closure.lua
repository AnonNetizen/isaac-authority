local state = {amount = __tag(1, 'initial')}
local function make()
    return function(value)
        if value then state.amount = value end
        return state.amount
    end
end
local first, second = make(), make()
local before = first()
first(__tag(9, 'updated'))
return before, second(), first(), string.char(0, 255, 65), false, nil
