if not keeper then
  local state = __tag({value = 7}, 'world')
  keeper = function() return state.value end
end
local garbage = {}
for i = 1, 32 do
  local object = {value = i}
  object.self = object
  garbage[i] = function() return object.value end
end
garbage = nil
collectgarbage('collect')
return keeper(), N
