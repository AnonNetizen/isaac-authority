A=RegisterMod('Shared Name',1)
AHelper=RegisterMod('A Helper',1)
function RegisterViaA(name)return RegisterMod(name,1)end
SDK_counter=0
SharedCallback=function(self)Isaac.RenderText(self==A and 'shared-a' or 'shared-b',0,0)end
A:AddCallback(1,function()Isaac.GetPlayer(0):AddCoins(1)end)
A:AddCallback(2,function()
 SDK_counter=SDK_counter+1
 if Input.IsButtonTriggered('save')then A:SaveData('saved-a')end
 Isaac.RenderText('A:'..A:LoadData()..'|n='..SDK_counter,10,0)
end)
A:AddCallback(20,SharedCallback)
A:AddPriorityCallback(21,2,function()Isaac.RenderText('priority-a',0,0)end)
A:AddPriorityCallback(23,-1,function()Isaac.RenderText('stop-false',0,0);return false end)
A:AddCallback(24,function()
 A:SaveData('bad-a');B:SaveData('bad-b');SDK_counter=99
 Isaac.GetPlayer(0):GetNumCoins();Isaac.RenderText('unpublished',0,0);error('sdk-injected')
end)
A:AddCallback(25,function()Isaac.RenderText(tostring(A:HasData()),0,0)end)
A:AddCallback(26,function()Isaac.RenderText(A:LoadData(),0,0)end)
AHelper:AddPriorityCallback(21,-1,function()Isaac.RenderText('priority-helper',0,0)end)
